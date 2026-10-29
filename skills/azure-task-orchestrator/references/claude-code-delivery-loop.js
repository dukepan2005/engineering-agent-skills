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
//     "plannedCandidate": "opus-medium",
//     "diagnosticCandidate": "opus-max",
//     "reviewCandidate": "haiku-low",
//     "reviewEvidence": "Bounded contract with focused negative-path tests",
//     "plannerEvidence": "...",
//     "orderReason": "..."
//   }],
//   "additionalCandidates": {
//     "additional-1": {
//       "model": "<current-host model identifier>",
//       "reasoning_effort": "<supported effort or unset>"
//     }
//   },
//   "trackerConnection": {
//     "organization": "https://dev.azure.com/example",
//     "project": "ExampleProject",
//     "team": "Example Team"
//   }
// }

export const meta = {
  name: 'azure-task-orchestrator-delivery',
  description: 'Deliver profiled work items with parent-owned flat implementation and review workers',
  phases: [
    { title: 'Preflight', detail: 'Read work-item scope and acceptance criteria' },
    { title: 'Implement', detail: 'Implement with exact model and reasoning effort' },
    { title: 'Review round 1', detail: 'Run Standards and Spec review workers in parallel' },
    { title: 'Repair after review round 1', detail: 'Repair findings in a separate commit' },
    { title: 'Review round 2', detail: 'Review the repaired delta at the approved implementation effort' },
    { title: 'Final repair at higher effort', detail: 'After round 2 findings, raise implementation effort one supported level' },
    { title: 'Review round 3', detail: 'Review the final repaired delta; unresolved findings require human direction' },
    { title: 'Closeout', detail: 'Close item and update checklist with evidence' },
  ],
}

// Execution profile registry: profile ID → {model, effort}
const PROFILES = {
  'sonnet-medium': { model: 'sonnet', effort: 'medium' },
  'sonnet-high': { model: 'sonnet', effort: 'high' },
  'sonnet-xhigh': { model: 'sonnet', effort: 'xhigh' },
  'opus-medium': { model: 'opus', effort: 'medium' },
  'opus-high': { model: 'opus', effort: 'high' },
  'opus-max': { model: 'opus', effort: 'max' },
  'opus-xhigh': { model: 'opus', effort: 'xhigh' },
}

const NEXT_IMPLEMENTATION_CANDIDATE = {
  'sonnet-medium': 'sonnet-high',
  'sonnet-high': 'sonnet-xhigh',
  'opus-medium': 'opus-high',
  'opus-high': 'opus-xhigh',
  'opus-xhigh': 'opus-max',
}

const DIAGNOSTIC_UPGRADES = {
  'sonnet-medium': 'opus-max',
  'sonnet-high': 'opus-max',
  'sonnet-xhigh': 'opus-max',
  'opus-medium': 'opus-max',
  'opus-high': 'opus-max',
  'opus-xhigh': 'opus-max',
}

const REVIEW_PROFILES = {
  ...PROFILES,
  'haiku-low': { model: 'haiku', effort: 'low' },
}

function resolveReviewCandidate(candidateId) {
  if (!Object.hasOwn(REVIEW_PROFILES, candidateId)) {
    throw new Error(`Unknown review candidate ID: ${candidateId}`)
  }
  return REVIEW_PROFILES[candidateId]
}

function describeReviewCandidate(candidateId) {
  const candidate = resolveReviewCandidate(candidateId)
  return { candidateId, model: candidate.model, reasoning_effort: candidate.effort }
}

function resolveCandidate(candidateId) {
  const profile = PROFILES[candidateId]
  if (profile) return profile

  const candidate = args.additionalCandidates?.[candidateId]
  if (!candidate || typeof candidate.model !== 'string' || !candidate.model.trim()) {
    throw new Error(`Unknown execution candidate ID: ${candidateId}`)
  }
  if (candidate.reasoning_effort !== 'unset'
    && (typeof candidate.reasoning_effort !== 'string' || !candidate.reasoning_effort.trim())) {
    throw new Error(`Candidate ${candidateId} must specify reasoning_effort or unset`)
  }
  return {
    model: candidate.model,
    effort: candidate.reasoning_effort === 'unset' ? undefined : candidate.reasoning_effort,
  }
}

function agentOptions(candidate, label) {
  return candidate.effort === undefined
    ? { model: candidate.model, label }
    : { model: candidate.model, effort: candidate.effort, label }
}

function describeCandidate(candidateId) {
  const candidate = resolveCandidate(candidateId)
  return {
    candidateId,
    model: candidate.model,
    reasoning_effort: candidate.effort ?? 'unset',
  }
}

function nextImplementationCandidate(candidateId) {
  return NEXT_IMPLEMENTATION_CANDIDATE[candidateId] || null
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
  if (result.outcome === 'implementation_failed') {
    const recovery = result.recovery
    if (!result.reviewBase || result.taskStartCommit !== result.reviewBase
      || !recovery || !['retry', 'blocked'].includes(recovery.disposition)
      || !recovery.reason || !recovery.evidence || !recovery.nextAction) {
      throw new Error(`${label} failure requires fixed point and an evidence-backed recovery disposition`)
    }
    const diagnostics = result.diagnostics
    if (!diagnostics || !Number.isFinite(diagnostics.noProgressMinutes) || diagnostics.noProgressMinutes < 0
      || !Number.isInteger(diagnostics.rejectedFixes) || diagnostics.rejectedFixes < 0) {
      throw new Error(`${label} failure requires nonnegative diagnostic checkpoint metrics`)
    }
    if (recovery.disposition === 'retry' && recovery.deniedAction
      && (!recovery.safeAlternative || recovery.safeAlternative === recovery.deniedAction
        || recovery.nextAction === recovery.deniedAction)) {
      throw new Error(`${label} denied action requires a different permitted alternative`)
    }
    return result
  }
  if (!result.reviewBase || result.taskStartCommit !== result.reviewBase || !result.commit) {
    throw new Error(`${label} ready_for_review requires matching reviewBase/taskStartCommit and commit`)
  }
  if (!Array.isArray(result.verification) || !Array.isArray(result.acceptanceEvidence)) {
    throw new Error(`${label} ready_for_review requires verification and acceptanceEvidence arrays`)
  }
  return result
}

function parseReview(value, axis, reviewBase, head, expectedParent, label) {
  const result = parseJson(value, label)
  if (!result || result.axis !== axis || result.reviewBase !== reviewBase
    || result.head !== head || result.parent !== expectedParent) {
    throw new Error(`${label} must preserve axis, reviewBase, head, and parent`)
  }
  if (!['clean', 'findings', 'no_spec_available'].includes(result.status)) {
    throw new Error(`${label} has an invalid status`)
  }
  if (axis === 'standards' && result.status === 'no_spec_available') {
    throw new Error('Standards review cannot use no_spec_available')
  }
  if (!Array.isArray(result.findings)) throw new Error(`${label} findings must be an array`)
  if ((result.status === 'findings') !== (result.findings.length > 0)) {
    throw new Error(`${label} status must agree with its findings array`)
  }
  for (const finding of result.findings) {
    if (!['P0', 'P1', 'P2', 'P3'].includes(finding?.priority)
      || !finding.location || !finding.summary || !finding.evidence) {
      throw new Error(`${label} finding requires a P0–P3 priority, location, summary, and evidence`)
    }
  }
  return result
}

function hasFindings(reports) {
  return reports.some((report) => report.findings.length > 0)
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`
}

function parsePreflight(value, itemId) {
  const result = parseJson(value, `preflight ${itemId}`)
  if (!result || result.error) throw new Error(`preflight failed for ${itemId}`)
  return result
}

function parseCloseout(value, itemId) {
  const result = parseJson(value, `closeout ${itemId}`)
  const expectedId = Number(String(itemId).replace(/^AB#/, ''))
  if (!result || result.mode !== 'applied' || result.id !== expectedId
    || result.fields?.['System.State'] !== 'Closed') {
    throw new Error(`closeout ${itemId} must apply Closed state to work item ${expectedId}`)
  }
  return result
}

async function runReviewRound({ item, implementation, preflightData, round, expectedParent, previousReports }) {
  phase(`Review ${round}`)
  const fixedPoint = implementation.reviewBase
  const head = implementation.commit
  const shared = `
Work item: ${item.id} (${item.type || 'Task'})
Review round: ${round}
Fixed point: ${fixedPoint}
Expected task commit: ${head}
Expected head parent: ${expectedParent}

Preflight scope:
${JSON.stringify(preflightData, null, 2)}

Implementation summary:
${JSON.stringify(implementation, null, 2)}
${round > 1 ? `
All preceding review reports (including original findings):
${JSON.stringify(previousReports, null, 2)}
` : ''}
`
  const prompt = (axis) => `reviewAxis: ${axis.toLowerCase()}
Use the flat review worker contract at
\`references/flat-review-worker.md\`. Run exactly the ${axis} review axis for
the supplied fixed point. Do not invoke an external review coordinator, do not
spawn or call another agent, and do not edit code, Git, Azure Boards, or any
file. Inspect the actual diff and return JSON only with axis, reviewBase, head,
parent, status, findings, and summary.
${shared}`

  const reviewCandidate = resolveReviewCandidate(item.reviewCandidate)
  const [standardsResult, specResult] = await Promise.all([
    agent(prompt('Standards'), agentOptions(reviewCandidate, `review_${round}_standards_${item.id}`)),
    agent(prompt('Spec'), agentOptions(reviewCandidate, `review_${round}_spec_${item.id}`)),
  ])

  if (!standardsResult || !specResult) throw new Error(`review ${round} child returned null`)
  return [
    parseReview(standardsResult, 'standards', fixedPoint, head, expectedParent, `standards review ${round}`),
    parseReview(specResult, 'spec', fixedPoint, head, expectedParent, `spec review ${round}`),
  ]
}

async function runRepair({ item, implementation, preflightData, reports, candidateId, label, phaseLabel = label }) {
  phase(phaseLabel)
  const candidate = resolveCandidate(candidateId)
  const candidateMapping = describeCandidate(candidateId)
  const result = await agent(
    `Use \`$azure-task-implement\` with \`reviewOwner=parent\` in ${label} mode for
work item ${item.id}. Preserve user-owned changes, the original reviewBase, and
the existing task delta. Repair every supplied actionable finding, rerun the
relevant verification, and create one separate repair commit on top of the
supplied implementation commit. Keep that commit intact. Do not invoke
\`$code-review\`, spawn any child, amend a commit, or perform Azure Boards
operations. Return JSON only using the implementation Skill's
ready_for_review or implementation_failed contract.

Effective candidate: ${candidateId}
Exact model/effort mapping: ${JSON.stringify(candidateMapping)}

Original implementation:
\`\`\`json
${JSON.stringify(implementation, null, 2)}
\`\`\`

Preflight scope:
\`\`\`json
${JSON.stringify(preflightData, null, 2)}
\`\`\`

All preceding review reports:
\`\`\`json
${JSON.stringify(reports, null, 2)}
\`\`\``,
    agentOptions(candidate, `${label}_${item.id}`)
  )
  return parseImplementation(result, `${label} ${item.id}`)
}

// Main delivery loop. All children below are started by this parent Workflow.
const results = []
const plan = args.validatedPlan || []
const trackerConnection = args.trackerConnection

if (!Array.isArray(plan)) throw new Error('validatedPlan must be an array')
for (const item of plan) {
  if (!item?.plannedCandidate) throw new Error(`plannedCandidate is required for ${item?.id || 'a work item'}`)
  if (!item?.plannerEvidence || !item?.orderReason) {
    throw new Error(`plannerEvidence and orderReason are required for ${item.id || 'a work item'}`)
  }
  resolveCandidate(item.plannedCandidate)
  if (item.diagnosticCandidate != null) {
    resolveCandidate(item.diagnosticCandidate)
    const expected = DIAGNOSTIC_UPGRADES[item.plannedCandidate]
    const dynamic = item.plannedCandidate.startsWith('additional-') || item.diagnosticCandidate.startsWith('additional-')
    if (item.diagnosticCandidate === item.plannedCandidate || (!dynamic && item.diagnosticCandidate !== expected)) {
      throw new Error(`Unsupported diagnostic escalation for ${item.id}`)
    }
  }
  resolveReviewCandidate(item.reviewCandidate)
  if (!item.reviewCandidate || typeof item.reviewEvidence !== 'string' || !item.reviewEvidence.trim()) {
    throw new Error(`Built-in reviewCandidate and reviewEvidence are required for ${item.id}`)
  }
}

if (!trackerConnection?.organization || !trackerConnection?.project) {
  throw new Error('trackerConnection.organization and trackerConnection.project are required')
}

const boardsConnectionArgs = `--organization ${shellQuote(trackerConnection.organization)} --project ${shellQuote(trackerConnection.project)}`
let stoppedAt = null

for (let i = 0; i < plan.length; i++) {
  const item = plan[i]
  const itemId = item.id
  const itemType = item.type || 'Task'
  const plannedCandidate = item.plannedCandidate
  const reviewCandidate = item.reviewCandidate
  const reviewEvidence = item.reviewEvidence
  let effectiveCandidate = plannedCandidate
  let implementation = null
  let implementationCommit = null
  const repairCommits = []
  let effortEscalation = null
  let reviewRounds = []
  const recoveryHistory = []

  log(`[${i + 1}/${plan.length}] ${itemId}: preflight → implement → flat review/repair → closeout`)

  try {
    // === STEP 1: Preflight ===
    phase('Preflight')
    const preflightResult = await agent(
      `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Run \`implement-preflight ${boardsConnectionArgs} --id ${itemId}\` and return the JSON output unchanged. Do not perform any non-Boards work.`,
      { model: 'haiku', effort: 'low', label: `preflight_${itemId}` }
    )
    const preflightData = parsePreflight(preflightResult, itemId)

    async function recoverCurrent(result, stage, reports = []) {
      const fixedPoint = result.reviewBase
      for (let attempt = 1; result.outcome === 'implementation_failed'; attempt++) {
        const { recovery, diagnostics } = result
        if (recovery.disposition === 'blocked') {
          throw new Error(`external blocker: ${compact(recovery)}`)
        }
        if (attempt > 3) throw new Error(`recovery budget exhausted: ${compact(recovery)}`)
        const stalled = diagnostics.noProgressMinutes >= 20 || diagnostics.rejectedFixes >= 2 || attempt >= 2
        const previousCandidate = effectiveCandidate
        if (stalled && item.diagnosticCandidate && effectiveCandidate !== item.diagnosticCandidate) {
          effectiveCandidate = item.diagnosticCandidate
          log(`[${itemId}] diagnostic escalation: ${previousCandidate} → ${effectiveCandidate}`)
        } else if (stalled && !item.diagnosticCandidate && DIAGNOSTIC_UPGRADES[effectiveCandidate]) {
          throw new Error(`approved diagnostic candidate required: ${compact(recovery)}`)
        }
        recoveryHistory.push({ stage, attempt, fromCandidate: previousCandidate, candidateId: effectiveCandidate,
          mapping: describeCandidate(effectiveCandidate), recovery, diagnostics })
        phase('Diagnose and recover')
        const resumed = await agent(
          `Use \`$azure-task-implement\` with \`reviewOwner=parent\` to diagnose and recover the current ${stage} of ${itemId}. Continue only this authorized work item. Preserve the workspace, reviewBase/taskStartCommit ${fixedPoint}, existing commits and acceptance scope. Build or reuse the exact red-capable loop before a causal fix; use permitted local alternatives for recoverable tool/environment failures. Do not repeat or indirectly bypass the denied action. A denied action is not permission to retry it. Report an external blocker only when evidence shows no permitted local recovery remains. Do not invoke \`$code-review\`, spawn a child, or perform Boards operations.
Checkpoint within 10 minutes (finish an already running bounded test first); hand back earlier after two rejected candidate fixes or a concrete external blocker. Return implementation_failed with recovery/diagnostics for an incomplete checkpoint; it requests continued recovery, not review. On success, rerun affected verification after cleanup, preserve/create the task-only unpushed commit (a separate repair commit for review repairs), and return ready_for_review. No review or closeout before verification and commit are complete.
Effective candidate: ${effectiveCandidate}
Exact mapping: ${JSON.stringify(describeCandidate(effectiveCandidate))}
Recovery attempt: ${attempt}/3. Measure noProgressMinutes since the last new causal evidence and rejectedFixes since the latest candidate escalation; include the evidence/timestamps. Keep this candidate fixed during the worker turn. Hand off the current loop, rejected hypotheses, source/build identity, running commands and remaining checks; do not restart a settled experiment.
Preflight scope: ${JSON.stringify(preflightData)}
Previous checkpoint: ${JSON.stringify(result)}
Preceding review reports: ${JSON.stringify(reports)}`,
          agentOptions(resolveCandidate(effectiveCandidate), `diagnose_${stage}_${attempt}_${itemId}`)
        )
        result = parseImplementation(resumed, `recovery ${itemId}`)
        recoveryHistory.at(-1).outcome = result.outcome
        recoveryHistory.at(-1).commit = result.commit
        if (result.reviewBase !== fixedPoint) throw new Error('recovery must preserve reviewBase')
      }
      return result
    }

    // === STEP 2: Implement ===
    phase('Implement')
    const candidate = resolveCandidate(effectiveCandidate)
    const candidateMapping = describeCandidate(effectiveCandidate)
    const implementationResult = await agent(
      `Use \`$azure-task-implement\` with \`reviewOwner=parent\` to implement work item ${itemId} in the current workspace and branch. The effective model/effort candidate is fixed. Do not invoke \`$code-review\`, spawn any child, or perform Azure Boards operations. Return JSON only using the implementation Skill's ready_for_review or implementation_failed contract. For incomplete work, include evidence-backed recovery and diagnostics. Checkpoint within 10 minutes of diagnosis (finish an already running bounded test first), or earlier after two rejected fixes; do not wait indefinitely for a result before returning control to the parent.

Planned candidate: ${plannedCandidate}
Effective candidate: ${effectiveCandidate}
Exact model/effort mapping: ${JSON.stringify(candidateMapping)}
Order reason: ${item.orderReason}
Planner evidence: ${item.plannerEvidence}

Preflight scope:
\`\`\`json
${JSON.stringify(preflightData, null, 2)}
\`\`\``,
      agentOptions(candidate, `delivery_${plannedCandidate}_${itemId}`)
    )
    implementation = parseImplementation(implementationResult, `implementation ${itemId}`)
    implementation = await recoverCurrent(implementation, 'implementation')
    implementationCommit = implementation.commit

    // === STEP 3: Review and repair, with one effort escalation before round 3 ===
    let expectedParent = implementation.reviewBase
    let reviewActionRequired = null
    for (let round = 1; round <= 3; round++) {
      const reports = await runReviewRound({
        item,
        implementation,
        preflightData,
        round,
        expectedParent,
        previousReports: reviewRounds.flat(),
      })
      reviewRounds.push(reports)
      if (!hasFindings(reports)) break

      const remainingFindings = reports.flatMap((report) =>
        report.findings.map((finding) => ({ ...finding, axis: report.axis }))
      )
      if (round === 3) {
        reviewActionRequired = {
          reason: 'findings remain after review round 3',
          remainingFindings,
        }
        break
      }

      if (round === 2) {
        const higherCandidate = nextImplementationCandidate(effectiveCandidate)
        if (!higherCandidate) {
          reviewActionRequired = {
            reason: `no documented higher supported implementation effort after review round 2 for ${effectiveCandidate}`,
            remainingFindings,
          }
          break
        }
        const previousMapping = describeCandidate(effectiveCandidate)
        effectiveCandidate = higherCandidate
        effortEscalation = {
          afterReviewRound: 2,
          from: previousMapping,
          to: describeCandidate(effectiveCandidate),
        }
        log(`[${itemId}] review round 2 still has findings; raising implementation effort to ${effectiveCandidate} for the final repair`)
      }

      const priorTaskCommit = implementation.commit
      let repaired = await runRepair({
        item,
        implementation,
        preflightData,
        reports: reviewRounds.flat(),
        candidateId: effectiveCandidate,
        label: round === 2 ? 'Final_repair_escalated' : `Repair_round_${round}`,
        phaseLabel: round === 2 ? 'Final repair at higher effort' : 'Repair after review round 1',
      })
      repaired = await recoverCurrent(repaired, 'repair', reviewRounds.flat())
      if (repaired.reviewBase !== implementation.reviewBase || repaired.commit === implementation.commit) {
        throw new Error('repair must preserve reviewBase and return a new commit')
      }
      repairCommits.push(repaired.commit)
      implementation = repaired
      expectedParent = priorTaskCommit
    }

    if (reviewActionRequired) {
      results.push({
        id: itemId,
        type: itemType,
        plannedCandidate,
        effectiveCandidate,
        reviewCandidate,
        reviewEvidence,
        implementationCommit,
        repairCommit: repairCommits.at(-1) || null,
        repairCommits,
        effortEscalation,
        recoveryHistory,
        status: 'review_action_required',
        ...reviewActionRequired,
        reviewRounds,
      })
      stoppedAt = itemId
      break
    }

    // === Closeout after the first clean round or any later clean round ===
    phase('Closeout')
    const repairCommit = repairCommits.at(-1) || null
    const implementationSummary = JSON.stringify({ implementationCommit, repairCommit, repairCommits, effortEscalation, implementation, reviewRounds, reviewCandidate, reviewEvidence, reviewMapping: describeReviewCandidate(reviewCandidate) })
    const preflightRev = preflightData.rev || preflightData.revision || 'unknown'
    const closeoutResult = parseCloseout(await agent(
      `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Read the current full work item with \`show ${boardsConnectionArgs} --full --id ${itemId}\`. Read Acceptance Criteria from \`Microsoft.VSTS.Common.AcceptanceCriteria\`, separately from Description. Apply only evidence-backed Markdown checklist changes specified by the implementation and review summary, preserving all other Acceptance Criteria and Description content. Write the resulting Acceptance Criteria to \`/tmp/acceptance_criteria_${itemId}.md\` and a Markdown completion comment to \`/tmp/comment_${itemId}.md\`. Then run \`close-task --apply ${boardsConnectionArgs} --id ${itemId} --expected-rev ${preflightRev} --state Closed --acceptance-criteria-file /tmp/acceptance_criteria_${itemId}.md --comment-file /tmp/comment_${itemId}.md\`. Return the JSON output unchanged. Do not use \`--check-ac\`, and do not perform any non-Boards work.

Implementation and flat review summary:
${implementationSummary}`,
      { model: 'haiku', effort: 'low', label: `closeout_${itemId}` }
    ), itemId)

    log(`✓ Completed ${itemId}`)
    results.push({
      id: itemId,
      type: itemType,
      plannedCandidate,
      effectiveCandidate,
      reviewCandidate,
      reviewEvidence,
      reviewBase: implementation.reviewBase,
      implementationCommit,
      repairCommit,
      repairCommits,
      effortEscalation,
      recoveryHistory,
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
      plannedCandidate,
      effectiveCandidate,
      reviewCandidate,
      reviewEvidence,
      implementationCommit,
      repairCommit: repairCommits.at(-1) || null,
      repairCommits,
      effortEscalation,
      recoveryHistory,
      status: 'delivery_failed',
      error: error.message,
      reviewRounds,
    })
    stoppedAt = itemId
    break
  }
}

const reportedResults = results.map((result) => ({
  ...result,
  reviewMapping: describeReviewCandidate(result.reviewCandidate),
  plannedMapping: describeCandidate(result.plannedCandidate),
  effectiveMapping: describeCandidate(result.effectiveCandidate),
}))

const report = {
  totalItems: plan.length,
  completedItems: reportedResults.filter((result) => result.status === 'completed').length,
  stoppedAt,
  results: reportedResults,
  summary: `Delivered ${reportedResults.filter((result) => result.status === 'completed').length}/${plan.length} work items.${
    stoppedAt ? ` Stopped at ${stoppedAt}; later items were not dispatched.` : ' All items completed successfully.'
  }`,
}

return report
