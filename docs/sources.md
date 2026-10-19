# 官方来源与版本基线

核对日期：2026-10-19。本次环境没有可调用的 Context7 MCP，直接核对上游官方资料。使用此项目时若 Context7 可用，先 resolve-library-id 再 query-docs；升级以目标版本文档为准。

- [Docker Ubuntu 官方 apt 安装](https://docs.docker.com/engine/install/ubuntu/)：官方软件源、签名与 Compose plugin。不会运行第三方 Docker 一键脚本。
- [sing-box VLESS inbound](https://sing-box.sagernet.org/configuration/inbound/vless/)、[TLS / Reality](https://sing-box.sagernet.org/configuration/shared/tls/)、[Hysteria2 inbound](https://sing-box.sagernet.org/configuration/inbound/hysteria2/)、[WebSocket transport](https://sing-box.sagernet.org/configuration/shared/v2ray-transport/)。
- [sing-box v1.13.14](https://github.com/SagerNet/sing-box/releases/tag/v1.13.14)：本项目固定配置基线；不声称是最新版本。部署时记录 GHCR digest。
- [sing-box migration](https://sing-box.sagernet.org/migration/)：升级前核对配置迁移。
- [Cloudflare DNS create](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/create/)、[Zone settings get](https://developers.cloudflare.com/api/resources/zones/subresources/settings/methods/get/)：DNS 与 strict TLS 预检。
- [acme.sh](https://github.com/acmesh-official/acme.sh)、[Cloudflare DNS API](https://github.com/acmesh-official/acme.sh/wiki/dnsapi)：DNS-01、CF_Token/CF_Zone_ID、install-cert 和 reloadcmd。
- acme.sh 源码固定 `3.1.6`，下载自官方 codeload，SHA-256 固定在执行器中；校验失败时停止，不跳过。
- [mihomo VLESS](https://wiki.metacubex.one/config/proxies/vless/)、[Hysteria2](https://wiki.metacubex.one/config/proxies/hysteria2/)、[DNS](https://wiki.metacubex.one/config/dns/)：客户端模板依据。

源码摘要只验证与本项目选定内容一致；公开分享前仍应审查上游依赖与升级记录。
