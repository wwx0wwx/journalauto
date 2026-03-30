from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class VpsSignals:
    uptime_days: int
    load1: float
    mem_pct: int
    ssh_bad: int
    disk_pct: int
    nginx_hits: int
    service_restart_hits: int
    cert_hits: int


def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, text=True, capture_output=True).stdout.strip()


def collect_vps_signals() -> VpsSignals:
    uptime_out = sh("awk '{print int($1)}' /proc/uptime")
    uptime_days = int(uptime_out) // 86400 if uptime_out else 0
    load_out = sh("cut -d' ' -f1 /proc/loadavg")
    load1 = float(load_out) if load_out else 0.0
    mem_out = sh("free -m | awk '/Mem:/ {printf \"%d\", ($3*100)/$2}'")
    mem_pct = int(mem_out) if mem_out else 0
    ssh_bad = int(sh("journalctl --since '24 hours ago' 2>/dev/null | egrep -ci 'Failed password|Invalid user|authentication failure' || true") or 0)
    disk_pct = int(sh("df -P / | awk 'NR==2 {print int($5)}' | tr -d '%' ") or 0)
    nginx_hits = int(sh("find /var/log/nginx -type f -name '*access*.log' -mtime -1 -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || true") or 0)
    service_restart_hits = int(sh("journalctl --since '24 hours ago' 2>/dev/null | egrep -ci 'Started|Restarted' || true") or 0)
    cert_hits = int(sh("grep -Rchi 'Cert not yet due for renewal|Congratulations' /var/log/letsencrypt 2>/dev/null || true") or 0)
    return VpsSignals(
        uptime_days=uptime_days,
        load1=load1,
        mem_pct=mem_pct,
        ssh_bad=ssh_bad,
        disk_pct=disk_pct,
        nginx_hits=nginx_hits,
        service_restart_hits=service_restart_hits,
        cert_hits=cert_hits,
    )
