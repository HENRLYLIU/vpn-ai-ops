# 运维手册

## 命令约定

所有本地命令在仓库根目录运行。需要指定别的配置文件时，把 `--config <path>` 放在子命令前。`plan` 完全离线；`preflight` 读取 VPS 和 Cloudflare；`deploy` 改变服务器和 DNS；其他服务器操作无需本地 Cloudflare Token。

退出码：`0` 成功；`1` 参数、连接、命令失败；`2` 巡检或客户端验收未通过。JSON 的 warnings 即使不阻止运行也需要 AI 在报告中呈现。

## 首次部署的命令顺序（由 AI 执行）

先按 [环境准备](ai-environment.md) 完成可信 SSH 公钥登录和凭据注入。当前 CLI 不接受 SSH 密码，也不会从 MCP 自动取得 Token。以下命令供 AI 实施与排错使用，用户不需要逐条复制执行。

```bash
python3 vpnctl.py init
# AI 按 docs/setup.md 填写 config.local.json；已有配置时先检查，不重复 init
python3 vpnctl.py plan
# CF_API_TOKEN 已通过安全渠道注入本次实际执行环境
python3 vpnctl.py preflight
python3 vpnctl.py deploy
python3 vpnctl.py status
python3 vpnctl.py verify --mihomo /absolute/path/to/mihomo
```

`verify` 的路径由 AI 替换为已核对来源与摘要的真实核心路径。`deploy` 自动导出私有客户端文件到 `artifacts/`。完成或失败退出时，由 AI 在持有凭据的实际会话中清理临时环境变量；不假定另一工具调用的 `unset` 能清理先前进程或秘密存储。VPS 上 acme.sh 的续期凭据需保留。

完整部署已有 ready 标记时，再次 `deploy` 只做健康检查及重新导出，不轮换密钥。单独重新导出使用 `export`；更换版本使用 `upgrade`。当前配置基线 sing-box 1.13.14，部署固定 digest，不追踪 latest。

## 服务器目录

```text
/opt/vpn-ai-ops/                  root-only
├── state.json                   管理标记、资源参数、版本、镜像 digest
├── keys.json                    节点凭据；不可公开
├── compose.json                 固定 digest 的 Compose 配置
├── config/config.json           sing-box 配置，包含私钥，600
├── certs/                       正式证书与私钥
├── acme/                        固定版本 acme.sh、账户、续期 Token
├── agent.py                     定时任务执行器
├── backups/                     最近 8 份完整敏感快照
├── reports/latest-health.json   最近定时巡检报告
├── reports/latest-backup.json   最近定时备份结果
└── last-error.log               最近失败命令诊断，可能含秘密，600
```

正常路径不输出命令原始日志。失败时由有权限的 AI/运维人员在服务器上选取最小错误摘要并脱敏，禁止直接 `cat last-error.log` 到公开会话。

## 定时任务与证书

- `vpn-ai-ops-health.timer`：每日检查，随机错开最多 30 分钟。
- `vpn-ai-ops-backup.timer`：每周备份，随机错开最多 30 分钟。
- 两个 timer 都使用 `Persistent=true`，错过调度后可补执行。
- acme.sh 自身 cron 自动续期，使用私有 home；成功续期后仅重启本项目容器。
- `status` 检查容器、镜像一致性、配置、源站 TLS、敏感文件权限、磁盘、重启提示、cron 和 timer。不会查询云账单、流量余额或云安全组。

通过 SSH 检查以下非敏感状态：

```bash
sudo systemctl list-timers 'vpn-ai-ops-*'
sudo systemctl status vpn-ai-ops-health.service vpn-ai-ops-backup.service --no-pager
sudo cat /opt/vpn-ai-ops/reports/latest-health.json
sudo cat /opt/vpn-ai-ops/reports/latest-backup.json
```

巡检发现实际失败时 service 返回非零；warnings 保留在 JSON。没有邮件/聊天机器人默认推送。无人登录时仍会续期、检查和备份，但不会自动把报告发给你。需要告警时接入现有监控或安排 AI 定期运行 `status`。

不要反复 `--force` 申请证书。Token 失效时在安全终端更新凭据后，按 acme.sh 官方流程修复账户；不要把 Token 打进命令日志。固定版本 acme.sh 本身不自动升级，升级需检查官方变更与源码摘要。

## 备份与恢复范围

`backup` 生成 gzip tar，权限 600，包含节点密钥、配置、证书、ACME 账户及续期 Token。备份不是脱敏报告，不能提交 Git。自动保留最近 8 份，包括手动和升级前的快照；频繁操作会缩短实际历史窗口。

这是本机恢复快照，不是异地容灾。VPS 丢失时，本机快照也会丢失。异地备份需要用户选择自己的加密存储位置，另行配置。

普通 `rollback` 只恢复本项目的状态、配置、镜像和一致的节点密钥，保留最新证书、ACME 账户和定时任务。先备份当前状态；失败时尝试恢复操作前快照。它不会回退系统软件包、DNS、UFW、SSH 或旧业务。

新建部署中途失败时，已创建的 DNS、依赖和 root-only 状态保留供排错与重试；不自动卸载共享系统组件。修复原因后重新 `deploy`，保留原密钥。若它已启动容器但验收失败，可由 AI 明确执行本项目的 `docker compose -f /opt/vpn-ai-ops/compose.json stop`，不删除数据。

## 升级

1. 阅读目标版本 release notes / migration，指定精确稳定版本。
2. 确认当前 `status` 和 `verify` 的基线；失败时先排错。
3. 运行 `upgrade --version X.Y.Z`。新镜像必须先通过旧配置检查，之后才备份和重建。
4. 服务端启动或健康检查失败会自动回滚；保持镜像缓存，不执行 Docker prune。
5. 服务端通过后运行 `verify`。客户端协议失败不会由服务器自检捕获，需要 AI 执行 `rollback --backup <本次返回的快照>`。
6. 回滚后再验证。成功升级/回滚会同步 `config.local.json` 中的版本；如果 SSH 在变更中断开，先用 `status` 确认实际版本，再同步本地配置。

系统内核升级、Docker 升级及 VPS 重启不在自动任务范围内。必须计划短暂中断、保留云控制台恢复渠道，并检查重启后全部服务。
