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
  'sol-high': { model: 'opus', effort: 'high' },
  'sol-xhigh': { model: 'fable', effort: 'xhigh' },
}

// Resolve profile ID to model + effort
function resolveProfile(profileId) {
  const p = PROFILES[profileId]
  if (!p) {
    throw new Error(`Unknown profile ID: ${profileId}`)
  }
  return p
}

// Main delivery loop
const results = []
const plan = args.validatedPlan || []
const preflightResults = args.preflightResults || {}

for (let i = 0; i < plan.length; i++) {
  const item = plan[i]
  const itemId = item.id
  const itemType = item.type || 'Task'
  const plannedProfile = item.plannedProfile
  const profileSpec = resolveProfile(plannedProfile)

  log(`[${i + 1}/${plan.length}] ${itemId}: preflight → implement (${plannedProfile}) → closeout`)

  // === STEP 1: Preflight ===
  phase('Preflight')

  const preflightResult = await agent(
    `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Run \`implement-preflight --id ${itemId}\` and return the JSON output unchanged. Do not perform any non-Boards work.`,
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

Return the compact delivery summary with commit hash, changed areas, verification evidence, remaining work, and an acceptance-evidence table. Map each supplied acceptance criterion to concrete verification evidence, or state that it was not verified. Do not perform Azure Boards operations or closeout.

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

  log(`✓ Implementation complete for ${itemId}`)

  // === STEP 3: Closeout ===
  phase('Closeout')

  // Extract revision from preflight data (needed for stale-revision check)
  const preflightRev = preflightData.rev || preflightData.revision || 'unknown'

  const closeoutPrompt = `Use \`$azure-devops-boards-skill\` in its semantic \`task-boards-ops\` role. Read the current full Description with \`show --full --id ${itemId}\`. Apply only the evidence-backed Markdown checklist changes specified by the implementation summary, preserving all other Description content. Write the rewritten Description to \`/tmp/description_${itemId}.md\` and a Markdown completion comment to \`/tmp/comment_${itemId}.md\`. Then run \`close-task --apply --id ${itemId} --expected-rev ${preflightRev} --state Closed --description-file /tmp/description_${itemId}.md --comment-file /tmp/comment_${itemId}.md\`.
Return the JSON output unchanged. Do not use \`--check-ac\`, and do not perform any non-Boards work.

Implementation delivery summary:
${implementResult}`

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
      effectiveProfile: plannedProfile,
      status: 'closeout_failed',
      error: 'Closeout child failed or returned null',
      implementSummary: implementResult.substring(0, 200),
    })
    break // Stop sequence on closeout failure
  }

  log(`✓ Closeout complete for ${itemId}`)

  results.push({
    id: itemId,
    type: itemType,
    plannedProfile,
    effectiveProfile: plannedProfile,
    status: 'completed',
    implementSummary: implementResult.substring(0, 500),
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
