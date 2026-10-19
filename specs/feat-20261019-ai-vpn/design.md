# 设计

- 本地 Python 3.10+ 标准库 CLI；AI 从 AGENTS.md 和 prompts/ 进入。无 pip 依赖，Linux/macOS/WSL 控制端。
- 标准 OpenSSH 传输，严格主机密钥校验。远程 Python 执行器通过 SSH stdin 接收 JSON，秘密不放在命令行。Cloudflare Token 仅从环境读取。
- 受管目录 /opt/vpn-ai-ops，标记文件区分自己的部署，拒绝覆盖未知部署。首次部署先检查系统和端口，再改 DNS、安装依赖。DNS 冲突不覆盖，不修改全站 SSL 设置。
- 固定 sing-box 版本，并在部署时解析 image digest。acme.sh 固定源码版本与摘要，独立 home。服务端随机生成凭据，目录 700、秘密文件 600。
- 维护：acme.sh 自动续期、systemd 每日健康检查/每周备份，备份保留 8 份。升级和回滚由 AI 明确调用，无无人值守版本追踪或系统重启。
- 健康检查输出 JSON；定时检查失败让 systemd 单元失败以供外部监控采集。无外部告警推送默认配置。
- 部署成功只代表服务端就绪，真实三线路出口和用户设备 DNS 验收分开记录。
