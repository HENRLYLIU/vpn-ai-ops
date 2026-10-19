#!/usr/bin/env python3
"""Run from the repository root with Python 3.10 or later."""
import json
import sys
from vpnops.cli import main
from vpnops.model import OpsError

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OpsError, OSError, ValueError, KeyError) as exc:
        message = str(exc) if isinstance(exc, OpsError) else "配置/文件/网络错误；检查文件结构、权限及依赖，不输出秘密调试"
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("已中断本地等待；先确认服务端状态再重试。", file=sys.stderr)
        sys.exit(130)
