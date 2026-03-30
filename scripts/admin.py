#!/usr/bin/env python3
"""Modern web admin panel for night-journal engine with JSON API.

Usage:
    python scripts/admin.py [--port 8765] [--root /opt/blog-src]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

from night_journal.config import load_settings
from night_journal.inputs.state_store import StateStore


# ---------------------------------------------------------------------------
# Settings singleton
# ---------------------------------------------------------------------------
_settings = None


def get_settings(root: Path = None):
    global _settings
    if _settings is None:
        _settings = load_settings(root or project_root)
    return _settings


# ---------------------------------------------------------------------------
# Helpers: personas
# ---------------------------------------------------------------------------

def _personas_dir(settings) -> Path:
    return settings.automation_dir / 'personas'


def _active_persona_name(settings) -> str:
    f = settings.automation_dir / 'active_persona'
    if f.exists():
        return f.read_text(encoding='utf-8').strip()
    return ''


def _list_personas(settings) -> list[dict]:
    pdir = _personas_dir(settings)
    active = _active_persona_name(settings)
    result = []
    if pdir.exists():
        for d in sorted(pdir.iterdir()):
            if d.is_dir():
                result.append({'name': d.name, 'active': d.name == active})
    return result


def _read_persona(settings, name: str) -> dict | None:
    pdir = _personas_dir(settings) / name
    if not pdir.is_dir():
        return None
    md_path = pdir / 'persona.md'
    json_path = pdir / 'persona.json'
    return {
        'md': md_path.read_text(encoding='utf-8') if md_path.exists() else '',
        'json': json.loads(json_path.read_text(encoding='utf-8')) if json_path.exists() else {},
    }


def _save_persona(settings, name: str, md: str, data: dict) -> None:
    pdir = _personas_dir(settings) / name
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / 'persona.md').write_text(md, encoding='utf-8')
    (pdir / 'persona.json').write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


def _delete_persona(settings, name: str) -> None:
    pdir = _personas_dir(settings) / name
    if pdir.is_dir():
        shutil.rmtree(pdir)


def _switch_persona(settings, name: str) -> None:
    (settings.automation_dir / 'active_persona').write_text(name, encoding='utf-8')
    src_md = _personas_dir(settings) / name / 'persona.md'
    src_json = _personas_dir(settings) / name / 'persona.json'
    if src_md.exists():
        (settings.automation_dir / 'persona.md').write_text(
            src_md.read_text(encoding='utf-8'), encoding='utf-8'
        )
    if src_json.exists():
        (settings.automation_dir / 'persona.json').write_text(
            src_json.read_text(encoding='utf-8'), encoding='utf-8'
        )


# ---------------------------------------------------------------------------
# Helpers: publishers
# ---------------------------------------------------------------------------

def _publishers_file(settings) -> Path:
    return settings.automation_dir / 'publishers.json'


def _load_publishers(settings) -> list:
    f = _publishers_file(settings)
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    return []


def _save_publishers(settings, data: list) -> None:
    _publishers_file(settings).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ---------------------------------------------------------------------------
# Helpers: api settings
# ---------------------------------------------------------------------------

def _api_settings_file(settings) -> Path:
    return settings.automation_dir / 'api_settings.json'


def _load_api_settings(settings) -> dict:
    f = _api_settings_file(settings)
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    return {'api_key': '', 'base_url': '', 'model': '', 'model_fast': ''}


def _save_api_settings(settings, data: dict) -> None:
    existing = _load_api_settings(settings)
    if data.get('api_key', '').strip('*') == '':
        data['api_key'] = existing.get('api_key', '')
    _api_settings_file(settings).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ---------------------------------------------------------------------------
# Helpers: schedule
# ---------------------------------------------------------------------------

def _schedule_file(settings) -> Path:
    return settings.automation_dir / 'schedule.json'


def _load_schedule(settings) -> dict:
    f = _schedule_file(settings)
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    return {}


def _save_schedule(settings, data: dict) -> None:
    _schedule_file(settings).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ---------------------------------------------------------------------------
# Helpers: overrides
# ---------------------------------------------------------------------------

def _overrides_file(settings) -> Path:
    return settings.automation_dir / 'manual_overrides.json'


def _load_overrides(settings) -> dict:
    f = _overrides_file(settings)
    if f.exists():
        return json.loads(f.read_text(encoding='utf-8'))
    return {}


def _save_overrides(settings, data: dict) -> None:
    _overrides_file(settings).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
    )


# ---------------------------------------------------------------------------
# JSON API Handler
# ---------------------------------------------------------------------------

def _json_response(data: dict, status: int = 200) -> tuple[bytes, str]:
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    return body, 'application/json'


def _error_response(message: str, status: int = 400) -> tuple[bytes, str]:
    return _json_response({'error': message}, status)


class AdminAPIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        settings = get_settings()

        # API routes
        if path == '/api/personas':
            data = _list_personas(settings)
            body, ctype = _json_response({'personas': data})
        elif path == '/api/personas/active':
            name = _active_persona_name(settings)
            body, ctype = _json_response({'active': name})
        elif path.startswith('/api/personas/') and path.endswith('/detail'):
            name = path.split('/')[-2]
            persona = _read_persona(settings, name)
            if persona is None:
                body, ctype = _error_response('Persona not found', 404)
            else:
                body, ctype = _json_response({'name': name, **persona})
        elif path == '/api/publishers':
            data = _load_publishers(settings)
            body, ctype = _json_response({'publishers': data})
        elif path == '/api/schedule':
            data = _load_schedule(settings)
            body, ctype = _json_response(data)
        elif path == '/api/overrides':
            data = _load_overrides(settings)
            body, ctype = _json_response(data)
        elif path == '/api/api-settings':
            data = _load_api_settings(settings)
            # Mask api_key for display
            if data.get('api_key'):
                data['api_key'] = data['api_key'][:8] + '****'
            body, ctype = _json_response(data)
        elif path == '/api/state':
            store = StateStore(settings.automation_dir)
            state = store.load_world_state()
            body, ctype = _json_response({'state': state})
        elif path.startswith('/api/drafts'):
            from pathlib import Path
            draft_dir = settings.automation_dir / 'draft_review'
            if not draft_dir.exists():
                body, ctype = _json_response({'drafts': []})
            else:
                files = sorted(draft_dir.glob('*.md'), reverse=True)
                drafts = [{'name': f.name, 'size': f.stat().st_size} for f in files]
                body, ctype = _json_response({'drafts': drafts})
        elif path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(_INDEX_HTML.encode('utf-8'))
            return
        else:
            body, ctype = _error_response('Not found', 404)

        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        settings = get_settings()

        content_length = int(self.headers.get('Content-Length', 0))
        body_data = self.rfile.read(content_length) if content_length > 0 else b''
        try:
            data = json.loads(body_data.decode('utf-8')) if body_data else {}
        except json.JSONDecodeError:
            data = {}

        # Parse query params for POST
        qparams = parse_qs(parsed.query)

        try:
            if path == '/api/personas':
                # Create new persona
                name = data.get('name', '').strip()
                if not name:
                    body, ctype, status = _error_response('Name required')
                else:
                    # Copy from quanzhen as template if exists
                    default_name = 'quanzhen'
                    src = _personas_dir(settings) / default_name
                    dst = _personas_dir(settings) / name
                    if src.exists() and not dst.exists():
                        shutil.copytree(src, dst)
                    _save_persona(settings, name, data.get('md', ''), data.get('json', {}))
                    body, ctype = _json_response({'success': True, 'name': name})
            elif path.startswith('/api/personas/') and path.endswith('/save'):
                name = path.split('/')[-2]
                _save_persona(settings, name, data.get('md', ''), data.get('json', {}))
                body, ctype = _json_response({'success': True})
            elif path.startswith('/api/personas/') and path.endswith('/activate'):
                name = path.split('/')[-2]
                _switch_persona(settings, name)
                body, ctype = _json_response({'success': True, 'active': name})
            elif path.startswith('/api/personas/') and path.endswith('/delete'):
                name = path.split('/')[-2]
                _delete_persona(settings, name)
                body, ctype = _json_response({'success': True})
            elif path == '/api/publishers':
                _save_publishers(settings, data.get('publishers', []))
                body, ctype = _json_response({'success': True})
            elif path == '/api/schedule':
                _save_schedule(settings, data)
                body, ctype = _json_response({'success': True})
            elif path == '/api/overrides':
                _save_overrides(settings, data)
                body, ctype = _json_response({'success': True})
            elif path == '/api/api-settings':
                _save_api_settings(settings, data)
                body, ctype = _json_response({'success': True})
            elif path == '/api/api-settings/test':
                # Test API connection
                api_data = _load_api_settings(settings)
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        api_data.get('base_url', '') + '/models',
                        headers={'Authorization': f"Bearer {api_data.get('api_key', '')}"}
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        body, ctype = _json_response({'success': True, 'message': 'Connection OK'})
                except Exception as e:
                    body, ctype = _json_response({'success': False, 'error': str(e)})
            elif path == '/api/generate':
                # Trigger generation (async, return immediately)
                mode = data.get('mode', 'auto')
                topic = data.get('topic', '')
                overrides = _load_overrides(settings)
                if mode:
                    overrides['mode_override'] = mode
                if topic:
                    overrides['force_topic'] = topic
                _save_overrides(settings, overrides)
                body, ctype = _json_response({'success': True, 'message': f'Generation started in {mode} mode'})
            elif path.startswith('/api/drafts/'):
                # Get draft content
                filename = path.split('/')[-1]
                draft_dir = settings.automation_dir / 'draft_review'
                fpath = draft_dir / filename
                if fpath.exists():
                    content = fpath.read_text(encoding='utf-8')
                    body, ctype = _json_response({'name': filename, 'content': content})
                else:
                    body, ctype = _error_response('Draft not found', 404)
            else:
                body, ctype, status = _error_response('Not found', 404)
                self.send_response(status)
                self.send_header('Content-Type', ctype)
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_response(200)
            self.send_header('Content-Type', ctype + '; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)

        except Exception as e:
            error_msg = traceback.format_exc()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e), 'trace': error_msg}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


# ---------------------------------------------------------------------------
# Modern Vue 3 + Picnic CSS Frontend
# ---------------------------------------------------------------------------

_INDEX_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Night Journal Admin</title>
  <link rel="stylesheet" href="https://unpkg.com/picnic-css@2.4.0/picnic.min.css">
  <style>
    :root {
      --primary: #4a90d9;
      --success: #27ae60;
      --danger: #e74c3c;
      --warning: #f39c12;
      --dark: #2c3e50;
      --light: #ecf0f1;
    }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f6fa; margin: 0; }
    .app-container { display: flex; min-height: 100vh; }
    .sidebar {
      width: 220px;
      background: var(--dark);
      color: white;
      padding: 20px 0;
      flex-shrink: 0;
    }
    .sidebar h1 {
      font-size: 1.2rem;
      margin: 0 0 30px 20px;
      color: var(--primary);
      border-bottom: 1px solid #34495e;
      padding-bottom: 15px;
    }
    .nav-item {
      padding: 12px 20px;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .nav-item:hover { background: #34495e; }
    .nav-item.active { background: var(--primary); }
    .nav-item svg { width: 18px; height: 18px; }
    .main-content {
      flex: 1;
      padding: 30px;
      overflow-y: auto;
    }
    .page-header {
      margin-bottom: 25px;
    }
    .page-header h2 {
      margin: 0 0 5px 0;
      color: var(--dark);
    }
    .page-header p { margin: 0; color: #7f8c8d; font-size: 0.9rem; }
    .card {
      background: white;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
      padding: 20px;
      margin-bottom: 20px;
    }
    .card h3 { margin: 0 0 15px 0; color: var(--dark); border-bottom: 1px solid #eee; padding-bottom: 10px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: 600; color: #555; }
    .form-group input, .form-group select, .form-group textarea {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 14px;
      box-sizing: border-box;
    }
    .form-group textarea { min-height: 120px; font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; }
    .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; transition: all 0.2s; }
    .btn-primary { background: var(--primary); color: white; }
    .btn-primary:hover { background: #357abd; }
    .btn-success { background: var(--success); color: white; }
    .btn-success:hover { background: #219a52; }
    .btn-danger { background: var(--danger); color: white; }
    .btn-danger:hover { background: #c0392b; }
    .btn-warning { background: var(--warning); color: white; }
    .btn-warning:hover { background: #d68910; }
    .btn-outline { background: transparent; border: 1px solid #ddd; color: #555; }
    .btn-outline:hover { background: #f5f5f5; }
    .btn-sm { padding: 5px 10px; font-size: 12px; }
    .flex { display: flex; }
    .flex-between { justify-content: space-between; }
    .flex-gap { gap: 10px; }
    .items-center { align-items: center; }
    .mb-1 { margin-bottom: 10px; }
    .mb-2 { margin-bottom: 20px; }
    .msg-box { padding: 10px 15px; border-radius: 4px; margin-top: 10px; display: none; }
    .msg-box.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .msg-box.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .persona-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px; }
    .persona-item {
      padding: 10px 15px;
      background: #f8f9fa;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .persona-item:hover { background: #e9ecef; }
    .persona-item.active { background: var(--primary); color: white; }
    .persona-item .badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
    .persona-item .badge.active { background: var(--success); color: white; }
    .publisher-card {
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 15px;
    }
    .publisher-card.enabled { border-color: var(--success); background: #f8fff8; }
    .publisher-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
    .publisher-header h4 { margin: 0; }
    .toggle-switch { position: relative; width: 50px; height: 26px; }
    .toggle-switch input { opacity: 0; width: 0; height: 0; }
    .toggle-slider {
      position: absolute;
      cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background: #ccc;
      transition: 0.3s;
      border-radius: 26px;
    }
    .toggle-slider:before {
      position: absolute;
      content: "";
      height: 20px;
      width: 20px;
      left: 3px;
      bottom: 3px;
      background: white;
      transition: 0.3s;
      border-radius: 50%;
    }
    .toggle-switch input:checked + .toggle-slider { background: var(--success); }
    .toggle-switch input:checked + .toggle-slider:before { transform: translateX(24px); }
    .mode-selector { display: flex; gap: 10px; margin-bottom: 20px; }
    .mode-option {
      flex: 1;
      padding: 15px;
      border: 2px solid #ddd;
      border-radius: 8px;
      cursor: pointer;
      text-align: center;
      transition: all 0.2s;
    }
    .mode-option:hover { border-color: var(--primary); }
    .mode-option.selected { border-color: var(--primary); background: #f0f7ff; }
    .mode-option h4 { margin: 0 0 5px 0; }
    .mode-option p { margin: 0; font-size: 12px; color: #777; }
    .day-selector { display: flex; gap: 8px; flex-wrap: wrap; }
    .day-chip {
      padding: 6px 14px;
      border: 1px solid #ddd;
      border-radius: 20px;
      cursor: pointer;
      font-size: 13px;
      transition: all 0.2s;
    }
    .day-chip:hover { border-color: var(--primary); }
    .day-chip.selected { background: var(--primary); color: white; border-color: var(--primary); }
    .editor-tabs { display: flex; gap: 0; margin-bottom: 0; }
    .editor-tab {
      padding: 8px 20px;
      background: #eee;
      cursor: pointer;
      border: 1px solid #ddd;
      border-bottom: none;
      border-radius: 4px 4px 0 0;
    }
    .editor-tab.active { background: white; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .json-editor { font-family: 'Monaco', 'Menlo', monospace; font-size: 13px; min-height: 300px; }
    .toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      padding: 12px 20px;
      background: var(--dark);
      color: white;
      border-radius: 4px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 1000;
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.3s;
    }
    .toast.show { transform: translateY(0); opacity: 1; }
    .toast.success { background: var(--success); }
    .toast.error { background: var(--danger); }
    .spinner {
      display: inline-block;
      width: 20px;
      height: 20px;
      border: 2px solid #f3f3f3;
      border-top: 2px solid var(--primary);
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
  </style>
</head>
<body>
<div id="app" class="app-container">
  <!-- Sidebar -->
  <nav class="sidebar">
    <h1>Night Journal</h1>
    <div class="nav-item" :class="{active: currentPage === 'generate'}" @click="currentPage = 'generate'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5,3 19,12 5,21"/></svg>
      立即生成
    </div>
    <div class="nav-item" :class="{active: currentPage === 'personas'}" @click="currentPage = 'personas'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
      角色管理
    </div>
    <div class="nav-item" :class="{active: currentPage === 'api'}" @click="currentPage = 'api'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
      AI 接口
    </div>
    <div class="nav-item" :class="{active: currentPage === 'publishers'}" @click="currentPage = 'publishers'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
      发布平台
    </div>
    <div class="nav-item" :class="{active: currentPage === 'schedule'}" @click="currentPage = 'schedule'">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      定时发送
    </div>
  </nav>

  <!-- Main Content -->
  <main class="main-content">
    <!-- Generate Page -->
    <div v-if="currentPage === 'generate'">
      <div class="page-header">
        <h2>立即生成</h2>
        <p>手动触发生成一篇文章</p>
      </div>
      <div class="card">
        <div class="form-group">
          <label>运行模式</label>
          <select v-model="generateMode">
            <option value="auto">auto（自动发布）</option>
            <option value="review">review（存草稿）</option>
            <option value="manual-only">manual-only（仅手动）</option>
            <option value="debug">debug（调试，不写文件）</option>
          </select>
        </div>
        <div class="form-group">
          <label>指定主题（可选）</label>
          <input type="text" v-model="generateTopic" placeholder="留空则自动选择">
        </div>
        <button class="btn btn-primary" @click="triggerGenerate" :disabled="generating">
          <span v-if="generating" class="spinner"></span>
          <span v-else>开始生成</span>
        </button>
        <div v-if="generateMsg" class="msg-box" :class="generateMsgType">{{ generateMsg }}</div>
      </div>
    </div>

    <!-- Personas Page -->
    <div v-if="currentPage === 'personas'">
      <div class="page-header">
        <h2>角色管理</h2>
        <p>管理人物 Prompt 配置</p>
      </div>
      <div class="flex flex-gap mb-2">
        <input type="text" v-model="newPersonaName" placeholder="新角色名称（英文/拼音）" style="flex:1">
        <button class="btn btn-primary" @click="createPersona">新建角色</button>
      </div>
      <div class="persona-list">
        <div
          v-for="p in personas"
          :key="p.name"
          class="persona-item"
          :class="{active: p.active}"
          @click="selectPersona(p.name)"
        >
          <span>{{ p.name }}</span>
          <span v-if="p.active" class="badge active">已激活</span>
        </div>
      </div>
      <div v-if="selectedPersona" class="card">
        <h3>编辑角色：{{ selectedPersona }}</h3>
        <div class="editor-tabs">
          <div class="editor-tab" :class="{active: personaTab === 'json'}" @click="personaTab = 'json'">persona.json</div>
          <div class="editor-tab" :class="{active: personaTab === 'md'}" @click="personaTab = 'md'">persona.md (Prompt)</div>
        </div>
        <div style="border: 1px solid #ddd; padding: 15px; border-top: none;">
          <div v-if="personaTab === 'json'" class="tab-content active">
            <textarea
              class="json-editor"
              v-model="editPersonaJson"
              placeholder="persona.json"
            ></textarea>
          </div>
          <div v-if="personaTab === 'md'" class="tab-content active">
            <textarea
              style="min-height: 350px; font-family: monospace;"
              v-model="editPersonaMd"
              placeholder="persona.md (Prompt 模板)"
            ></textarea>
          </div>
        </div>
        <div class="flex flex-between items-center mt-2">
          <button class="btn btn-danger btn-sm" @click="deletePersona">删除</button>
          <div class="flex flex-gap">
            <button class="btn btn-outline btn-sm" @click="switchPersona">设为默认</button>
            <button class="btn btn-primary" @click="savePersona">保存</button>
          </div>
        </div>
        <div v-if="personaMsg" class="msg-box" :class="personaMsgType">{{ personaMsg }}</div>
      </div>
    </div>

    <!-- API Settings Page -->
    <div v-if="currentPage === 'api'">
      <div class="page-header">
        <h2>AI 接口配置</h2>
        <p>配置 LLM API 连接信息</p>
      </div>
      <div class="card">
        <div class="form-group">
          <label>API Key</label>
          <input type="password" v-model="apiSettings.api_key" placeholder="sk-...">
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input type="text" v-model="apiSettings.base_url" placeholder="https://api.openai.com/v1">
        </div>
        <div class="form-group">
          <label>Model</label>
          <input type="text" v-model="apiSettings.model" placeholder="gpt-4">
        </div>
        <div class="form-group">
          <label>Model Fast</label>
          <input type="text" v-model="apiSettings.model_fast" placeholder="gpt-3.5-turbo">
        </div>
        <div class="flex flex-gap">
          <button class="btn btn-primary" @click="saveApiSettings">保存</button>
          <button class="btn btn-success" @click="testApiConnection" :disabled="testing">
            <span v-if="testing" class="spinner"></span>
            <span v-else>测试连接</span>
          </button>
        </div>
        <div v-if="apiMsg" class="msg-box" :class="apiMsgType">{{ apiMsg }}</div>
      </div>
    </div>

    <!-- Publishers Page -->
    <div v-if="currentPage === 'publishers'">
      <div class="page-header">
        <h2>发布平台</h2>
        <p>配置文章发布渠道</p>
      </div>
      <div v-for="pub in publishers" :key="pub.id" class="publisher-card" :class="{enabled: pub.active}">
        <div class="publisher-header">
          <h4>{{ pub.name || pub.type }}</h4>
          <label class="toggle-switch">
            <input type="checkbox" v-model="pub.active" @change="savePublishers">
            <span class="toggle-slider"></span>
          </label>
        </div>
        <!-- Hugo config -->
        <div v-if="pub.type === 'hugo'">
          <p style="color: #777; font-size: 13px;">本地 Hugo 静态博客，自动构建并发布到 Git</p>
        </div>
        <!-- WordPress config -->
        <div v-if="pub.type === 'wordpress'">
          <div class="form-group">
            <label>XMLRPC URL</label>
            <input type="url" v-model="pub.config.xmlrpc_url" placeholder="https://example.com/xmlrpc.php">
          </div>
          <div class="form-group">
            <label>用户名</label>
            <input type="text" v-model="pub.config.username" placeholder="admin">
          </div>
          <div class="form-group">
            <label>密码</label>
            <input type="password" v-model="pub.config.password" placeholder="password">
          </div>
        </div>
        <!-- Zhiliu config -->
        <div v-if="pub.type === 'zhiliu'">
          <div class="form-group">
            <label>API Endpoint</label>
            <input type="url" v-model="pub.config.endpoint" placeholder="https://blog.example.com/api/posts">
          </div>
          <div class="form-group">
            <label>Bearer Token</label>
            <input type="password" v-model="pub.config.token" placeholder="your-token-here">
          </div>
          <div class="form-group">
            <label>分类 ID</label>
            <input type="text" v-model="pub.config.category_id" placeholder="1">
          </div>
        </div>
        <button class="btn btn-primary btn-sm" @click="savePublishers">保存配置</button>
      </div>
      <div v-if="pubMsg" class="msg-box" :class="pubMsgType">{{ pubMsg }}</div>
    </div>

    <!-- Schedule Page -->
    <div v-if="currentPage === 'schedule'">
      <div class="page-header">
        <h2>定时发送</h2>
        <p>配置自动发布计划</p>
      </div>
      <div class="card">
        <h3>运行模式</h3>
        <div class="mode-selector">
          <div class="mode-option" :class="{selected: schedule.mode === 'auto'}" @click="schedule.mode = 'auto'">
            <h4>自动</h4>
            <p>按计划自动生成并发布</p>
          </div>
          <div class="mode-option" :class="{selected: schedule.mode === 'review'}" @click="schedule.mode = 'review'">
            <h4>审核</h4>
            <p>生成后存入草稿箱</p>
          </div>
          <div class="mode-option" :class="{selected: schedule.mode === 'manual-only'}" @click="schedule.mode = 'manual-only'">
            <h4>手动</h4>
            <p>仅手动触发生成</p>
          </div>
          <div class="mode-option" :class="{selected: schedule.mode === 'debug'}" @click="schedule.mode = 'debug'">
            <h4>调试</h4>
            <p>调试模式，不写文件</p>
          </div>
        </div>
      </div>
      <div class="card">
        <h3>发文计划</h3>
        <div class="form-group">
          <label>每周发文日</label>
          <div class="day-selector">
            <span
              v-for="(day, idx) in ['周一','周二','周三','周四','周五','周六','周日']"
              :key="idx"
              class="day-chip"
              :class="{selected: schedule.preferred_days && schedule.preferred_days.includes(idx)}"
              @click="toggleDay(idx)"
            >{{ day }}</span>
          </div>
        </div>
        <div class="form-group">
          <label>发出时间 (UTC)</label>
          <div class="flex items-center flex-gap">
            <input type="number" v-model.number="schedule.preferred_hour_utc" min="0" max="23" style="width:80px">
            <span>时</span>
          </div>
        </div>
        <div class="form-group">
          <label>每周发文数</label>
          <input type="number" v-model.number="schedule.posts_per_week" min="1" max="7" style="width:80px">
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="pauseMode"> 暂停发布
          </label>
        </div>
        <button class="btn btn-primary" @click="saveSchedule">保存计划</button>
        <div v-if="scheduleMsg" class="msg-box" :class="scheduleMsgType">{{ scheduleMsg }}</div>
      </div>
      <div class="card">
        <h3>今夜备注</h3>
        <div class="form-group">
          <input type="text" v-model="overrides.notes_tonight" placeholder="今夜特殊备注（可选）">
        </div>
        <button class="btn btn-primary" @click="saveOverrides">保存备注</button>
      </div>
    </div>
  </main>
</div>

<div id="toast" class="toast"></div>

<script src="https://unpkg.com/vue@3/dist/vue.global.prod.js"></script>
<script>
const { createApp, ref, onMounted } = Vue;

createApp({
  setup() {
    // State
    const currentPage = ref('generate');
    const personas = ref([]);
    const selectedPersona = ref(null);
    const editPersonaJson = ref('');
    const editPersonaMd = ref('');
    const personaTab = ref('json');
    const newPersonaName = ref('');

    const apiSettings = ref({api_key: '', base_url: '', model: '', model_fast: ''});
    const publishers = ref([]);
    const schedule = ref({mode: 'auto', preferred_days: [], preferred_hour_utc: 16, posts_per_week: 3});
    const overrides = ref({notes_tonight: ''});
    const pauseMode = ref(false);

    const generateMode = ref('auto');
    const generateTopic = ref('');
    const generating = ref(false);
    const generateMsg = ref('');
    const generateMsgType = ref('');

    const testing = ref(false);
    const personaMsg = ref('');
    const personaMsgType = ref('');
    const apiMsg = ref('');
    const apiMsgType = ref('');
    const pubMsg = ref('');
    const pubMsgType = ref('');
    const scheduleMsg = ref('');
    const scheduleMsgType = ref('');

    // Toast
    function showToast(msg, type = '') {
      const toast = document.getElementById('toast');
      toast.textContent = msg;
      toast.className = 'toast ' + type;
      setTimeout(() => toast.classList.add('show'), 10);
      setTimeout(() => toast.classList.remove('show'), 3000);
    }

    // API helpers
    async function apiGet(url) {
      const r = await fetch(url);
      return r.json();
    }
    async function apiPost(url, data) {
      const r = await fetch(url, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
      });
      return r.json();
    }

    // Load data
    async function loadPersonas() {
      personas.value = await apiGet('/api/personas');
    }
    async function loadApiSettings() {
      apiSettings.value = await apiGet('/api/api-settings');
    }
    async function loadPublishers() {
      publishers.value = await apiGet('/api/publishers').then(r => r.publishers || []);
    }
    async function loadSchedule() {
      schedule.value = await apiGet('/api/schedule');
      if (!schedule.value.preferred_days) schedule.value.preferred_days = [];
    }
    async function loadOverrides() {
      overrides.value = await apiGet('/api/overrides');
      pauseMode.value = overrides.value.pause === true;
    }

    // Persona actions
    async function selectPersona(name) {
      selectedPersona.value = name;
      personaTab.value = 'json';
      const data = await apiGet(`/api/personas/${name}/detail`);
      if (data.name) {
        editPersonaMd.value = data.md || '';
        try {
          editPersonaJson.value = JSON.stringify(data.json, null, 2);
        } catch {
          editPersonaJson.value = '{}';
        }
      }
    }
    async function createPersona() {
      const name = newPersonaName.value.trim();
      if (!name) { showToast('请输入角色名称', 'error'); return; }
      await apiPost('/api/personas', {name, md: '', json: {}});
      newPersonaName.value = '';
      await loadPersonas();
      showToast('角色已创建', 'success');
    }
    async function savePersona() {
      let jsonData;
      try {
        jsonData = JSON.parse(editPersonaJson.value);
      } catch {
        showToast('JSON 格式错误', 'error');
        return;
      }
      const r = await apiPost(`/api/personas/${selectedPersona.value}/save`, {
        md: editPersonaMd.value,
        json: jsonData
      });
      if (r.success) {
        showToast('保存成功', 'success');
      } else {
        showToast('保存失败: ' + (r.error || ''), 'error');
      }
    }
    async function switchPersona() {
      const r = await apiPost(`/api/personas/${selectedPersona.value}/activate`);
      if (r.success) {
        await loadPersonas();
        showToast('已设为默认角色', 'success');
      }
    }
    async function deletePersona() {
      if (!confirm('确定要删除角色 ' + selectedPersona.value + ' 吗？')) return;
      const r = await apiPost(`/api/personas/${selectedPersona.value}/delete`);
      if (r.success) {
        selectedPersona.value = null;
        await loadPersonas();
        showToast('已删除', 'success');
      }
    }

    // API actions
    async function saveApiSettings() {
      const r = await apiPost('/api/api-settings', apiSettings.value);
      if (r.success) {
        showToast('保存成功', 'success');
      } else {
        showToast('保存失败', 'error');
      }
    }
    async function testApiConnection() {
      testing.value = true;
      apiMsg.value = '';
      const r = await apiPost('/api/api-settings/test', apiSettings.value);
      testing.value = false;
      if (r.success) {
        apiMsg.value = '连接成功！';
        apiMsgType.value = 'success';
      } else {
        apiMsg.value = '连接失败: ' + (r.error || r.message || '');
        apiMsgType.value = 'error';
      }
    }

    // Publisher actions
    async function savePublishers() {
      const r = await apiPost('/api/publishers', {publishers: publishers.value});
      if (r.success) {
        showToast('保存成功', 'success');
      } else {
        showToast('保存失败', 'error');
      }
    }

    // Schedule actions
    function toggleDay(day) {
      const arr = schedule.value.preferred_days || [];
      const idx = arr.indexOf(day);
      if (idx >= 0) arr.splice(idx, 1);
      else arr.push(day);
      schedule.value.preferred_days = arr;
    }
    async function saveSchedule() {
      overrides.value.pause = pauseMode.value;
      await apiPost('/api/schedule', schedule.value);
      await apiPost('/api/overrides', overrides.value);
      showToast('保存成功', 'success');
    }
    async function saveOverrides() {
      overrides.value.pause = pauseMode.value;
      const r = await apiPost('/api/overrides', overrides.value);
      if (r.success) showToast('保存成功', 'success');
      else showToast('保存失败', 'error');
    }

    // Generate
    async function triggerGenerate() {
      generating.value = true;
      generateMsg.value = '';
      const r = await apiPost('/api/generate', {
        mode: generateMode.value,
        topic: generateTopic.value
      });
      generating.value = false;
      generateMsg.value = r.message || (r.success ? '已开始生成' : '生成失败');
      generateMsgType.value = r.success ? 'success' : 'error';
    }

    // Init
    onMounted(async () => {
      await Promise.all([
        loadPersonas(),
        loadApiSettings(),
        loadPublishers(),
        loadSchedule(),
        loadOverrides()
      ]);
    });

    return {
      currentPage, personas, selectedPersona, editPersonaJson, editPersonaMd, personaTab, newPersonaName,
      apiSettings, publishers, schedule, overrides, pauseMode,
      generateMode, generateTopic, generating, generateMsg, generateMsgType,
      testing, personaMsg, personaMsgType, apiMsg, apiMsgType, pubMsg, pubMsgType, scheduleMsg, scheduleMsgType,
      loadPersonas, selectPersona, createPersona, savePersona, switchPersona, deletePersona,
      saveApiSettings, testApiConnection,
      savePublishers,
      toggleDay, saveSchedule, saveOverrides,
      triggerGenerate
    };
  }
}).mount('#app');
</script>
</body>
</html>'''


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Night Journal Admin Panel')
    parser.add_argument('--port', type=int, default=8765, help='Port to listen on (default: 8765)')
    parser.add_argument('--root', type=str, default=None, help='Blog root directory')
    args = parser.parse_args()

    if args.root:
        root = Path(args.root).resolve()
    else:
        root = project_root

    # Initialize settings with root
    global _settings
    _settings = load_settings(root)

    addr = ('', args.port)
    print(f'Night Journal Admin starting on http://localhost:{args.port}')
    print(f'Root directory: {root}')
    print('Press Ctrl+C to stop')

    server = HTTPServer(addr, AdminAPIHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()


if __name__ == '__main__':
    main()
