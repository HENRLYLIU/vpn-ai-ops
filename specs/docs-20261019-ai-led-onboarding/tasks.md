# Tasks

- [x] 核对现有 CLI 的 SSH、Token、MCP 和设备权限边界，确认用户目标
- [x] 重写用户入口与环境准备清单
- [x] 完善 AI 执行提示词、运维约定和参数发现流程
- [x] 同步发布和首次使用验收说明
- [x] 检查链接、文档一致性、公开文件与 Git 差异，记录实际验证结果

## 分析检查点

当前 CLI 使用 BatchMode SSH 公钥登录，preflight/deploy 直接读取 CF_API_TOKEN；未实现 MCP 适配或密码引导。官方 Cloudflare API MCP 支持 OAuth 和 DNS API，但具体授权及秘密传递路径必须在执行环境中检查。本次无 project-context-mcp 可调用工具，使用本 Spec 记录里程碑。

## 实施检查点

README 已改为资源清单和一段任务；新增 docs/ai-environment.md。setup.md 和 prompts/deploy.md 改为 AI 执行职责；命令参考移入 operations.md；同步 AGENTS、Token 指南入口、官方来源、发布和验收清单。下一步检查全部文档链接、边界一致性、公开文件及 Git 差异。本次不修改运行时代码，不连接真实 VPS 或 Cloudflare 账号。

## 验证检查点

- `python3 -m unittest discover -s tests -v`：22 项通过。
- `python3 -m compileall -q vpnctl.py vpnops scripts tests`：通过。
- `python3 scripts/check_public_files.py`：39 个公开文件检查通过。
- 临时 Markdown 检查：24 个本地链接目标存在，代码围栏成对；未向仓库添加镜像实现的测试。
- `git diff --check`：通过；审查修改及新文件，范围仅 Markdown 文档和项目状态，无运行时代码变更。
- 未执行真实 VPS / MCP / 客户端 GUI 验收；对应清单已明确标记待实测。本版按用户要求提交至本地 Git，未推送远端。
