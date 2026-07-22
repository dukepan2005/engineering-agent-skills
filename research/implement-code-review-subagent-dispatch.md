# `implement` / `code-review` 子代理派发机制研究

## 结论

1. **指定审查子代理的是 `code-review`，不是 `implement`。** `code-review` 明确要求 Standards 与 Spec 两个审查轴以并行子代理执行，并在流程第 4 步要求一次消息内发起两个 `Agent` 调用；两者均指定为 `general-purpose` 子代理。来源：`/Users/duke/.agents/skills/code-review/SKILL.md` 第 3、11、58–60 行。

2. **`implement` 只规定交接顺序。** 完成实现后调用 `/code-review`，然后提交当前分支；它没有规定创建子代理、子代理类型、固定点或并行策略。因此，调用 `implement` 后出现审查子代理，是 `/code-review` 被调用后的行为，不是 `implement` 的独立派发规则。来源：`/Users/duke/.agents/skills/implement/SKILL.md` 第 13–15 行。

3. **真正派发需要宿主运行时能力，Skill Markdown 本身不能创建执行单元。** 这两份文件都是工作流指令：`code-review` 只能要求调用 `Agent` 工具；实际派发取决于宿主是否提供可调用的子代理/任务创建工具、可用的子代理类型与并发配额，并由宿主执行该工具调用。本会话的 Codex 宿主提供的是 `spawn_agent` 能力，而不是这份 Matt Skill 所写的 `Agent` 工具名；因此，必须由宿主（或适配层）把该声明翻译为实际的 `spawn_agent` 调用。OpenAI 对 Skills 的定位也是可复用的工作流/指令；插件中的 App 才连接可执行的数据与动作能力。[OpenAI: Skills in ChatGPT](https://help.openai.com/en/articles/20001066-skills-in-chatgpt/)；[OpenAI: Plugins in Codex](https://help.openai.com/en/articles/20001256-plugins-in-codex/)

4. **Spec 审查器的跳过条件是“没有可用 spec”。** 源查找依次为提交信息关联 issue、用户给出的路径、与功能匹配的 `docs/`、`specs/` 或 `.scratch/` 文件；若仍找不到，应询问用户。用户确认不存在 spec 时，Spec 子代理跳过并报告 `no spec available`；流程也再次规定 spec 缺失时跳过，并在最终报告说明。这里的“用户尚未回答去哪里找”不是可直接跳过的条件。来源：`/Users/duke/.agents/skills/code-review/SKILL.md` 第 25–32、74 行。

## 对 `azure-task-implement` 重设计的含义

以下是基于上述已确认事实的设计推论：

- 保持 wrapper 薄：`azure-task-implement` 应继续负责代码实现、验证与 closeout comment；编排器负责 Azure 预检和关闭。审查语义（固定点、两轴、输入资料与聚合）应继续委托给 `code-review`，而不是复制一套逐渐漂移的审查流程。
- 明确运行时契约：不要在 Skill 中把 `Agent` 当作可移植、必然存在的工具。应由调用它的宿主提供并声明实际派发原语（本 Codex 环境为 `spawn_agent`）、允许的代理类型、并发上限、超时/失败处理与结果回收；若无此能力，则退化为同一代理串行执行两个轴并如实标注，而非声称已经并行独立审查。
- 先完成审查前置条件：在委托前固定比较基准，确认其可解析且 diff 非空；为 Standards 收集仓库规范，为 Spec 找到来源或先询问。只有用户确认“没有 spec”时才跳过 Spec，不能将“尚未定位”静默等同于“没有”。
- 保持既有交接顺序：实现和验证完成后做未提交 diff 的审查；处理发现后才提交；Azure Boards 关闭应继续位于提交之后。该顺序是 `implement` 的 review-before-commit 要求与 Azure wrapper 的职责组合，后半句是架构建议，不是 Matt `implement` 文件的原文要求。

## 已确认与未确认边界

- 已确认：上述两份已安装 Skill 的文字要求、Spec 跳过条件，以及 OpenAI 对 Skill/插件能力边界的产品说明。
- 未确认：当前或未来任一 Codex 宿主是否必然暴露 `spawn_agent`、是否支持 `general-purpose` 这一代理类型、以及具体并发数。它们必须由实际宿主工具清单/配置在运行时确认，不能从 Matt Skill 推断。
