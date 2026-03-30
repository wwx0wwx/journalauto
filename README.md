# 全真夜札引擎

一个具有连续性、生命感和剧情推进能力的角色叙事引擎，作为持续运转的 Hugo 博客系统。

## 功能特性

- **角色驱动**：核心角色「全真」，常年立于暗处守护主人的暗卫
- **情感层次**：隐忍、痴忠、清冷，对「姐姐」宿命般的嫉妒
- **文风控制**：极简、古风，动作代替心理，场景白描传递情绪
- **状态管理**：世界状态机驱动长期关系弧线（主人疲惫度、姐姐归期、全真嫉妒值等）
- **记忆系统**：多维记忆库（核心锚点 / 滚动记忆 / 未来预感）
- **现实映射**：VPS 运维数据 → 江湖意象（SSH 拦截 → 宵小夜闯，负载 → 堂上风雨）
- **智能生成**：调用 OpenAI 兼容接口生成文本
- **质量控制**：长度 / 禁词 / 模板化 / 重复度四重检查
- **发布管理**：支持 auto / review / manual-only 三种模式

## 技术架构

### 三层架构

| 层 | 职责 | 实现 |
|---|---|---|
| 站点层 | 博客展示 | Hugo + Nginx，输出到 `/var/www/<domain>` |
| 引擎层 | 核心逻辑 | Python 包 `night_journal/` |
| 调度层 | 定时触发 | systemd timer (`night-journal.timer`) |

### 引擎模块划分

```text
night_journal/
├── inputs/          # 输入层：状态读取、素材加载、VPS 信号、近期文章
├── narrative/       # 叙事层：选题、选素材、选记忆、未来预感、剧情弧线
├── generation/      # 生成层：prompt 构建、LLM 调用、正文润色、标题 description
├── quality/         # 质检层：质量门禁、发布守卫
├── publishing/      # 发布层：Markdown 构建、模式路由、Hugo 构建、git 推送
└── analysis/        # 分析层：复盘统计、报告生成
```

## 部署原则

- **主方案始终是 Hugo 博客**
- **静态页不是默认方案，只能作为故障兜底**
- 主题 `themes/PaperMod` 已 vendored 入仓库，部署时不再依赖 submodule

## 快速部署

### 1. 拉取代码

当前仓库已内置 `themes/PaperMod`，普通 clone 即可：

```bash
git clone <repo-url> /opt/blog-src
```

### 2. 执行一键安装向导（推荐）

直接运行交互式部署脚本，向导会自动完成环境配置、依赖安装和定时发文设定：

```bash
bash /opt/blog-src/install.sh
```

### 3. 手动部署流程（可选）

如果你不希望使用交互流程，可以完全手动配置：

**3.1 配置环境变量**
复制 `.env.example` 为 `.env`，填入相关信息：

```bash
cp /opt/blog-src/.env.example /opt/blog-src/.env
```
重点需改字段：
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `ENGINE_ROOT`
- `BLOG_OUTPUT_DIR`

**3.2 执行底层初始化脚本**

```bash
bash /opt/blog-src/scripts/bootstrap_server.sh <domain>
```

例如：
```bash
bash /opt/blog-src/scripts/bootstrap_server.sh example.com
```

脚本会完成：
- 自动补齐 `themes/PaperMod` 和系统依赖
- 创建发布目录与 Nginx 配置
- 安装 systemd service/timer 守护进程

### 4. 启用 HTTPS

```bash
certbot --nginx -d <domain> -d www.<domain> --non-interactive --agree-tos -m admin@<domain> --redirect
```

### 5. 验证博客主链

```bash
systemctl status night-journal.timer --no-pager
systemctl status night-journal.service --no-pager
hugo version
curl -I http://<domain>
curl -I https://<domain>
test -f /var/www/<domain>/index.html && echo OK
```

## 运行模式

- `auto`：自动生成并发布到 `content/posts`
- `review`：生成后存入 `draft_review` 待审
- `manual-only`：禁止自动发布

## 手动运行

```bash
# 自动模式（直接发布）
python scripts/run.py

# 审稿模式（存草稿）
python scripts/run.py --mode review

# 指定项目根目录
python scripts/run.py --root /path/to/blog

# 强制指定主题
python scripts/run.py --force-topic "守夜"

# 试运行（离线 mock，不写入文件）
python scripts/run.py --dry-run
```

> `--dry-run` 现在会自动切到 `manual-only` + `MOCK_LLM=true`，不会写入最终文章，也不会请求真实模型接口。

## 文件结构

```text
/opt/blog-src/
├── scripts/
│   ├── run.py
│   ├── generate_night_journal.py
│   └── health_check.py
├── automation/
│   ├── world_state.json
│   ├── manual_overrides.json
│   ├── *.json
│   └── night-journal.timer / night-journal.service
├── content/posts/
├── draft_review/
├── logs/
├── themes/PaperMod/
├── hugo.toml
└── .env
```

## 维护与复盘

- `scripts/analyze_journal.py`：统计发文成功率、高频意象、情绪分布、剧情进度
- `scripts/health_check.py`：检查 API 连接、文件权限、磁盘空间等
- 日志：`/opt/blog-src/logs/night-journal.log`

## 部署文档导航

按使用场景看：

- `DEPLOY_SOP.md`：最短路径的一键迁移 SOP，适合直接照着做
- `DEPLOY_FINAL_CHECKLIST.md`：最终验收与避坑清单，适合部署后逐项勾检
- `DEPLOY_EXAMPLE.md`：完整迁移样例，适合复盘或第一次搭建时参考
