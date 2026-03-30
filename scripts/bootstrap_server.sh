#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <domain> [engine_root]"
  exit 1
fi

DOMAIN="$1"
ENGINE_ROOT="${2:-${ENGINE_ROOT:-/opt/blog-src}}"
SITE_ROOT="/var/www/${DOMAIN}"
HUGO_VER="0.147.0"

export DEBIAN_FRONTEND=noninteractive

require_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "[!] required file not found: $path"
    exit 1
  fi
}

ensure_theme() {
  local theme_dir="${ENGINE_ROOT}/themes/PaperMod"

  if [[ -d "$theme_dir" ]]; then
    return 0
  fi

  echo "[i] PaperMod theme missing, attempting to restore it..."

  if [[ -d "${ENGINE_ROOT}/.git" ]]; then
    git -C "${ENGINE_ROOT}" submodule update --init --recursive || true
  fi

  if [[ -d "$theme_dir" ]]; then
    return 0
  fi

  mkdir -p "${ENGINE_ROOT}/themes"
  git clone --depth=1 https://github.com/adityatelange/hugo-PaperMod "$theme_dir"
}

ensure_env_has_output_dir() {
  if grep -q '^BLOG_OUTPUT_DIR=' "${ENGINE_ROOT}/.env"; then
    sed -i "s|^BLOG_OUTPUT_DIR=.*|BLOG_OUTPUT_DIR=${SITE_ROOT}|" "${ENGINE_ROOT}/.env"
  else
    printf '\nBLOG_OUTPUT_DIR=%s\n' "${SITE_ROOT}" >> "${ENGINE_ROOT}/.env"
  fi
}

apt-get update
apt-get install -y git nginx python3 python3-venv python3-pip certbot python3-certbot-nginx rsync curl jq unzip

if ! command -v hugo >/dev/null 2>&1; then
  echo "[!] hugo not found in PATH"
  echo "    Please install Hugo Extended >= ${HUGO_VER} first, or copy a known-good binary to /usr/local/bin/hugo."
  exit 1
fi

if ! hugo version | grep -Eq 'v0\.(14[6-9]|1[5-9][0-9])|v[1-9][0-9]'; then
  echo "[!] Hugo version is too old for PaperMod."
  echo "    Current: $(hugo version)"
  echo "    Required: Hugo Extended >= ${HUGO_VER}"
  exit 1
fi

mkdir -p "${SITE_ROOT}" "${ENGINE_ROOT}/logs" "${ENGINE_ROOT}/draft_review" "${ENGINE_ROOT}/automation/backups"

require_file "${ENGINE_ROOT}/hugo.toml"
require_file "${ENGINE_ROOT}/automation/night-journal.service"
require_file "${ENGINE_ROOT}/automation/night-journal.timer"

if [[ ! -f "${ENGINE_ROOT}/.env" ]]; then
  echo "[!] ${ENGINE_ROOT}/.env not found"
  echo "    Copy .env.example to .env and fill real values first."
  exit 1
fi

ensure_env_has_output_dir
ensure_theme

cp "${ENGINE_ROOT}/automation/night-journal.service" /etc/systemd/system/night-journal.service
sed -i "s|WorkingDirectory=/opt/blog-src|WorkingDirectory=${ENGINE_ROOT}|" /etc/systemd/system/night-journal.service
sed -i "s|ExecStart=/opt/blog-src/scripts/run_night_journal.sh|ExecStart=${ENGINE_ROOT}/scripts/run_night_journal.sh|" /etc/systemd/system/night-journal.service
cp "${ENGINE_ROOT}/automation/night-journal.timer" /etc/systemd/system/night-journal.timer
systemctl daemon-reload
systemctl enable --now night-journal.timer

cat > "/etc/nginx/sites-available/${DOMAIN}" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};
    root ${SITE_ROOT};
    index index.html;

    charset utf-8;
    charset_types text/html text/plain text/css application/javascript application/json;

    location / {
        try_files \$uri \$uri/ /index.html;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

cd "${ENGINE_ROOT}"
sed -i "s|^baseURL = .*|baseURL = \"https://${DOMAIN}/\"|" "${ENGINE_ROOT}/hugo.toml"
hugo --destination "${SITE_ROOT}"

if [[ ! -f "${SITE_ROOT}/index.html" ]]; then
  echo "[!] Hugo build finished but ${SITE_ROOT}/index.html is missing"
  exit 1
fi

echo
printf '%s\n' "[ok] Bootstrap complete for ${DOMAIN}"
printf '%s\n' "[ok] Blog output: ${SITE_ROOT}"
printf '%s\n' "[next] If DNS is ready, enable HTTPS with:"
printf 'certbot --nginx -d %s -d www.%s --non-interactive --agree-tos -m admin@%s --redirect\n' "${DOMAIN}" "${DOMAIN}" "${DOMAIN}"
