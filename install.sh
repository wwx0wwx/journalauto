#!/usr/bin/env bash
set -e

# Require root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Try: sudo bash $0"
   exit 1
fi

ENGINE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export ENGINE_ROOT
cd "$ENGINE_ROOT"

echo "=========================================================="
echo "          全真夜札引擎 - 交互式一键部署向导               "
echo "=========================================================="
echo ""

# 1. 域名收集
read -p "[1/5] 请输入分配给本站的域名 (例: example.com): " DOMAIN
if [[ -z "$DOMAIN" ]]; then
    echo "⚠️ 域名不能为空，安装已中止。"
    exit 1
fi

# 2. 核心私密配置 (API)
read -s -p "[2/5] 请粘贴你的 OpenAI (兼容) API Key: " API_KEY
echo ""
if [[ -z "$API_KEY" ]]; then
    echo "⚠️ API Key 不能为空，安装已中止。"
    exit 1
fi

# 3. 基础地址覆盖
read -p "[3/5] 请输入 API Endpoint (留空默认: https://api.openai.com/v1/chat/completions): " BASE_URL
BASE_URL=${BASE_URL:-https://api.openai.com/v1/chat/completions}

# 4. 模型名称
read -p "[4/5] 请输入使用的模型名称 (留空默认: gpt-5.4): " MODEL_NAME
MODEL_NAME=${MODEL_NAME:-gpt-5.4}

# 5. Timer 选项
echo ""
echo "[5/5] 请选择“全真”自感知生成的常规频次（系统定时器）："
echo "  1) [默认] 每周三次 (北京时间深夜/UTC 16点触发)"
echo "  2) [激进] 每日一札 (每天 UTC 16点触发)"
echo "  3) [静音] 暂不启用自动触发（后续可自行在 automation/ 中配置并重启 service）"
read -p "选择对应的数字 (默认填 1): " SCHEDULE_CHOICE

SCHEDULE_STR="OnCalendar=Tue,Thu,Sat *-*-* 16:00:00 UTC" # fallback default
case "$SCHEDULE_CHOICE" in
    2) SCHEDULE_STR="OnCalendar=*-*-* 16:00:00 UTC" ;;
    3) SCHEDULE_STR="OnCalendar=" ;;
    *) SCHEDULE_STR="OnCalendar=Tue,Thu,Sat *-*-* 16:00:00 UTC" ;;
esac

echo ""
echo "[i] ====== 前置参数采集完毕，开始无人值守初始化 ======"
echo ""

# A. 灌入环境变量
echo "[i] 生成核心依赖 .env"
cat > "$ENGINE_ROOT/.env" <<EOF
OPENAI_API_KEY=$API_KEY
OPENAI_BASE_URL=$BASE_URL
OPENAI_MODEL=$MODEL_NAME
ENGINE_ROOT=$ENGINE_ROOT
BLOG_OUTPUT_DIR=/var/www/$DOMAIN
LOG_DIR=$ENGINE_ROOT/logs
ENABLE_GIT_PUSH=false
LOG_LEVEL=INFO
API_TIMEOUT=150
MAX_RETRIES=3
EOF
chmod 600 "$ENGINE_ROOT/.env"

# B. 修改 systemd 文件的时间轴
echo "[i] 重写 Systemd 定时规则..."
TIMER_FILE="$ENGINE_ROOT/automation/night-journal.timer"
if [[ -f "$TIMER_FILE" ]]; then
    # 由于原始文本含有 OnCalendar=，我们通过 SED 替换整行
    # 若选择了不启用，则我们仅仅注释掉当前配置或设为空 (Systemd 有些版本不支持空，所以我们注释)
    if [[ -z "$SCHEDULE_STR" || "$SCHEDULE_CHOICE" == "3" ]]; then
        sed -i "s/^OnCalendar=.*/# OnCalendar= (已在安装中禁用)/g" "$TIMER_FILE"
    else
        sed -i "s/^OnCalendar=.*/$SCHEDULE_STR/g" "$TIMER_FILE"
    fi
fi

# C. 执行核心建站
echo "[i] 移交核心引导进程 bootstrap_server.sh ... "
bash "$ENGINE_ROOT/scripts/bootstrap_server.sh" "$DOMAIN"

# D. 模拟发文测试 API 和运行时
echo ""
echo "[i] 跑通本地链路（模拟状态 dry-run）："
python3 "$ENGINE_ROOT/scripts/run.py" --dry-run || {
    echo "⚠️ 离线连通模拟测出异常预警，系统已架构起外部页面，但文章引擎跑不通。"
    echo "请检查你的 API 配置、网络代理条件或 Python 版本支持。"
    exit 1
}

echo ""
echo "=========================================================="
echo "🎯  [ 核心装配大功告成 ] 🎯"
echo "=========================================================="
echo "当前外部暴露初始站已生成: http://$DOMAIN"
echo ""
echo "待 DNS 生效稳定后，请最后执行回环收口开启小锁 (HTTPS)："
echo "  certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN --redirect"
echo ""
echo "一切已就绪，向导结束！"
exit 0
