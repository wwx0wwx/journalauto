#!/usr/bin/env bash
set -euo pipefail

# 获取脚本所在目录的父目录作为 ENGINE_ROOT
ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ENGINE_ROOT}/automation/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

# 备份所有 JSON 配置文件和状态文件
tar -czf "${BACKUP_DIR}/night-journal-${TIMESTAMP}.tar.gz" -C "${ENGINE_ROOT}" automation/*.json

# 保留最近 30 天的备份，清理过旧文件
find "${BACKUP_DIR}" -name "night-journal-*.tar.gz" -mtime +30 -delete

echo "[ok] Backup created: ${BACKUP_DIR}/night-journal-${TIMESTAMP}.tar.gz"
