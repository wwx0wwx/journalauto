# 全真夜札系统运行模式

## mode 字段

- `auto`：生成后直接发布
- `review-first`：生成到 `draft_review/`，不自动发布
- `manual-only`：只允许手动触发，不允许 timer 正常发文
- `max_posts_per_day`：每日发文硬限制。0 代表不限制，1 代表发过一篇后当天强制阻断

## 手动干预项

- `force_topic`：强制今夜主题
- `force_primary_emotion`：强制主情绪
- `force_secondary_emotion`：强制辅情绪
- `force_scene`：强制场景
- `force_memory_id`：强制触发某条记忆锚点
- `force_future_id`：强制触发某条未来片段
- `forbid_terms`：禁写词
- `forbid_topics`：禁写主题
- `pause_publishing`：暂停发布
- `notes_for_tonight`：额外导演批注
