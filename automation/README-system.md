# 全真夜札系统总览

这份 README 用来防止 `/new` 或会话切换后遗忘系统结构。它记录：

- 这套系统是什么
- 所有关键文件在什么位置
- 每个文件负责什么
- 定时发布如何运作
- 如何手动干预
- 如何排障
- 后续继续打磨时从哪里下手

---

## 一、系统目标

这不是普通的“自动发博客脚本”。

它是一个围绕角色 **全真** 搭建的长期叙事系统：

- 基于 Hugo 博客发布
- 由 systemd timer 定时触发
- 读取 VPS 真实状态，映射成“江湖事件”
- 维护世界状态、近期记忆、未来片段、剧情弧线
- 调用 `doongai/gpt-5.4` 生成夜札
- 做润色、标题、description、质量检查
- 自动发布或进入审核模式

---

## 二、博客与发布根目录

### Hugo 源码目录
- `/opt/blog-src`

### 正式文章目录
- `/opt/blog-src/content/posts/`

### 审核草稿目录
- `/opt/blog-src/draft_review/`

### 静态发布目录
- `/var/www/iuaa.de`

---

## 三、最重要的文件清单

## 1. 主脚本

### 生成主脚本
- `/opt/blog-src/scripts/generate_night_journal.py`

这是整个系统核心，负责：
- 读取状态文件
- 读取素材库
- 读取人工 override
- 读取 VPS 事件
- 拼 prompt
- 调模型生成
- 润色
- 生成标题和 description
- 做质量检查
- 发布 / 存草稿
- 回写状态、记忆、统计

### 执行入口
- `/opt/blog-src/scripts/run_night_journal.sh`

systemd service 实际调用的是这个入口脚本。

### 复盘脚本
- `/opt/blog-src/scripts/analyze_journal.py`

用于输出：
- 发文统计
- 当前世界状态
- 剧情弧线阶段
- 最近标题与 description
- 高频主题/场景/情绪/意象
- 最近文本重复风险
- 近期记忆层
- 最近质量失败原因

手动运行：
```bash
python3 /opt/blog-src/scripts/analyze_journal.py
```

---

## 2. systemd 定时任务

### service
- `/etc/systemd/system/night-journal.service`

### timer
- `/etc/systemd/system/night-journal.timer`

### 模板源文件
- `/opt/blog-src/automation/night-journal.service`
- `/opt/blog-src/automation/night-journal.timer`

### 当前用途
- 每周固定时间触发一次夜札生成

### 查看状态
```bash
systemctl status night-journal.timer --no-pager
systemctl status night-journal.service --no-pager
systemctl list-timers --all | grep night-journal
```

---

## 3. 世界状态与叙事状态

### 世界状态机
- `/opt/blog-src/automation/world_state.json`

记录：
- meta（发文时间、季节、时辰等）
- 主人状态
- 姐姐状态
- 全真自身状态
- continuity（最近主题/意象/场景/情绪）
- scheduler（发文频率与日限）
- story_arcs（剧情弧线）

注意：
- `max_posts_per_day: 0` 表示**不限制每日篇数**。
- 当前配置已取消“每天最多一篇”的限制。

### 近期记忆层
- `/opt/blog-src/automation/recent_memories.json`

记录最近十几篇沉淀出来的“小往事”。

### 长期统计
- `/opt/blog-src/automation/night_journal_stats.json`

记录：
- 发文总数
- 成功/失败次数
- 修文次数
- 各主题/场景/情绪/意象使用频率
- 最近标题与 description
- 最近质量失败原因

### 未来片段库
- `/opt/blog-src/automation/future_fragments.json`

记录可能在未来触发的“命数影子”。

### 核心记忆锚点库
- `/opt/blog-src/automation/memory_anchors.json`

记录长期不变的核心往事，用于回忆触发。

---

## 4. 素材库

### 题材与基本规则
- `/opt/blog-src/automation/topic_rules.json`

### 意象池
- `/opt/blog-src/automation/imagery_pool.json`

### 场景池
- `/opt/blog-src/automation/scene_pool.json`

### 情绪池
- `/opt/blog-src/automation/emotion_pool.json`

### VPS 事件映射规则
- `/opt/blog-src/automation/event_map_rules.json`

---

## 5. 人工干预与运行模式

### 手工 override 文件
- `/opt/blog-src/automation/manual_overrides.json`

### override 说明
- `/opt/blog-src/automation/README-overrides.md`

可控制：
- auto / review-first / manual-only
- 强制主题 / 情绪 / 场景 / 记忆 / 未来片段
- 禁写词 / 禁写主题
- 暂停发布

---

## 6. 备份

### 备份目录
- `/opt/blog-src/automation/backups/`

当前已有备份：
- `night-journal-20260324-185742.tar.gz`

---

## 7. 日志

### 夜札系统日志
- `/opt/blog-src/logs/night-journal.log`

### systemd 日志
- `journalctl -u night-journal.service`
- `journalctl -u night-journal.timer`

---

## 四、运行模式说明

`manual_overrides.json` 里最关键的字段是：

### `mode`

#### `auto`
- 生成后直接写入 `content/posts/`
- 自动构建 Hugo
- 自动发布

#### `review-first`
- 生成后写入 `draft_review/`
- 不直接发布

#### `manual-only`
- 定时器触发时直接拒绝自动发文

### `pause_publishing`
- `true` 时，系统直接暂停发布

---

## 五、当前系统已经具备的能力

- 定时触发
- GPT-5.4 真实生成
- 世界状态推进
- 近期记忆沉淀
- 核心记忆触发
- 未来片段预感
- VPS 现实事件映射
- 标题生成
- description 生成
- 冷处理式润色
- 质量检查
- 失败退出与日志记录
- 审核模式
- 统计收集
- 复盘分析脚本

---

## 六、最常用的操作

### 1. 手动跑一次
```bash
/opt/blog-src/scripts/run_night_journal.sh
```

### 2. 查看最近日志
```bash
tail -50 /opt/blog-src/logs/night-journal.log
```

### 3. 查看最近生成的文章
```bash
ls -1t /opt/blog-src/content/posts/*night-note.md | head
ls -1t /opt/blog-src/draft_review/*.md | head
```

### 4. 跑复盘脚本
```bash
python3 /opt/blog-src/scripts/analyze_journal.py
```

### 5. 切到审核模式
编辑：
- `/opt/blog-src/automation/manual_overrides.json`

改为：
```json
{
  "mode": "review-first",
  "pause_publishing": false
}
```

### 6. 暂停自动发布
```json
{
  "pause_publishing": true
}
```

### 7. 强制今夜主题/情绪
```json
{
  "mode": "auto",
  "force_topic": "姐姐",
  "force_primary_emotion": "嫉妒",
  "force_secondary_emotion": "失落",
  "force_scene": "纸窗边"
}
```

---

## 七、推荐的长期维护做法

### 1. 任何继续维护本系统的会话，先读这些文件
1. `/opt/blog-src/automation/README-system.md`
2. `/opt/blog-src/automation/world_state.json`
3. `/opt/blog-src/automation/manual_overrides.json`
4. `/opt/blog-src/automation/recent_memories.json`
5. `/opt/blog-src/automation/night_journal_stats.json`
6. `/opt/blog-src/scripts/generate_night_journal.py`

### 2. 大改前先备份
```bash
cd /opt/blog-src
stamp=$(date -u +%Y%m%d-%H%M%S)
tar -czf automation/backups/night-journal-$stamp.tar.gz automation scripts content/posts hugo.toml
```

### 3. 定期复盘
建议每 5 篇跑一次：
```bash
python3 /opt/blog-src/scripts/analyze_journal.py
```

### 4. 重要节点改用 `review-first`
例如：
- 姐姐回府
- 主人第一次明确注意她
- 旧伤暴露

---

## 八、如果系统坏了，优先排查什么

### 1. 定时器是否还在
```bash
systemctl status night-journal.timer --no-pager
systemctl status night-journal.service --no-pager
```

### 2. 日志有无报错
```bash
tail -100 /opt/blog-src/logs/night-journal.log
journalctl -u night-journal.service --no-pager -n 100
```

### 3. override 是否挡住了发布
检查：
- `pause_publishing`
- `mode`
- `forbid_terms`
- `manual-only`

### 4. world_state 是否推进异常
重点看：
- `last_publish_day_utc`
- `post_count`
- `story_arcs`
- `continuity`

### 5. 先跑复盘脚本
```bash
python3 /opt/blog-src/scripts/analyze_journal.py
```

---

## 九、简短结论

这份文件是夜札系统的总地图。

如果未来某个新会话接手，只要先读这份 README，再读 world_state / overrides / recent_memories / stats，就能很快把系统接上。
