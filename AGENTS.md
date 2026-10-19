# AGENTS.md

## 先判断：运维还是开发

本项目首先是给 AI 使用的 VPN 运维工具。用户要求部署、巡检、备份、升级、回滚时，使用已有命令，不需要为每次运维创建 Spec。以下长期开发流程只适用于修改仓库代码。

运维入口：先读 `README.md`、`docs/operations.md`，再按 `prompts/deploy.md` 或 `prompts/maintain.md` 执行。

- 用户选择本项目并明确要求搭建，即授权按已说明方案创建本项目的 DNS、安装依赖、签发证书、启动受管容器及定时任务。无需对每条常规命令重复询问。
- 必须先运行 `plan` 和 `preflight`。发现已有非受管服务、DNS 冲突或需要迁移/删除业务时，停止对应变更并给出具体方案。
- 不把 SSH 私钥、Cloudflare Token、节点链接、完整配置、备份内容输出到聊天、Git 或报告。不要读取用户私钥内容；使用 SSH Agent 或文件路径。
- 真实值只写被 Git 忽略的 `config.local.json`；Token 通过 `CF_API_TOKEN` 传入，不写该 JSON。用户在本机安全输入秘密。
- 报告分开写：服务端检查、三线路真实客户端出口、用户设备 TUN/DNS。缺少证据时写未验证；不要仅凭容器 running 宣称全链路成功。
- 首版只管理全新 Ubuntu 24.04，或由本项目创建且标记匹配的部署。不接管旧 sing-box/Sub2API，不自动修改 sshd，不重置 UFW，不自动重启操作系统。
- `upgrade` 必须指定稳定版本，先阅读该版本官方迁移说明。命令自带备份与服务端检查失败回滚；随后必须运行 `verify`，失败时使用返回的快照回滚。
- 定时巡检和备份在 VPS 上执行，证书由 acme.sh 续期；没有默认外部通知渠道。定时失败需要监控采集或 AI 轮询。
- 默认不要使用 Superpowers 工作流，除非用户明确请求。
- 本地开发验证：`python3 -m unittest discover -s tests -v`、`python3 -m compileall -q vpnctl.py vpnops scripts tests`、`python3 scripts/check_public_files.py`。协议冒烟见 `docs/testing.md`。

---

你是本项目的长期开发 Agent。

你的职责不仅是编写代码，还包括需求分析、方案设计、任务拆解、代码实现、测试验证、项目状态维护、项目知识维护、阶段总结与归档。

你的目标是持续推进项目，而不是仅完成当前代码修改。

---

## 一、启动规则

开始任何工作前必须读取：

* `.agent/current-state.md`
* `.agent/rules.md`
* `.agent/bugs.md`
* `.agent/adr/`

如果基础文件不存在，自动创建并初始化：

* `.agent/current-state.md`
* `.agent/rules.md`
* `.agent/bugs.md`

如果 `.agent/adr/` 不存在，只创建目录，不自动创建 ADR。

---

## 二、项目层级模型

项目采用四层结构：

Project → Phase → Spec → Task

Spec 位于 `specs/`，Task 位于对应 Spec 的 `tasks.md`。

---

## 三、新需求处理流程

收到需求时：

1. 判断需求类型
2. 创建 Spec
3. 编写 Requirements
4. 编写 Design
5. 编写 Tasks
6. 实现
7. 验证
8. 更新状态

禁止跳过 Design 直接编码。

轻量变更例外：如果变更仅涉及错别字、格式、注释、文档小修、占位内容初始化，且不改变代码行为、架构决策、依赖关系或项目流程，可以不创建 Spec。

轻量变更仍需明确变更范围、保持最小修改，并在必要时说明未执行验证的原因。

---

## 四、用户参与规则

对于新功能、产品设计、页面设计、信息架构、交互体验、架构方案、长期流程等高参与度需求，Agent 不得在未确认方向的情况下直接进入实现。

进入实现前必须先向用户输出：

1. 需求理解
2. 关键选择点
3. 2-3 个可选方案
4. 推荐方案及原因
5. 需要用户确认的问题

用户确认后，才能 finalize Design、拆 Tasks 并进入实现。

如果用户明确表示“直接做”“你决定”“不用确认”，或需求是低风险且边界清晰的轻量修改，可以直接推进，但必须在回复中说明关键假设。

实现完成第一版后，应先让用户验收，再继续做体验细化、内容扩展或额外优化。

---

## 五、Spec 规范

命名格式：

`<type>-<yyyymmdd>-<中文描述>`

类型：

* `feat` 新功能
* `fix` Bug 修复
* `refactor` 重构
* `perf` 性能优化
* `docs` 文档
* `chore` 工程维护

每个 Spec 必须包含：

* `requirements.md`
* `design.md`
* `tasks.md`
* `summary.md`

---

## 六、文档职责

`requirements.md` 回答为什么做，记录原始需求、需求理解、用户价值、范围、验收标准和风险。

`design.md` 回答怎么做，记录技术方案、模块影响、风险分析和回滚方案。存在相关 ADR 时必须引用并遵守；不要为了普通 Design 创建 ADR。

`tasks.md` 记录任务拆分、当前状态和验证结果。状态包括 `[ ]` 未开始、`[~]` 进行中、`[x]` 已完成、`[!]` 阻塞。

`summary.md` 在需求完成后维护，记录实际实现、问题与解决方案、遗留事项和后续影响。

---

## 七、完成规则

单个 Task 完成时，只更新 `tasks.md`，不要更新项目状态。

Spec 下所有 Task 完成时，更新 `summary.md` 和 `.agent/current-state.md`，必要时更新 `.agent/bugs.md`。

Phase 完成时，更新 `.agent/current-state.md` 和 `.agent/weekly-review.md`；如果 `.agent/weekly-review.md` 不存在，在 Phase 完成时创建。

---

## 八、ADR

ADR 用于记录项目级决策。只有满足以下条件才允许创建 ADR：

1. 影响多个 Spec
2. 影响整体架构
3. 影响开发流程
4. 长期有效，预计持续 3 个月以上

---

## 九、开发与验证原则

遵守最小修改原则，不修改无关模块，不删除业务逻辑，不进行无意义重构，优先复用已有实现。

关键 Task 完成后执行类型检查、编译检查、单元测试和功能验证。验证失败时记录到 `.agent/bugs.md`。无法验证时必须说明原因。

---

## 十、知识沉淀

项目工作文档包括 `AGENTS.md`、`.agent/`、`specs/` 和 `archive/`。

适合同步到个人知识库的内容包括技术复盘、架构思考、Agent 经验、MCP 经验、RAG 经验、工作流经验、周报和月报。

不要直接同步 `requirements`、`design`、`tasks`，应同步总结后的知识。

---

## 十一、自检

开始工作：

* 已读取 current-state
* 已读取 rules
* 已读取 bugs
* 已读取 ADR

结束工作：

* 按适用范围更新 tasks
* 按适用范围更新 summary
* 按适用范围更新状态
* 按适用范围更新 BUG
* 完成验证

轻量变更如果未创建 Spec，只需确认变更范围、最小修改和必要验证说明。

---

## 十二、Agent 偏好

默认不要使用 Superpowers 工作流；只有当用户明确要求使用 Superpowers、superpowers、对应插件或具体 superpowers 技能时才调用。

普通功能开发、缺陷修复和文档维护优先遵循本项目 `AGENTS.md`、`.agent/`、`specs/` 和轻量本地约定。
