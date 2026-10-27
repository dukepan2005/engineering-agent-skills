# Grok 4.6/4.7 reasoning effort — 2026-09-23

## Findings

| Official context | Model name | Documented effort labels | Scope and qualification |
|---|---|---|---|
| xAI API | `grok-4.6` | `low`, `medium`, `high`, `xhigh` | xAI's reasoning reference lists `grok-4.6` explicitly and says `xhigh` is available on 4.6 and later. Set through `reasoning_effort` (Chat Completions) or `reasoning.effort` (Responses API). [Reasoning docs](https://docs.x.ai/developers/model-capabilities/text/reasoning) |
| xAI API | `grok-4.7` | `low`, `medium`, `high`, `xhigh` | Same documented effort labels and API parameters; `high` is the default. [Reasoning docs](https://docs.x.ai/developers/model-capabilities/text/reasoning), [Grok 4.7 docs](https://docs.x.ai/developers/grok-4-7) |
| Cursor | `grok-4.6` | `low`, `medium`, `high`, `xhigh` | Cursor's model-specific documentation lists all four labels, with `high` as the named-model default. Cursor Start fixes it at `medium` in non-fast mode; choosing an effort requires Pro or higher. [Cursor Grok 4.6 docs](https://cursor.com/help/models-and-usage/grok-4-6) |
| Cursor | `grok-4.7` | `xhigh`, `high`, `medium`, `low` | Cursor's model reference lists all four labels, with `high` as the default. Cursor Start (India) fixes it at `medium` at standard speed. [Cursor Grok 4.7 docs](https://cursor.com/docs/models/grok-4-7) |

## Conclusion for the project profile

The project's statement that Cursor Grok 4.6 and 4.7 support `high` and `xhigh` is supported by both vendors' official documentation. It is an intentionally restricted profile set, not a claim that these are the only available effort levels: both official sources also list `low` and `medium`. Cursor plan restrictions can further limit what a user can select; on the documented Start plans, effort is fixed at `medium`.

The spelling is lowercase `xhigh` in both xAI API documentation and Cursor's model pages. xAI uses the API parameter names `reasoning_effort` and, for Responses, `reasoning.effort`; Cursor describes selectable effort levels in its host model documentation.
