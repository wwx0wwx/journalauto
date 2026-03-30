# 全真夜札系统：最终迁移清单

> 用途：把一套已经跑通的全真夜札博客，迁移到一台全新的 VPS，并避免本次实战里踩过的坑。

---

## 一、迁移前确认

### 1. 机器与域名
- [ ] VPS 可 SSH 登录
- [ ] 域名已解析到目标机器 IP
- [ ] Cloudflare / 代理模式已确认（若开代理，回源 80/443 必须通）

### 2. 仓库与代码
- [ ] 使用 **最新稳定版本**（建议 `v1.0.4` 或之后）
- [ ] 仓库已内置 `themes/PaperMod`
- [ ] 不再依赖 submodule
- [ ] 普通 `git clone` 即可

### 3. 密钥与配置
- [ ] 已准备好 `OPENAI_API_KEY`
- [ ] 已确认 `OPENAI_BASE_URL`
- [ ] 已确认模型名（如 `gpt-5.4`）
- [ ] 已准备好部署域名（如 `siecan.de`）

---

## 二、代码部署

### 1. 获取代码
```bash
git clone <repo-url> /opt/blog-src
```

### 2. 写入 `.env`
```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://ai.dooo.ng/v1/chat/completions
OPENAI_MODEL=gpt-5.4
ENGINE_ROOT=/opt/blog-src
BLOG_OUTPUT_DIR=/var/www/<domain>
LOG_DIR=/opt/blog-src/logs
ENABLE_GIT_PUSH=false
LOG_LEVEL=INFO
API_TIMEOUT=150
MAX_RETRIES=3
```

### 3. 确认目录
- [ ] `/opt/blog-src` 存在
- [ ] `/var/www/<domain>` 可写
- [ ] `/opt/blog-src/logs` 可写
- [ ] `/opt/blog-src/draft_review` 可写

---

## 三、Hugo 主链检查（重点）

### 1. Hugo 版本
- [ ] `hugo version` >= `0.146.0`
- [ ] 必须是 **extended** 版本

> 本次实战踩坑：Ubuntu 自带 Hugo 过低（0.123.x），会导致 PaperMod 直接构建失败。

### 2. 主题检查
- [ ] `themes/PaperMod` 存在
- [ ] `layouts/partials/google_analytics.html` 存在（兼容垫片）

> 本次实战踩坑：远端构建时报 `partial "google_analytics.html" not found`，已通过空 partial 修复。

### 3. baseURL
- [ ] `hugo.toml` 中 `baseURL` 已改为目标域名
- [ ] 不残留旧域名（如历史部署中曾使用过的旧域名）

> 本次实战踩坑：回滚版遗留旧域名，需在部署时替换为新域名。

---

## 四、初始化部署

执行：
```bash
bash /opt/blog-src/scripts/bootstrap_server.sh <domain> /opt/blog-src
```

脚本应完成：
- [ ] 安装基础依赖
- [ ] 检查 `.env`
- [ ] 安装 / 使用可用 Hugo
- [ ] 创建 Nginx 配置
- [ ] 安装 systemd timer/service
- [ ] 首次构建博客
- [ ] 校验 `index.html`

---

## 五、发文链验证

### 1. 先跑离线 dry-run
```bash
cd /opt/blog-src
python3 scripts/run.py --dry-run
```

预期：
- [ ] 成功返回模拟标题
- [ ] 不写入正式文章
- [ ] 不请求真实模型 API

### 2. 再跑真实发文
```bash
cd /opt/blog-src
python3 scripts/run.py
```

预期：
- [ ] 在 `content/posts/` 下生成新文章
- [ ] 标题、分类、主题输出正常
- [ ] Hugo 重建成功

---

## 六、站点联通性检查

### 1. 本机检查
```bash
curl -I http://127.0.0.1
curl -I http://<domain>
```

预期：
- [ ] 返回 200 或后续 HTTPS 跳转

### 2. Nginx 检查
```bash
systemctl status nginx --no-pager
ss -ltnp | grep -E ':80|:443'
```

预期：
- [ ] nginx active (running)
- [ ] 80 / 443 正常监听

### 3. systemd 检查
```bash
systemctl status night-journal.timer --no-pager
systemctl status night-journal.service --no-pager
systemctl list-timers --all | grep night-journal
```

预期：
- [ ] timer 已启用
- [ ] service 可被触发

---

## 七、HTTPS 收口

执行：
```bash
certbot --nginx -d <domain> -d www.<domain> --non-interactive --agree-tos -m admin@<domain> --redirect
```

预期：
- [ ] 证书签发成功
- [ ] HTTP 自动跳转 HTTPS
- [ ] `https://<domain>` 返回 200

> 本次实战踩坑：站点先前已通 HTTP，但外部一度出现 521。最终通过 Nginx 正常回源 + certbot 收口恢复稳定。

---

## 八、最终验收

### 必须全部满足
- [ ] 仓库为最新稳定版
- [ ] Hugo 构建成功
- [ ] 第一篇文章生成成功
- [ ] `http://<domain>` 自动跳 HTTPS
- [ ] `https://<domain>` 返回 200
- [ ] `night-journal.timer` 已启用
- [ ] 日志目录正常写入
- [ ] 不再依赖 submodule
- [ ] 远端不残留旧域名配置

---

## 九、部署后建议

- [ ] 备份 `/opt/blog-src/.env`
- [ ] 备份 `/opt/blog-src/automation/*.json`
- [ ] 备份 `/etc/nginx/sites-available/<domain>`
- [ ] 定期检查 `/var/log/letsencrypt/letsencrypt.log`
- [ ] 首次观察 1~2 次定时发文结果

---

## 十、一句话版

迁移时最容易出问题的，不是 Python，而是这四处：

1. **Hugo 版本过低**
2. **主题兼容 / partial 缺失**
3. **旧域名残留在 `hugo.toml`**
4. **HTTPS 最后一步没收口**

先把这四处钉死，系统就稳了。
