# Current model-profile evidence sources

Date checked: 2026-09-23

This is a dated source inventory, not a permanent ranking. For live planning,
recheck the official model/host documentation and the newest applicable
benchmark report as required by the [`task-model-planner` skill](../skills/task-model-planner/SKILL.md).

## Source policy

- Official provider documentation establishes model identity, supported
  controls, and provider guidance. For host aliases, the host's current docs or
  runtime selection establish what the alias resolves to.
- Benchmark reports establish results only for their stated model version,
  effort, task set, harness, tools, and date. Vendor-published scores are
  first-party results, not independent confirmation. Prefer matched comparisons
  and record uncertainty or harness differences.
- The execution-profile registry remains the approved set of configurations for
  this workflow. Public API support for additional settings does not expand the
  host-approved profiles.

## Benchmark-owner leaderboards and methodology

These are primary entry points maintained by benchmark owners or evaluators.
Use the task-specific results and methodology, not just the headline rank.

- [SWE-bench official leaderboards](https://www.swebench.com/): repository issue
  resolution across Verified, Lite, Multilingual, and other suites. For a
  cleaner comparison, inspect the Bash Only view, where entries use the same
  mini-SWE-agent environment; other submissions may use different agents and
  settings.
- [Terminal-Bench leaderboard](https://www.tbench.ai/): tool-using agent tasks;
  rows identify both model and agent, and the page reports resolution rate,
  cost, token use, and confidence intervals. Match the agent/harness as well as
  the model before interpreting a score difference.
- [SWE-Bench Pro public leaderboard](https://labs.scale.com/leaderboard/swe_bench_pro):
  Scale AI's harder, longer-horizon repository engineering evaluation. This is
  a benchmark-owner result; compare it with other sources rather than treating
  the publisher's leaderboard as independent replication.
- [LiveCodeBench leaderboard](https://livecodebench.github.io/leaderboard.html)
  and [project/method overview](https://livecodebench.github.io/): continuously
  collected competitive-programming problems, code generation, self-repair,
  execution, and test-output prediction. It is useful for coding ability, but
  does not directly measure autonomous work in an existing repository.
- [Aider Polyglot coding leaderboard](https://aider.chat/docs/leaderboards/):
  code editing on Exercism tasks through Aider's edit workflow; entries can
  include the model, effort, edit format, cost, and Aider version. Treat it as
  Aider-harness evidence, not a host-neutral model-only comparison.

For a cross-benchmark view, [Artificial Analysis' Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)
is a third-party evaluator's composite leaderboard of model-and-agent
configurations, with a [published methodology](https://artificialanalysis.ai/methodology/coding-agents-benchmarking).
Use its per-benchmark breakdown and setup details; an aggregate score can hide
meaningful differences between repository patching, terminal workflows, and
repository Q&A.

## Sources checked

### Codex / ChatGPT

- OpenAI's [GPT-6 Sol model documentation](https://developers.openai.com/api/docs/models/gpt-6-sol),
  [GPT-6 Luna model documentation](https://developers.openai.com/api/docs/models/gpt-6-luna),
  and [model-selection guidance](https://developers.openai.com/api/docs/guides/model-selection)
  confirm the current API model identifiers and explain that availability and
  reasoning settings vary by product and model version. The API catalog exposes
  a broader set of reasoning settings than this workflow's approved profile
  registry; use the registry and active host selection, not the API list alone.
- OpenAI's model-selection page notes that model availability and reasoning
  settings differ by product/version. This check verified the public API catalog,
  not the live model picker for the signed-in Codex/ChatGPT host; confirm the
  active host before dispatch.
- The current [CursorBench 4.0 results](https://prod.cursor.com/evals) page has
  no exact-current-profile row for GPT-6 Sol or Luna, so it does not provide a
  coding comparison for them. The [OpenAI GPT-6 system-card evaluations](https://deploymentsafety.openai.com/gpt-6-astra/protocolqa-open-ended)
  include safety and cybersecurity evaluations for Sol and Luna, but those are
  not general coding-agent benchmark results.
- No exact-current-profile coding benchmark report was located in the sources checked on this date. Treat this as an evidence gap, not evidence that no report exists. Do not use older-version scores as a substitute or make a comparative performance claim without a newer exact-match report.

### Claude Code

- Anthropic's current [Claude Opus 5.5 release and evaluation report](https://www.anthropic.com/claude-opus-5-5)
  is dated September 22, 2026. Its reported coding evaluations include
  Terminal-Bench 4.0, FrontierCode v1.1, and CursorBench 4.0. The report says
  most Opus 5.5 results use adaptive thinking at max effort, while Terminal-Bench
  uses xhigh; competitor results include figures reported by other vendors, and
  benchmark-specific standard errors are disclosed. These results are useful
  but are not a single matched-effort comparison across all tests.
- Anthropic's [Claude Sonnet 5 release](https://www.anthropic.com/news/claude-sonnet-5)
  is dated June 30, 2026 and points to a more detailed system card. Recheck the
  [system-card index](https://www.anthropic.com/system-cards) for updates before
  planning.
- The official [Claude Code CLI documentation](https://docs.anthropic.com/en/docs/claude-code/cli-usage)
  describes `sonnet` and `opus` as aliases for the latest model in each family,
  but retains old version examples. Record the version and effort from the
  active runtime; a moving alias can outlive a
  benchmark report for the version it used to resolve to.

### Cursor

- Cursor's [Composer 2.5 model documentation](https://prod.cursor.com/docs/models/cursor-composer-2-5)
  identifies its model ID and Cursor-hosted agent capabilities. The
  [Composer 2.5 release evaluation](https://cursor.com/marketing-static/blog/composer-2-5),
  published May 18, 2026, includes vendor-reported benchmark charts. Composer
  2.5 has no manually selected reasoning effort in this workflow's registry.
- The current [CursorBench 4.0 results](https://prod.cursor.com/evals) include
  exact rows for Composer 2.5 and Grok 4.6/4.7 configurations. Cursor describes
  the tasks as ambiguous, multi-file work from real Cursor sessions; its
  changelog says version 4.0 added longer-horizon tasks on September 10, 2026.
  Results are measured in Cursor's own evaluation environment, and Cursor warns
  that small score differences may not be statistically meaningful. Treat this
  as a host-specific, vendor-run benchmark rather than a universal ranking. See
  Cursor's [benchmark methodology](https://cursor.com/blog/cursorbench).
- xAI's [Grok 4.7 documentation](https://docs.x.ai/developers/grok-4-7),
  [reasoning-effort documentation](https://docs.x.ai/developers/model-capabilities/text/reasoning),
  and [release notes](https://docs.x.ai/developers/release-notes) verify current
  API names and settings. Its [Grok 4.7 release report](https://x.ai/news/grok-4-7),
  dated September 21, 2026, reports coding and agent benchmarks. The headline
  comparison uses Grok 4.7 at xhigh and Grok 4.6 at high, so it does not isolate
  the version change from the effort change; use matched-effort rows when
  available. Cursor's current model configuration remains the authority for
  which options this workflow may select.

## Additional useful evidence

For future calibration, consult benchmark maintainers' methodology and
leaderboards, model/system cards and release notes, and blind evaluations on a
representative sample of this repository's completed work. Project evaluations
should use the same prompts, tools, verification, and success criteria across
candidate profiles, then compare correctness, review findings, retries,
latency, token/tool use, and cost. These sources supplement, rather than replace,
the two required source classes above.
