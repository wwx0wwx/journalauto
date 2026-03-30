# 全真夜札系统：一键迁移 SOP

> 适用对象：一台全新 VPS，一套已整理好的全真夜札仓库。
> 目标：最短路径完成部署、发文、HTTPS 收口。

---

## 0. 先准备好这四样

- 域名：`<domain>`
- 仓库地址：`<repo-url>`
- OpenAI 兼容接口地址：`<base-url>`
- API Key：`<api-key>`

建议模型：
- `gpt-5.4`

---

## 1. 登录 VPS

```bash
ssh root@<server-ip>
```

---

## 2. 拉代码

```bash
rm -rf /opt/blog-src
git clone <repo-url> /opt/blog-src
```

> 当前仓库已内置 `themes/PaperMod`，**不需要** `--recurse-submodules`。

---

## 3. 初始化与环境配置

你可以选择使用**命令行向导**，或者**纯手动配置**。

### 选项 A：使用一键安装向导（极度推荐）

直接拉起全动化脚本，向导会交互式地询问你所有参数，并自动完成环境变量生成、系统依赖底座与 Nginx 安装、以及自动发文配置。

```bash
cd /opt/blog-src
bash install.sh
```

> **注意：如果使用了向导完成部署，你可以直接跳过选项 B 以及后文的第 4、5、6、7 步，直接进入最后的第 8 步验证即可！**

---

### 选项 B：纯手动环境配置

**B.1 手动拉写 `.env` 内容**

```bash
cat > /opt/blog-src/.env <<'EOF'
OPENAI_API_KEY=<api-key>
OPENAI_BASE_URL=<base-url>/chat/completions
OPENAI_MODEL=gpt-5.4
ENGINE_ROOT=/opt/blog-src
BLOG_OUTPUT_DIR=/var/www/<domain>
LOG_DIR=/opt/blog-src/logs
ENABLE_GIT_PUSH=false
LOG_LEVEL=INFO
API_TIMEOUT=150
MAX_RETRIES=3
EOF
```

**B.2 替换 `hugo.toml` 中 `baseURL`**

确认 `baseURL` 已改成目标域名，可使用下一行流：

```bash
python3 - <<'PY'
from pathlib import Path
p=Path('/opt/blog-src/hugo.toml')
s=p.read_text(encoding='utf-8')
s=s.replace('https://example.com/','https://<domain>/')
p.write_text(s,encoding='utf-8')
PY
```

## 5. 安装 Hugo（若机器太旧，直接拷已知可用版本）

先看版本：

```bash
hugo version
```

要求：
- Hugo Extended
- `>= 0.146.0`

如果系统自带版本过低，不要硬撑，直接放一份已知可用二进制到：

```bash
/usr/local/bin/hugo
```

然后确认：

```bash
/usr/local/bin/hugo version
```

---

## 6. 跑初始化部署

```bash
bash /opt/blog-src/scripts/bootstrap_server.sh <domain> /opt/blog-src
```

这一步应完成：
- 安装依赖
- 检查 `.env`
- 安装 nginx / certbot / systemd timer
- 构建博客
- 校验 `index.html`

---

## 7. 若 PaperMod 报 `google_analytics.html` 缺失

直接确认这个文件存在：

```bash
ls -l /opt/blog-src/layouts/partials/google_analytics.html
```

如果没有，补一个空垫片：

```bash
mkdir -p /opt/blog-src/layouts/partials
cat > /opt/blog-src/layouts/partials/google_analytics.html <<'EOF'
{{/* compatibility stub */}}
EOF
```

---

## 8. 本机先验证博客可构建

```bash
cd /opt/blog-src
/usr/local/bin/hugo --destination /var/www/<domain>
test -f /var/www/<domain>/index.html && echo OK
```

---

## 9. 先跑离线 dry-run

```bash
cd /opt/blog-src
python3 scripts/run.py --dry-run
```

预期：
- 成功
- 不写入正式文件
- 不请求真实 API

---

## 10. 发布第一篇文章

```bash
cd /opt/blog-src
python3 scripts/run.py
/usr/local/bin/hugo --destination /var/www/<domain>
```

检查最新文章：

```bash
ls -1 /opt/blog-src/content/posts | tail -5
```

---

## 11. 检查 Nginx 和 timer

```bash
systemctl status nginx --no-pager
systemctl status night-journal.timer --no-pager
systemctl status night-journal.service --no-pager
ss -ltnp | grep -E ':80|:443'
```

---

## 12. 开 HTTPS

```bash
certbot --nginx -d <domain> -d www.<domain> --non-interactive --agree-tos -m admin@<domain> --redirect
```

---

## 13. 最终验收

```bash
curl -I http://<domain>
curl -I https://<domain>
```

正确结果应是：
- `http://<domain>` → `301`
- `https://<domain>` → `200`

---

## 14. 若外部仍异常，优先查这几处

### A. 站内 200，外部 521 / 522
查：
- Cloudflare / CDN 回源
- 80 / 443 是否开放
- nginx 是否 active

### B. Hugo 构建失败
查：
- Hugo 版本是否过低
- `themes/PaperMod` 是否存在
- `google_analytics.html` 垫片是否存在

### C. 页面链接跳旧域名
查：
- `hugo.toml` 的 `baseURL`

### D. 发文失败
查：
- `.env` 中的 `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- 模型名是否正确

---

## 15. 一句话执行顺序

> 拉代码 → 写 `.env` → 修 `baseURL` → 确认 Hugo 版本 → 跑 `bootstrap_server.sh` → dry-run → 正式发首篇 → certbot → 验收。
