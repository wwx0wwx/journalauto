#!/usr/bin/env bash
# 全真夜札引擎 - 自动运行脚本（供 systemd 调用）
set -euo pipefail

# 项目根目录（可通过环境变量覆盖）
PROJECT_ROOT="${ENGINE_ROOT:-/opt/blog-src}"

cd "$PROJECT_ROOT"

# 运行新的模块化引擎
/usr/bin/env python3 "$PROJECT_ROOT/scripts/run.py" >> "${LOG_DIR:-$PROJECT_ROOT/logs}/night-journal.log" 2>&1
