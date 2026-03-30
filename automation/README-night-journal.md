# 全真夜札引擎（最小可用骨架）

## 目录

- `automation/world_state.json`：世界状态机
- `automation/memory_anchors.json`：核心记忆锚点库
- `automation/topic_rules.json`：题材与约束
- `scripts/generate_night_journal.py`：生成 + 发布脚本
- `scripts/run_night_journal.sh`：执行入口
- `automation/night-journal.service`：systemd service 模板
- `automation/night-journal.timer`：systemd timer 模板

## 当前状态

这是一版 **最小可用原型**：

- 已能读取 VPS 基础状态：uptime、load、内存、SSH 失败日志
- 已能映射成“江湖事件”
- 已能拼接 prompt
- 已能写入 Hugo 文章并构建发布
- **暂时还没有真正调用模型 API**，当前写出的文章是“占位稿 + 当次 prompt”，便于先把框架跑通

## 下一步要接的东西

把 `generate_night_journal.py` 里的占位稿部分替换成真实模型调用即可。推荐方式：

1. 直接请求你在 OpenClaw 已配置可用的 provider/model
2. 或额外为博客脚本单独配置一个 API Key / Base URL

## 如何启用定时器（建议 systemd）

把模板复制到 systemd：

```bash
cp /opt/blog-src/automation/night-journal.service /etc/systemd/system/night-journal.service
cp /opt/blog-src/automation/night-journal.timer /etc/systemd/system/night-journal.timer
chmod +x /opt/blog-src/scripts/run_night_journal.sh /opt/blog-src/scripts/generate_night_journal.py
systemctl daemon-reload
systemctl enable --now night-journal.timer
systemctl list-timers | grep night-journal
```

## 手动试跑

```bash
chmod +x /opt/blog-src/scripts/run_night_journal.sh /opt/blog-src/scripts/generate_night_journal.py
/opt/blog-src/scripts/run_night_journal.sh
```

## 注意

- 目前默认每周二、四、六 UTC 16:00 运行
- 当前文章标题会按题材自动命名
- 建议接入真实模型后，再补：
  - 去重器
  - 回忆触发抑制
  - 上一篇自动摘要
  - 正式 API 错误重试与日志
