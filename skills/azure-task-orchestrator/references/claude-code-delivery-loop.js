// Azure Task Orchestrator: Claude Code Delivery Loop
//
// This is a Workflow script template for Claude Code that implements the
// per-item preflight/implement/closeout loop after the user confirms the plan.
//
// Usage:
// 1. The parent orchestrator (in main conversation) reads the snapshot,
//    invokes the planner, validates the plan, and waits for user confirmation.
// 2. After confirmation, the parent passes the validated plan to this script
//    as input (via the Workflow call's args parameter).
// 3. This script runs sequentially: for each work item, preflight → implement
//    → closeout, one item at a time.
//
// Input (args):
// {
//   "validatedPlan": [
//     {
//       "id": "AB#123",
//       "type": "Task",
//       "title": "...",
//       "plannedProfile": "sol-medium",
//       "orderReason": "..."
//     },
//     ...
//   ],
//   "preflightResults": {
//     "AB#123": { preflight JSON from step 1 },
//     ...
//   },
//   "trackerConnection": {
//     "organization": "https://dev.azure.com/example",
//     "project": "ExampleProject",
//     "team": "Example Team"
//   },
//   "plannerReport": { full planner report object }
// }

export const meta = {
  name: 'azure-task-orchestrator-delivery',
  description: 'Deliver profiled work items sequentially: preflight → implement → closeout',
  phases: [
    { title: 'Preflight', detail: 'Read work-item scope and acceptance criteria' },
    { title: 'Implement', detail: 'Implement with exact model and reasoning effort' },
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
  'sol-xhigh': { model: 'claude-opus-5', effort: 'xhigh' },
}

// This is distinct from capacity fallback: a completed worker exposed a
// blocking post-fix review finding, so recovery gets one stronger profile.
const REVIEW_ESCALATION = {
  'terra-medium': 'sol-high',
  'terra-high': 'sol-high',
  'sol-medium': 'sol-high',
  'sol-high': 'sol-max',
}

// Resolve profile ID to model + effort
function resolveProfile(profileId) {
  const p = PROFILES[profileId]
  if (!p) {
    throw new Error(`Unknown profile ID: ${profileId}`)
  }
  return p
}

function parseDeliveryOutcome(result) {
  const value = typeof result === 'string' ? JSON.parse(result) : result
  if (!value || !['ready_for_closeout', 'review_escalation_required'].includes(value.outcome)) {
    throw new Error('Implementation result must declare outcome ready_for_closeout or review_escalation_required')
  }
  if (value.outcome === 'ready_for_closeout' && !value.commit) {
    throw new Error('ready_for_closeout requires a task commit')
  }
  if (value.outcome === 'review_escalation_required' && !Array.isArray(value.blockingFindings)) {
    throw new Error('review_escalation_required requires blockingFindings')
  }
  return value
}

// Main delivery loop
const results = []
const plan = args.validatedPlan || []
const preflightResults = args.preflightResults || {}
const trackerConnection = args.trackerConnection

if (!trackerConnection?.organization || !trackerConnection?.project) {
  throw new Error('trackerConnection.organization and trackerConnection.project are required')
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", "'\\''")}'`
}

const boardsConnectionArgs = `--organization ${shellQuote(trackerConnection.organization)} --project ${shellQuote(trackerConnection.project)}`

for (let i = 0; i < plan.length; i++) {
  const item = plan[i]
  const itemId = item.id
  const itemType = item.type || 'Task'
  const plannedProfile = item.plannedProfile
  let effectiveProfile = plannedProfile
  let profileSpec = resolveProfile(effectiveProfile)

  log(`[${i + 1}/${plan.length}] ${itemId}: preflight → implement (${plannedProfile}) → closeout`)

  // === STEP 1: Preflight ===
  phase('Preflight')

  const preflightResult = await agent(
    `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Run \`implement-preflight ${boardsConnectionArgs} --id ${itemId}\` and return the JSON output unchanged. Do not perform any non-Boards work.`,
    {
      model: 'haiku',
      effort: 'low',
      label: `preflight_${itemId}`,
    }
  )

  if (!preflightResult) {
    log(`❌ Preflight failed for ${itemId}`)
    results.push({
      id: itemId,
      plannedProfile,
      status: 'preflight_failed',
      error: 'Preflight child failed or returned null',
    })
    break // Stop sequence on preflight failure
  }

  // Parse preflight output if it's a string (JSON)
  let preflightData
  try {
    preflightData = typeof preflightResult === 'string' ? JSON.parse(preflightResult) : preflightResult
  } catch (e) {
    log(`❌ Preflight output unparseable for ${itemId}`)
    results.push({
      id: itemId,
      plannedProfile,
      status: 'preflight_parse_error',
      error: e.message,
    })
    break
  }

  log(`✓ Preflight complete for ${itemId}`)

  // === STEP 2: Implement ===
  phase('Implement')

  const implementPrompt = `Use \`$azure-task-implement\` to implement work item ${itemId} in the current workspace and branch. The preflight scope is provided below. Re-read repository authority; the planner is not a substitute for repo guidance. The effective execution profile is fixed for this worker. Do not perform Azure Boards operations.

Return JSON only. Set outcome to ready_for_closeout only after fixing actionable review findings and completing post-fix review. If that review still has a P0/P1 or other blocking correctness, security, data-loss, or verification finding, set outcome to review_escalation_required and include blockingFindings. Do not perform Azure Boards operations or closeout.

Preflight scope:
\`\`\`json
${JSON.stringify(preflightData, null, 2)}
\`\`\``

  const implementResult = await agent(implementPrompt, {
    model: profileSpec.model,
    effort: profileSpec.effort,
    label: `delivery_${plannedProfile}_${itemId}`,
  })

  if (!implementResult) {
    log(`❌ Implementation failed for ${itemId}`)
    results.push({
      id: itemId,
      plannedProfile,
      effectiveProfile: plannedProfile,
      status: 'implement_failed',
      error: 'Implement child failed or returned null',
    })
    break // Stop sequence on implement failure
  }

  let deliveryOutcome
  try {
    deliveryOutcome = parseDeliveryOutcome(implementResult)
  } catch (e) {
    results.push({ id: itemId, plannedProfile, effectiveProfile, status: 'implement_result_invalid', error: e.message })
    break
  }

  if (deliveryOutcome.outcome === 'review_escalation_required') {
    const recoveryProfile = REVIEW_ESCALATION[effectiveProfile]
    if (!recoveryProfile) {
      results.push({
        id: itemId, plannedProfile, effectiveProfile,
        status: 'review_escalation_unavailable',
        blockingFindings: deliveryOutcome.blockingFindings || [],
      })
      break
    }

    // `sol-max` is not a valid Claude Code profile. Stop explicitly rather
    // than silently substituting sol-xhigh or another weaker configuration.
    if (!recoveryProfile || !PROFILES[recoveryProfile]) {
      results.push({
        id: itemId,
        plannedProfile,
        effectiveProfile,
        recoveryProfile: recoveryProfile || null,
        status: 'review_escalation_unavailable',
        blockingFindings: deliveryOutcome.blockingFindings || [],
      })
      break
    }

    phase('Review escalation')
    const recoverySpec = resolveProfile(recoveryProfile)
    const recoveryResult = await agent(
      `Use \`$azure-task-implement\` for review recovery on work item ${itemId} in the current workspace and branch. A lower profile completed implementation but post-fix review remains blocking. Preserve the existing task delta, repair the supplied findings, rerun verification, and use \`$code-review\` again. Do not perform Azure Boards operations or closeout. Return JSON only with outcome ready_for_closeout or review_escalation_required.\n\nPreflight scope:\n\`\`\`json\n${JSON.stringify(preflightData, null, 2)}\n\`\`\`\n\nBlocking findings:\n\`\`\`json\n${JSON.stringify(deliveryOutcome.blockingFindings || [], null, 2)}\n\`\`\``,
      { model: recoverySpec.model, effort: recoverySpec.effort, label: `review_recovery_${recoveryProfile}_${itemId}` }
    )
    if (!recoveryResult) {
      results.push({ id: itemId, plannedProfile, effectiveProfile, recoveryProfile, status: 'review_escalation_failed', error: 'Recovery child failed or returned null' })
      break
    }
    try {
      deliveryOutcome = parseDeliveryOutcome(recoveryResult)
    } catch (e) {
      results.push({ id: itemId, plannedProfile, effectiveProfile, recoveryProfile, status: 'review_escalation_failed', error: e.message })
      break
    }
    effectiveProfile = recoveryProfile
    if (deliveryOutcome.outcome === 'review_escalation_required') {
      results.push({ id: itemId, plannedProfile, effectiveProfile, status: 'review_escalation_failed', blockingFindings: deliveryOutcome.blockingFindings || [] })
      break
    }
  }

  log(`✓ Implementation complete for ${itemId}`)
  const implementationSummary = JSON.stringify(deliveryOutcome)

  // === STEP 3: Closeout ===
  phase('Closeout')

  // Extract revision from preflight data (needed for stale-revision check)
  const preflightRev = preflightData.rev || preflightData.revision || 'unknown'

  const closeoutPrompt = `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Read the current full Description with \`show ${boardsConnectionArgs} --full --id ${itemId}\`. Apply only the evidence-backed Markdown checklist changes specified by the implementation summary, preserving all other Description content. Write the rewritten Description to \`/tmp/description_${itemId}.md\` and a Markdown completion comment to \`/tmp/comment_${itemId}.md\`. Then run \`close-task --apply ${boardsConnectionArgs} --id ${itemId} --expected-rev ${preflightRev} --state Closed --description-file /tmp/description_${itemId}.md --comment-file /tmp/comment_${itemId}.md\`.
Return the JSON output unchanged. Do not use \`--check-ac\`, and do not perform any non-Boards work.

Implementation delivery summary:
${implementationSummary}`

  const closeoutResult = await agent(closeoutPrompt, {
    model: 'haiku',
    effort: 'low',
    label: `closeout_${itemId}`,
  })

  if (!closeoutResult) {
    log(`❌ Closeout failed for ${itemId}`)
    results.push({
      id: itemId,
      plannedProfile,
      effectiveProfile,
      status: 'closeout_failed',
      error: 'Closeout child failed or returned null',
      implementSummary: implementationSummary.substring(0, 200),
    })
    break // Stop sequence on closeout failure
  }

  log(`✓ Closeout complete for ${itemId}`)

  results.push({
    id: itemId,
    type: itemType,
    plannedProfile,
    effectiveProfile,
    status: 'completed',
    implementSummary: implementationSummary.substring(0, 500),
    closeoutSummary: closeoutResult.substring(0, 200),
  })
}

// Return final report
const report = {
  totalItems: plan.length,
  completedItems: results.filter((r) => r.status === 'completed').length,
  stoppedAt: results.length < plan.length ? plan[results.length]?.id : null,
  results,
  summary: `Delivered ${results.filter((r) => r.status === 'completed').length}/${plan.length} work items. ${
    results.length < plan.length
      ? `Stopped at ${plan[results.length]?.id} due to ${results[results.length - 1]?.status}`
      : 'All items completed successfully.'
  }`,
}

return report
