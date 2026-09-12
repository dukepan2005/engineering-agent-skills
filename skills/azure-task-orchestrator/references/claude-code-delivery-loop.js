// Azure Task Orchestrator: flat Claude Code delivery loop
//
// The parent Workflow owns every child dispatch after plan confirmation. An
// implementation child never starts review children; the parent starts the
// Standards and Spec workers directly and aggregates their JSON results.
//
// Input (args):
// {
//   "validatedPlan": [{
//     "id": "AB#123",
//     "type": "Task",
//     "title": "...",
//     "plannedProfile": "sol-medium",
//     "orderReason": "..."
//   }],
//   "trackerConnection": {
//     "organization": "https://dev.azure.com/example",
//     "project": "ExampleProject",
//     "team": "Example Team"
//   },
//   "plannerReport": { "full planner report object": true }
// }

export const meta = {
  name: 'azure-task-orchestrator-delivery',
  description: 'Deliver profiled work items with parent-owned flat implementation and review workers',
  phases: [
    { title: 'Preflight', detail: 'Read work-item scope and acceptance criteria' },
    { title: 'Implement', detail: 'Implement with exact model and reasoning effort' },
    { title: 'Review', detail: 'Run Standards and Spec review workers in parallel' },
    { title: 'Repair', detail: 'Repair findings and amend the same task commit' },
    { title: 'Closeout', detail: 'Close item and update checklist with evidence' },
  ],
}

// Execution profile registry: profile ID → {model, effort}
const PROFILES = {
  'terra-medium': { model: 'sonnet', effort: 'medium' },
  'terra-high': { model: 'sonnet', effort: 'high' },
  'terra-xhigh': { model: 'sonnet', effort: 'xhigh' },
  'sol-medium': { model: 'opus', effort: 'medium' },
  'sol-high': { model: 'claude-opus-5', effort: 'high' },
  'sol-max': { model: 'claude-opus-5', effort: 'max' },
  'sol-xhigh': { model: 'claude-opus-5', effort: 'xhigh' },
}

// A completed flat review still has a blocking finding; recovery gets one
// stronger profile. This is not a normal planning-ladder fallback.
const REVIEW_ESCALATION = {
  'terra-medium': 'sol-high',
  'terra-high': 'sol-high',
  'sol-medium': 'sol-high',
  'sol-high': 'sol-max',
}

function resolveProfile(profileId) {
  const profile = PROFILES[profileId]
  if (!profile) throw new Error(`Unknown profile ID: ${profileId}`)
  return profile
}

function parseJson(value, label) {
  try {
    return typeof value === 'string' ? JSON.parse(value) : value
  } catch (error) {
    throw new Error(`${label} is not valid JSON: ${error.message}`)
  }
}

function compact(value, limit = 700) {
  const text = typeof value === 'string' ? value : JSON.stringify(value)
  return text.length > limit ? `${text.substring(0, limit)}…` : text
}

function parseImplementation(value, label) {
  const result = parseJson(value, label)
  if (!result || !['ready_for_review', 'implementation_failed'].includes(result.outcome)) {
    throw new Error(`${label} must declare ready_for_review or implementation_failed`)
  }
  if (result.outcome === 'implementation_failed') return result
  if (!result.reviewBase || result.taskStartCommit !== result.reviewBase || !result.commit) {
    throw new Error(`${label} ready_for_review requires matching reviewBase/taskStartCommit and commit`)
  }
  if (!Array.isArray(result.verification) || !Array.isArray(result.acceptanceEvidence)) {
    throw new Error(`${label} ready_for_review requires verification and acceptanceEvidence arrays`)
  }
  return result
}

function parseReview(value, axis, reviewBase, label) {
  const result = parseJson(value, label)
  if (!result || result.axis !== axis || result.reviewBase !== reviewBase || !result.head) {
    throw new Error(`${label} must preserve axis, reviewBase, and head`)
  }
  if (!['clean', 'findings', 'no_spec_available'].includes(result.status)) {
    throw new Error(`${label} has an invalid status`)
  }
  if (axis === 'standards' && result.status === 'no_spec_available') {
    throw new Error('Standards review cannot use no_spec_available')
  }
  if (!Array.isArray(result.findings)) throw new Error(`${label} findings must be an array`)
  for (const finding of result.findings) {
    if (!finding.priority || !finding.location || !finding.summary || !finding.evidence) {
      throw new Error(`${label} finding is missing priority, location, summary, or evidence`)
    }
  }
  return result
}

function hasFindings(reports) {
  return reports.some((report) => report.findings.length > 0)
}

function blockingFindings(reports) {
  return reports.flatMap((report) => report.findings.filter(
    (finding) => finding.blocking === true || finding.priority === 'P0' || finding.priority === 'P1'
  ).map((finding) => ({ ...finding, axis: report.axis })))
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`
}

function parsePreflight(value, itemId) {
  const result = parseJson(value, `preflight ${itemId}`)
  if (!result || result.error) throw new Error(`preflight failed for ${itemId}`)
  return result
}

async function runReviewRound({ item, implementation, preflightData, round }) {
  phase(`Review ${round}`)
  const fixedPoint = implementation.reviewBase
  const head = implementation.commit
  const shared = `
Work item: ${item.id} (${item.type || 'Task'})
Review round: ${round}
Fixed point: ${fixedPoint}
Expected task commit: ${head}

Preflight scope:
${JSON.stringify(preflightData, null, 2)}

Implementation summary:
${JSON.stringify(implementation, null, 2)}
`
  const prompt = (axis) => `reviewAxis: ${axis.toLowerCase()}
Use the flat review worker contract at
\`references/flat-review-worker.md\`. Run exactly the ${axis} review axis for
the supplied fixed point. Do not invoke an external review coordinator, do not
spawn or call another agent, and do not edit code, Git, Azure Boards, or any
file. Inspect the actual diff and return JSON only with axis, reviewBase, head,
status, findings, and summary.
${shared}`

  const [standardsResult, specResult] = await Promise.all([
    agent(prompt('Standards'), {
      model: 'haiku',
      effort: 'low',
      label: `review_${round}_standards_${item.id}`,
    }),
    agent(prompt('Spec'), {
      model: 'haiku',
      effort: 'low',
      label: `review_${round}_spec_${item.id}`,
    }),
  ])

  if (!standardsResult || !specResult) throw new Error(`review ${round} child returned null`)
  return [
    parseReview(standardsResult, 'standards', fixedPoint, `standards review ${round}`),
    parseReview(specResult, 'spec', fixedPoint, `spec review ${round}`),
  ]
}

async function runRepair({ item, implementation, preflightData, reports, profileId, label }) {
  phase(label)
  const profile = resolveProfile(profileId)
  const findings = reports.flatMap((report) => report.findings.map((finding) => ({
    ...finding,
    axis: report.axis,
  })))
  const result = await agent(
    `Use \`$azure-task-implement\` with \`reviewOwner=parent\` in ${label} mode for
work item ${item.id}. Preserve user-owned changes, the original reviewBase, and
the existing task delta. Repair every supplied actionable finding, rerun the
relevant verification, and amend the same task commit. Do not invoke
\`$code-review\`, spawn any child, create a second task commit, or perform
Azure Boards operations. Return JSON only using the implementation Skill's
ready_for_review or implementation_failed contract.

Original implementation:
\`\`\`json
${JSON.stringify(implementation, null, 2)}
\`\`\`

Preflight scope:
\`\`\`json
${JSON.stringify(preflightData, null, 2)}
\`\`\`

Review findings:
\`\`\`json
${JSON.stringify(findings, null, 2)}
\`\`\``,
    { model: profile.model, effort: profile.effort, label: `${label}_${item.id}` }
  )
  return parseImplementation(result, `${label} ${item.id}`)
}

// Main delivery loop. All children below are started by this parent Workflow.
const results = []
const plan = args.validatedPlan || []
const trackerConnection = args.trackerConnection

if (!trackerConnection?.organization || !trackerConnection?.project) {
  throw new Error('trackerConnection.organization and trackerConnection.project are required')
}

const boardsConnectionArgs = `--organization ${shellQuote(trackerConnection.organization)} --project ${shellQuote(trackerConnection.project)}`
let stoppedAt = null

for (let i = 0; i < plan.length; i++) {
  const item = plan[i]
  const itemId = item.id
  const itemType = item.type || 'Task'
  const plannedProfile = item.plannedProfile
  let effectiveProfile = plannedProfile
  let implementation = null
  let reviewRounds = []

  log(`[${i + 1}/${plan.length}] ${itemId}: preflight → implement → flat review/repair → closeout`)

  try {
    // === STEP 1: Preflight ===
    phase('Preflight')
    const preflightResult = await agent(
      `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Run \`implement-preflight ${boardsConnectionArgs} --id ${itemId}\` and return the JSON output unchanged. Do not perform any non-Boards work.`,
      { model: 'haiku', effort: 'low', label: `preflight_${itemId}` }
    )
    const preflightData = parsePreflight(preflightResult, itemId)

    // === STEP 2: Implement ===
    phase('Implement')
    const profile = resolveProfile(effectiveProfile)
    const implementationResult = await agent(
      `Use \`$azure-task-implement\` with \`reviewOwner=parent\` to implement work item ${itemId} in the current workspace and branch. The effective profile is fixed. Do not invoke \`$code-review\`, spawn any child, or perform Azure Boards operations. Return JSON only using the implementation Skill's ready_for_review or implementation_failed contract.

Preflight scope:
\`\`\`json
${JSON.stringify(preflightData, null, 2)}
\`\`\``,
      { model: profile.model, effort: profile.effort, label: `delivery_${plannedProfile}_${itemId}` }
    )
    implementation = parseImplementation(implementationResult, `implementation ${itemId}`)
    if (implementation.outcome === 'implementation_failed') {
      throw new Error(`implementation failed: ${compact(implementation.blocker || implementation.remainingWork || implementation)}`)
    }

    // === STEP 3: Review round 1 ===
    const firstReview = await runReviewRound({ item, implementation, preflightData, round: 1 })
    reviewRounds.push(firstReview)

    // Repair every finding before the required second review round.
    if (hasFindings(firstReview)) {
      implementation = await runRepair({
        item,
        implementation,
        preflightData,
        reports: firstReview,
        profileId: effectiveProfile,
        label: 'Repair',
      })
      if (implementation.outcome === 'implementation_failed') {
        throw new Error(`repair failed: ${compact(implementation.blocker || implementation.remainingWork || implementation)}`)
      }
    }

    // === STEP 4: Required post-fix review round ===
    const secondReview = await runReviewRound({ item, implementation, preflightData, round: 2 })
    reviewRounds.push(secondReview)
    let unresolvedBlocking = blockingFindings(secondReview)

    // === STEP 5: One stronger recovery, then one final flat review ===
    let recoveryProfile = null
    if (unresolvedBlocking.length > 0) {
      recoveryProfile = REVIEW_ESCALATION[effectiveProfile]
      if (!recoveryProfile || !PROFILES[recoveryProfile]) {
        results.push({ id: itemId, type: itemType, plannedProfile, effectiveProfile, status: 'review_escalation_unavailable', blockingFindings: unresolvedBlocking })
        stoppedAt = itemId
        break
      }
      implementation = await runRepair({
        item,
        implementation,
        preflightData,
        reports: secondReview,
        profileId: recoveryProfile,
        label: `Review recovery ${recoveryProfile}`,
      })
      if (implementation.outcome === 'implementation_failed') {
        results.push({ id: itemId, type: itemType, plannedProfile, effectiveProfile, recoveryProfile, status: 'review_escalation_failed', error: compact(implementation.blocker || implementation.remainingWork || implementation) })
        stoppedAt = itemId
        break
      }
      effectiveProfile = recoveryProfile
      const recoveryReview = await runReviewRound({ item, implementation, preflightData, round: 'recovery' })
      reviewRounds.push(recoveryReview)
      unresolvedBlocking = blockingFindings(recoveryReview)
      if (unresolvedBlocking.length > 0) {
        results.push({ id: itemId, type: itemType, plannedProfile, effectiveProfile, recoveryProfile, status: 'review_escalation_required', blockingFindings: unresolvedBlocking, reviewRounds })
        stoppedAt = itemId
        break
      }
    }

    // === STEP 6: Closeout ===
    phase('Closeout')
    const implementationSummary = JSON.stringify({ implementation, reviewRounds })
    const preflightRev = preflightData.rev || preflightData.revision || 'unknown'
    const closeoutResult = await agent(
      `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Read the current full Description with \`show ${boardsConnectionArgs} --full --id ${itemId}\`. Apply only the evidence-backed Markdown checklist changes specified by the implementation and review summary, preserving all other Description content. Write the rewritten Description to \`/tmp/description_${itemId}.md\` and a Markdown completion comment to \`/tmp/comment_${itemId}.md\`. Then run \`close-task --apply ${boardsConnectionArgs} --id ${itemId} --expected-rev ${preflightRev} --state Closed --description-file /tmp/description_${itemId}.md --comment-file /tmp/comment_${itemId}.md\`. Return the JSON output unchanged. Do not use \`--check-ac\`, and do not perform any non-Boards work.

Implementation and flat review summary:
${implementationSummary}`,
      { model: 'haiku', effort: 'low', label: `closeout_${itemId}` }
    )
    if (!closeoutResult) throw new Error('closeout child returned null')

    log(`✓ Completed ${itemId}`)
    results.push({
      id: itemId,
      type: itemType,
      plannedProfile,
      effectiveProfile,
      recoveryProfile,
      reviewBase: implementation.reviewBase,
      commit: implementation.commit,
      verification: implementation.verification,
      reviewRounds,
      status: 'completed',
      implementSummary: compact(implementation),
      closeoutSummary: compact(closeoutResult, 300),
    })
  } catch (error) {
    results.push({
      id: itemId,
      type: itemType,
      plannedProfile,
      effectiveProfile,
      status: 'delivery_failed',
      error: error.message,
      reviewRounds,
    })
    stoppedAt = itemId
    break
  }
}

const report = {
  totalItems: plan.length,
  completedItems: results.filter((result) => result.status === 'completed').length,
  stoppedAt,
  results,
  summary: `Delivered ${results.filter((result) => result.status === 'completed').length}/${plan.length} work items.${
    stoppedAt ? ` Stopped at ${stoppedAt}; later items were not dispatched.` : ' All items completed successfully.'
  }`,
}

return report
