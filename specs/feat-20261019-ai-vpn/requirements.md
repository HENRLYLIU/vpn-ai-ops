# AI 驱动的个人 VPN 自动化

用户已确认：面向购买了 VPS、已托管 Cloudflare 域名的使用者，由 AI 执行命令和排错。仓库独立公开发布，不携带原项目凭据。

首版支持全新 Ubuntu 24.04 VPS、IPv4、SSH 公钥登录、root 或免密 sudo。提供 Reality / Hysteria2 / WebSocket TLS 三线路，Cloudflare DNS、证书、Docker 部署、客户端导出、三线路真实核心验证、定时巡检与备份、明确版本的升级和回滚。

验收：离线单元测试、真实核心配置校验、CLI 冒烟测试、Git 敏感信息检查。未经一次干净 VPS 部署，不宣称全链路生产验收完成。现有生产服务器不属于本次实现的测试目标。
