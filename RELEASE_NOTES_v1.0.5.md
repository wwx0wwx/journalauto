# 全真夜札 v1.0.5 发布说明

## 概要

v1.0.5 是基于 v1.0.4 的发布前收口版本，目标是把当前仓库整理为更适合作为**稳定迁移基线**的 Hugo 博客 + 自动发文系统。

本版优先处理冷审中指出的配置清洗、部署一致性与文档完整性问题，并补上交互式一键安装入口。

## 本版重点

- 移除发布包中的 `.env`，避免 API Key 被一并分发
- 将 `hugo.toml` 的 `baseURL` 改为 `https://example.com/`
- `bootstrap_server.sh` 自动按部署域名重写 `baseURL`
- 清理默认输出目录与旧域名残留，统一改为 `example.com` 占位符
- 修复遗留脚本对 `/opt/blog-src/.env` 的硬编码加载问题
- 将旧单文件引擎脚本显式标记为废弃并拒绝继续运行
- 补充 `scripts/backup_data.sh`
- 新增交互式一键安装脚本 `install.sh`
- 补充 `themes/PaperMod/VENDORED_VERSION.txt`
- 完整修复 `DEPLOY_EXAMPLE.md` 与 `automation/REQUIREMENTS.md` 的旧域名/编码问题
- 改善 dry-run 日志，明确“不写文件、不调用真实 API”

## 验证

已完成以下本地验证：

- `python3 -m py_compile` 通过
- `python3 scripts/run.py --dry-run` 通过
- 本地生产目录 `/opt/blog-src` 已同步更新
- `python3 scripts/run.py` 真实生成成功
- `hugo --destination /var/www/<domain>` 构建成功
- 生成文章：`content/posts/20260326-082711-night-note.md`
- 标题：`簪脚凉过一瞬`

## 发布结论

v1.0.5 可作为当前阶段的稳定迁移基线。
