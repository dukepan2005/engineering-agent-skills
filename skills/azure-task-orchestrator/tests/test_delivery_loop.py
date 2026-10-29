"""Execute the delivery template with local workers; no host or Boards calls."""
import subprocess
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "references" / "claude-code-delivery-loop.js"
HARNESS = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const source = fs.readFileSync(process.argv[1], 'utf8').replace('export const meta', 'const meta');
const execute = new AsyncFunction('args', 'agent', 'phase', 'log', source);
const finding = {priority:'P2', location:'file:1', summary:'repair this fault', evidence:'original proof'};
const applied = {mode:'applied', id:123, rev:2, fields:{'System.State':'Closed'}, commentId:1};
function failed({disposition='retry', noProgressMinutes=0, rejectedFixes=0, ...recovery} = {}) {
  return {outcome:'implementation_failed', reviewBase:'base', taskStartCommit:'base', commit:null,
    recovery:{disposition,reason:'preview missing',evidence:'focused test red',nextAction:'diagnose the missing destination',...recovery},
    diagnostics:{noProgressMinutes,rejectedFixes}};
}
async function run({repair=false, findingsRounds=null, transformReview=r=>r, closeout=applied, itemId='AB#123', plannedCandidate='opus-high', diagnosticCandidate=plannedCandidate==='opus-max'?null:'opus-max', implementationResults=[], recoveryResults=[], repairResults=[], secondItem=false} = {}) {
  const calls = [], firstReports = [];
  const reviewFindings = findingsRounds || (repair ? [1] : []);
  let repairCount = 0;
  const item = {id:itemId, type:'Task', plannedCandidate, diagnosticCandidate, reviewCandidate:'sonnet-medium',
    reviewEvidence:'review rationale', plannerEvidence:'implementation rationale', orderReason:'stable'};
  const agent = async (prompt, options) => {
    calls.push({prompt, ...options});
    if (options.label.startsWith('preflight_')) return {rev:1};
    if (options.label.startsWith('closeout_')) return closeout;
    if (options.label.startsWith('delivery_') && implementationResults.length) return implementationResults.shift();
    if (options.label.startsWith('diagnose_') && recoveryResults.length) return recoveryResults.shift();
    if (options.label.startsWith('Repair_') && repairResults.length) return repairResults.shift();
    if (options.label.startsWith('review_')) {
      const round = Number(options.label.split('_')[1]);
      const axis = options.label.includes('_standards_') ? 'standards' : 'spec';
      const findings = reviewFindings.includes(round) ? [finding] : [];
      const head = round === 1 ? 'impl' : `repair${round - 1}`;
      const parent = round === 1 ? 'base' : round === 2 ? 'impl' : `repair${round - 2}`;
      const report = {axis, reviewBase:'base', head, parent,
        status:findings.length?'findings':'clean', findings, summary:`${axis} original report context`};
      if (round === 1) firstReports.push(report);
      return transformReview(report, round);
    }
    const isRepair = options.label.startsWith('Repair_') || options.label.startsWith('Final_repair_');
    const commit = isRepair ? `repair${++repairCount}` : 'impl';
    return {outcome:'ready_for_review', reviewBase:'base', taskStartCommit:'base',
      commit, verification:[], acceptanceEvidence:[]};
  };
  const report = await execute({validatedPlan:secondItem?[item,{...item,id:'AB#124'}]:[item],trackerConnection:{organization:'org',project:'project'}},agent,()=>{},()=>{});
  return {report,calls,firstReports};
}
function assertStopped({report,calls}, stage) {
  assert.equal(report.completedItems, 0);
  assert.equal(report.results[0].status, 'delivery_failed');
  assert.equal(report.stoppedAt, 'AB#123');
  if (stage === 'review') assert.ok(!calls.some(c=>c.label.startsWith('closeout_')));
}
"""


class DeliveryLoopTests(unittest.TestCase):
    def run_probe(self, probe):
        program = HARNESS + "\n(async () => {\n" + probe + "\n})().catch(e=>{console.error(e);process.exitCode=1});"
        result = subprocess.run(["node", "-e", program, str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_local_failure_recovers_before_review(self):
        self.run_probe(r"""
const {report,calls} = await run({implementationResults:[failed()]});
assert.equal(report.completedItems,1);
const diagnosis = calls.findIndex(c=>c.label.startsWith('diagnose_'));
const review = calls.findIndex(c=>c.label.startsWith('review_'));
assert.ok(diagnosis > 0 && review > diagnosis);
assert.equal(calls[diagnosis].effort,'high');
assert.ok(calls[diagnosis].prompt.includes('focused test red'));
assert.equal(report.results[0].recoveryHistory.length,1);
assert.equal(report.results[0].recoveryHistory[0].outcome,'ready_for_review');
""")

    def test_stalled_or_rejected_fixes_use_approved_diagnostic_candidate(self):
        self.run_probe(r"""
for (const metrics of [{noProgressMinutes:20},{rejectedFixes:2}]) {
  const {report,calls} = await run({implementationResults:[failed(metrics)]});
  assert.equal(report.completedItems,1);
  const diagnosis = calls.find(c=>c.label.startsWith('diagnose_'));
  assert.equal(diagnosis.model,'opus'); assert.equal(diagnosis.effort,'max');
  assert.equal(report.results[0].effectiveCandidate,'opus-max');
  assert.ok(calls.filter(c=>c.label.startsWith('review_')).every(c=>c.effort==='medium'));
}
const repeated = await run({implementationResults:[failed()],recoveryResults:[failed()]});
assert.equal(repeated.report.completedItems,1);
assert.deepEqual(repeated.calls.filter(c=>c.label.startsWith('diagnose_')).map(c=>c.effort),['high','max']);
const below = await run({implementationResults:[failed({noProgressMinutes:19.9,rejectedFixes:1})]});
assert.equal(below.calls.find(c=>c.label.startsWith('diagnose_')).effort,'high');
const ceiling = await run({plannedCandidate:'opus-max',implementationResults:[failed({noProgressMinutes:20})]});
assert.equal(ceiling.report.completedItems,1);
assert.equal(ceiling.calls.find(c=>c.label.startsWith('diagnose_')).effort,'max');
""")

    def test_blocked_failure_and_denied_action_without_alternative_do_not_retry(self):
        self.run_probe(r"""
for (const failure of [failed({disposition:'blocked',reason:'credentials missing'}),
  failed({deniedAction:'delegate fixture claimed as actual taps'}),
  failed({deniedAction:'rejected command',safeAlternative:'rejected command',nextAction:'rejected command'})]) {
  const result = await run({implementationResults:[failure],secondItem:true});
  assertStopped(result,'implementation');
  assert.ok(!result.calls.some(c=>c.label.startsWith('diagnose_') || c.label.startsWith('review_') || c.label.startsWith('closeout_')));
  assert.ok(!result.calls.some(c=>c.label.includes('AB#124')));
}
""")

    def test_denial_with_permitted_alternative_recovers(self):
        self.run_probe(r"""
const alternative = 'Use actual Simulator pointer clicks and assert resulting pages';
const {report,calls} = await run({implementationResults:[failed({deniedAction:'delegate fixture claimed as actual taps',safeAlternative:alternative,nextAction:alternative})]});
assert.equal(report.completedItems,1);
const prompt = calls.find(c=>c.label.startsWith('diagnose_')).prompt;
assert.ok(prompt.includes(alternative));
assert.ok(prompt.includes('Do not repeat or indirectly bypass the denied action'));
""")

    def test_recovery_is_bounded_and_requires_an_approved_upgrade(self):
        self.run_probe(r"""
const exhausted = await run({implementationResults:[failed()],recoveryResults:[failed(),failed(),failed()],secondItem:true});
assertStopped(exhausted,'implementation');
assert.equal(exhausted.calls.filter(c=>c.label.startsWith('diagnose_')).length,3);
assert.ok(!exhausted.calls.some(c=>c.label.startsWith('review_') || c.label.includes('AB#124')));
const unapproved = await run({diagnosticCandidate:null,implementationResults:[failed({noProgressMinutes:20})]});
assertStopped(unapproved,'implementation');
assert.ok(!unapproved.calls.some(c=>c.label.startsWith('diagnose_')));
assert.ok(unapproved.report.results[0].error.includes('approved diagnostic candidate'));
""")

    def test_recovery_rejects_malformed_metrics_and_preserves_fixed_point(self):
        self.run_probe(r"""
for (const failure of [{outcome:'implementation_failed'},failed({noProgressMinutes:-1}),failed({rejectedFixes:'two'})]) {
  const result = await run({implementationResults:[failure]});
  assertStopped(result,'implementation');
  assert.ok(!result.calls.some(c=>c.label.startsWith('diagnose_')));
}
const changed = {outcome:'ready_for_review',reviewBase:'wrong',taskStartCommit:'wrong',commit:'impl',verification:[],acceptanceEvidence:[]};
const result = await run({implementationResults:[failed()],recoveryResults:[changed]});
assertStopped(result,'implementation');
assert.ok(!result.calls.some(c=>c.label.startsWith('review_')));
""")

    def test_review_repair_failure_recovers_before_next_review(self):
        self.run_probe(r"""
const brokenRepair = {...failed(),commit:'impl'};
const repaired = {outcome:'ready_for_review',reviewBase:'base',taskStartCommit:'base',commit:'repair1',verification:[],acceptanceEvidence:[]};
const {report,calls,firstReports} = await run({repair:true,repairResults:[brokenRepair],recoveryResults:[repaired]});
assert.equal(report.completedItems,1);
const recovery = calls.find(c=>c.label.startsWith('diagnose_repair_'));
assert.ok(recovery.prompt.includes(JSON.stringify(firstReports)));
assert.ok(calls.findIndex(c=>c.label.startsWith('diagnose_repair_')) < calls.findIndex(c=>c.label.startsWith('review_2_')));
assert.equal(report.results[0].recoveryHistory[0].stage,'repair');
""")

    def test_malformed_review_reports_stop_before_closeout(self):
        self.run_probe(r"""
for (const change of [
  {status:'findings',findings:[]},
  {status:'clean',findings:[finding]},
  {status:'no_spec_available',findings:[finding]},
  {status:'findings',findings:[{...finding,priority:'P9'}]},
  {status:'findings',findings:[null]},
]) {
  const result = await run({transformReview:r=>({...r,...change})});
  assertStopped(result, 'review');
  assert.ok(!result.calls.some(c=>c.label.startsWith('Repair_')));
}
assertStopped(await run({repair:true, transformReview:(r,round)=>round===2?{...r,status:'findings',findings:[]}:r}), 'review');
""")

    def test_closeout_requires_applied_result_for_expected_item(self):
        self.run_probe(r"""
for (const closeout of [null, {}, {closed:true}, {mode:'validated',id:123},
  {error:'revision mismatch'}, 'Boards update failed', '{invalid JSON',
  {...applied,id:999}, {mode:'applied',id:123}, {...applied,fields:{}},
  {...applied,fields:{'System.State':'Active'}},
  {...applied,fields:null}, JSON.stringify({mode:'validated',id:123})]) {
  assertStopped(await run({closeout}), 'closeout');
}
for (const closeout of [applied, JSON.stringify(applied)]) {
  for (const itemId of ['AB#123',123]) {
    const {report,calls} = await run({closeout,itemId});
    assert.equal(report.completedItems,1);
    assert.equal(report.results[0].status,'completed');
    assert.ok(!calls.some(c=>c.label.startsWith('Repair_')));
  }
}
const noSpec = await run({transformReview:r=>r.axis==='spec'?{...r,status:'no_spec_available'}:r});
assert.equal(noSpec.report.completedItems,1);
""")

    def test_repair_and_second_review_receive_complete_first_reports(self):
        self.run_probe(r"""
const {report,calls,firstReports} = await run({repair:true});
assert.equal(report.completedItems,1);
const fullReports = JSON.stringify(firstReports,null,2);
const repairCall = calls.find(c=>c.label.startsWith('Repair_'));
assert.ok(repairCall.prompt.includes(fullReports), 'repair must receive both complete reports');
const reviewers = calls.filter(c=>c.label.startsWith('review_2_'));
assert.equal(reviewers.length,2);
for (const reviewer of reviewers) {
  assert.ok(reviewer.prompt.includes(fullReports), 'round 2 must receive reports including original findings');
}
""")

    def test_second_round_findings_raise_effort_for_one_final_repair(self):
        self.run_probe(r"""
for (const [plannedCandidate, fromEffort, toEffort] of [
  ['opus-high', 'high', 'xhigh'],
  ['opus-xhigh', 'xhigh', 'max'],
]) {
  const {report,calls} = await run({repair:true,findingsRounds:[1,2],plannedCandidate});
  assert.equal(report.completedItems,1);
  assert.equal(report.results[0].status,'completed');
  assert.equal(calls.filter(c=>c.label.startsWith('Repair_') || c.label.startsWith('Final_repair_')).length,2);
  assert.equal(calls.filter(c=>c.label.startsWith('review_')).length,6);
  const repairs = calls.filter(c=>c.label.startsWith('Repair_') || c.label.startsWith('Final_repair_'));
  assert.deepEqual(repairs.map(c=>[c.model,c.effort]),[['opus',fromEffort],['opus',toEffort]]);
  const reviewers = calls.filter(c=>c.label.startsWith('review_'));
  assert.ok(reviewers.every(c=>c.model==='sonnet' && c.effort==='medium'));
  assert.equal(report.results[0].effortEscalation.from.reasoning_effort,fromEffort);
  assert.equal(report.results[0].effortEscalation.to.reasoning_effort,toEffort);
}
""")

    def test_third_round_findings_stop_without_closeout(self):
        self.run_probe(r"""
const {report,calls} = await run({repair:true,findingsRounds:[1,2,3]});
assert.equal(report.completedItems,0);
assert.equal(report.results[0].status,'review_action_required');
assert.equal(report.stoppedAt,'AB#123');
assert.equal(report.results[0].reviewRounds.length,3);
assert.equal(report.results[0].repairCommits.length,2);
assert.ok(report.results[0].reason.includes('review round 3'));
assert.equal(calls.filter(c=>c.label.startsWith('Repair_') || c.label.startsWith('Final_repair_')).length,2);
assert.equal(calls.filter(c=>c.label.startsWith('review_')).length,6);
assert.ok(!calls.some(c=>c.label.startsWith('closeout_')));
""")

    def test_no_higher_supported_effort_stops_after_second_round(self):
        self.run_probe(r"""
const {report,calls} = await run({repair:true,findingsRounds:[1,2],plannedCandidate:'opus-max'});
assert.equal(report.completedItems,0);
assert.equal(report.results[0].status,'review_action_required');
assert.ok(report.results[0].reason.includes('no documented higher supported implementation effort'));
assert.equal(report.results[0].reviewRounds.length,2);
assert.equal(report.results[0].repairCommits.length,1);
assert.equal(calls.filter(c=>c.label.startsWith('review_')).length,4);
assert.ok(!calls.some(c=>c.label.startsWith('closeout_')));
""")


if __name__ == "__main__":
    unittest.main()
