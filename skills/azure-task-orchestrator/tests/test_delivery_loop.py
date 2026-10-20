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
async function run({repair=false, transformReview=r=>r, closeout=applied, itemId='AB#123'} = {}) {
  const calls = [], firstReports = [];
  const item = {id:itemId, type:'Task', plannedCandidate:'opus-high', reviewCandidate:'sonnet-medium',
    reviewEvidence:'review rationale', plannerEvidence:'implementation rationale', orderReason:'stable'};
  const agent = async (prompt, options) => {
    calls.push({prompt, ...options});
    if (options.label.startsWith('preflight_')) return {rev:1};
    if (options.label.startsWith('closeout_')) return closeout;
    if (options.label.startsWith('review_')) {
      const round = Number(options.label.split('_')[1]);
      const axis = options.label.includes('_standards_') ? 'standards' : 'spec';
      const findings = repair && round === 1 ? [finding] : [];
      const report = {axis, reviewBase:'base', head:round===1?'impl':'repair', parent:round===1?'base':'impl',
        status:findings.length?'findings':'clean', findings, summary:`${axis} original report context`};
      if (round === 1) firstReports.push(report);
      return transformReview(report, round);
    }
    return {outcome:'ready_for_review', reviewBase:'base', taskStartCommit:'base',
      commit:options.label.startsWith('Repair_')?'repair':'impl', verification:[], acceptanceEvidence:[]};
  };
  const report = await execute({validatedPlan:[item],trackerConnection:{organization:'org',project:'project'}},agent,()=>{},()=>{});
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
  {...applied,id:999}, JSON.stringify({mode:'validated',id:123})]) {
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

    def test_remaining_second_round_findings_stop_closeout(self):
        self.run_probe(r"""
const {report,calls} = await run({repair:true,transformReview:r=>({...r,status:'findings',findings:[finding]})});
assert.equal(report.completedItems,0);
assert.equal(report.results[0].status,'review_action_required');
assert.equal(report.stoppedAt,'AB#123');
assert.equal(calls.filter(c=>c.label.startsWith('Repair_')).length,1);
assert.equal(calls.filter(c=>c.label.startsWith('review_')).length,4);
assert.ok(!calls.some(c=>c.label.startsWith('closeout_')));
""")


if __name__ == "__main__":
    unittest.main()
