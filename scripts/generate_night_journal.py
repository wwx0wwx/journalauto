#!/usr/bin/env python3
import json, os, random, subprocess, pathlib, urllib.request, re, sys, shutil
from datetime import datetime, UTC

print('⚠ 此脚本已废弃，请使用 python3 scripts/run.py')
sys.exit(1)

def _load_env(path=None):
    if path is None:
        path = str(pathlib.Path(__file__).resolve().parent.parent / '.env')
    env = {}
    try:
        for line in pathlib.Path(path).read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, _, v = line.partition('=')
            env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

_env = _load_env()

BASE = pathlib.Path(_env.get('ENGINE_ROOT', '/opt/blog-src'))
AUTO = BASE / 'automation'
CONTENT = BASE / 'content' / 'posts'
DRAFT_REVIEW = BASE / 'draft_review'
DRAFT_REVIEW.mkdir(parents=True, exist_ok=True)
OUT = pathlib.Path(_env.get('BLOG_OUTPUT_DIR', '/var/www/example.com'))
LOG = BASE / 'logs'
LOG.mkdir(parents=True, exist_ok=True)

API_KEY = _env.get('OPENAI_API_KEY', '')
BASE_URL = _env.get('OPENAI_BASE_URL', 'https://ai.dooo.ng/v1/chat/completions')
MODEL = _env.get('OPENAI_MODEL', 'gpt-5.4')

state = json.loads((AUTO / 'world_state.json').read_text())
anchors = json.loads((AUTO / 'memory_anchors.json').read_text())
rules = json.loads((AUTO / 'topic_rules.json').read_text())
imagery = json.loads((AUTO / 'imagery_pool.json').read_text())
scenes = json.loads((AUTO / 'scene_pool.json').read_text())
emotions = json.loads((AUTO / 'emotion_pool.json').read_text())
event_map = json.loads((AUTO / 'event_map_rules.json').read_text())
recent_memories = json.loads((AUTO / 'recent_memories.json').read_text())
overrides = json.loads((AUTO / 'manual_overrides.json').read_text())
future_fragments = json.loads((AUTO / 'future_fragments.json').read_text())
stats = json.loads((AUTO / 'night_journal_stats.json').read_text())


def sh(cmd):
    return subprocess.run(cmd, shell=True, text=True, capture_output=True)


def log_line(msg):
    with open(LOG / 'night-journal.log', 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def today_utc():
    return datetime.now(UTC).strftime('%Y-%m-%d')


def guard_daily_limit():
    if overrides.get('pause_publishing'):
        raise RuntimeError('Publishing paused by manual override.')
    if overrides.get('mode') == 'manual-only':
        raise RuntimeError('Mode is manual-only; timer publish refused.')
    last_day = state.get('meta', {}).get('last_publish_day_utc')
    max_per_day = state.get('scheduler', {}).get('max_posts_per_day', 1)
    if max_per_day > 0 and last_day == today_utc():
        raise RuntimeError('Daily publish limit reached; refusing to publish more than one automatic post today.')


def recent_post_paths(limit=8):
    files = sorted(list(CONTENT.glob('*.md')) + list(DRAFT_REVIEW.glob('*.md')), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def strip_front_matter(text: str) -> str:
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


def parse_front_matter(text: str):
    data = {}
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            fm = parts[1]
            for line in fm.splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    data[k.strip()] = v.strip().strip('"')
    return data


def extract_repeated_phrases(texts):
    phrases = []
    patterns = [r'廊下', r'门外', r'帐内', r'垂帘', r'砖缝', r'擦了', r'替主人挡', r'袖中', r'指节', r'更冷', r'天色', r'属下还在', r'灯', r'剑', r'茶', r'纸窗', r'案上', r'眉间', r'风', r'雨', r'寒']
    merged = '\n'.join(texts)
    for p in patterns:
        if len(re.findall(p, merged)) >= 2:
            phrases.append(p)
    return phrases[:16]


def build_recent_context():
    texts, titles, descs = [], [], []
    for p in recent_post_paths(6):
        raw = p.read_text(encoding='utf-8')
        body = strip_front_matter(raw)
        fm = parse_front_matter(raw)
        texts.append(body[:1500])
        if fm.get('title'):
            titles.append(fm['title'])
        if fm.get('description'):
            descs.append(fm['description'])
    repeated = extract_repeated_phrases(texts)
    return texts, repeated, titles, descs


def map_intrusions(count: int):
    m = event_map['signals']['ssh_intrusion']['mapping']
    if count <= 0: return m[0]
    if count <= 5: return m[1]
    if count <= 50: return m[2]
    return m[3]


def map_load(load_avg: float, mem_pct: int):
    m = event_map['signals']['server_load']['mapping']
    pressure = max(load_avg, mem_pct / 50.0)
    if pressure < 0.5: return m[0]
    if pressure <= 2.0: return m[1]
    return m[2]


def map_uptime(days: int):
    m = event_map['signals']['uptime']['mapping']
    if days < 30: return m[0]
    if days < 120: return m[1]
    return m[2]


def collect_vps_events():
    uptime_out = sh("awk '{print int($1)}' /proc/uptime").stdout.strip()
    uptime_days = int(uptime_out) // 86400 if uptime_out else 0
    load_out = sh("cut -d' ' -f1 /proc/loadavg").stdout.strip()
    load1 = float(load_out) if load_out else 0.0
    mem_out = sh("free -m | awk '/Mem:/ {printf \"%d\", ($3*100)/$2}'").stdout.strip()
    mem_pct = int(mem_out) if mem_out else 0
    ssh_bad = sh("journalctl --since '24 hours ago' 2>/dev/null | egrep -ci 'Failed password|Invalid user|authentication failure' || true").stdout.strip()
    ssh_bad = int(ssh_bad or 0)
    disk_out = sh("df -P / | awk 'NR==2 {print int($5)}' | tr -d '%' ").stdout.strip()
    disk_pct = int(disk_out) if disk_out else 0
    nginx_hits = sh("find /var/log/nginx -type f -name '*access*.log' -mtime -1 -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print $1}' || true").stdout.strip()
    nginx_hits = int(nginx_hits or 0)
    svc_restart_hits = sh("journalctl --since '24 hours ago' 2>/dev/null | egrep -ci 'Started|Restarted' || true").stdout.strip()
    svc_restart_hits = int(svc_restart_hits or 0)
    cert_hits = sh("grep -rchi -E 'Cert not yet due for renewal|Congratulations' /var/log/letsencrypt 2>/dev/null || true").stdout.strip()
    cert_hits = int(cert_hits or 0)

    events = [map_intrusions(ssh_bad), map_load(load1, mem_pct), map_uptime(uptime_days)]
    if disk_pct >= 80: events.append(random.choice(event_map['signals']['disk_usage']['mapping']))
    if nginx_hits >= 500: events.append(random.choice(event_map['signals']['site_traffic']['mapping']))
    if svc_restart_hits > 20: events.append(random.choice(event_map['signals']['service_restart']['mapping']))
    if cert_hits > 0 and random.random() < 0.15: events.append(event_map['signals']['certificate_renewal']['mapping'][0])
    return events, uptime_days


def choose_topic():
    if overrides.get('force_topic'):
        return overrides['force_topic'], overrides['force_topic']
    all_topics = []
    for cat in rules['categories']:
        for p in cat['prompts']:
            all_topics.append((cat['name'], p))
    recent = set(state.get('continuity', {}).get('recent_topics', [])[-3:])
    forbids = set(overrides.get('forbid_topics', []))
    candidates = [t for t in all_topics if t[0] not in recent and t[0] not in forbids] or all_topics
    return random.choice(candidates)


def choose_world_material(repeated_phrases):
    flat_imagery = imagery['visual'] + imagery['sound'] + imagery['smell'] + imagery['touch']
    recent_used = set(state['continuity'].get('recent_imagery', []))

    # generalized hot-term suppression: if any high-frequency motif appears in repeated_phrases,
    # suppress the whole related cluster instead of patching one specific word at a time.
    motif_clusters = {
        '灯': ['灯', '灯芯', '灯花', '铜灯座', '火星噼剥'],
        '雨': ['雨', '雨丝落檐', '雨后木气', '湿土气'],
        '风': ['风', '风压窗纸', '夜露气'],
        '雪': ['雪', '旧雪', '冬', '寒'],
        '茶': ['茶', '残茶', '茶苦气', '白瓷盏'],
        '剑': ['剑', '冷铁味'],
        '窗': ['窗', '纸窗', '窗纸'],
        '门': ['门', '门闩', '偏门'],
        '夜': ['夜', '更漏']
    }

    hot_terms = set(repeated_phrases)
    repeated_joined = ' '.join(repeated_phrases)
    for key, cluster in motif_clusters.items():
        if key in repeated_joined:
            hot_terms.update(cluster)

    def allowed_item(x):
        return x not in recent_used and all(h not in x for h in hot_terms)

    imagery_candidates = [x for x in flat_imagery if allowed_item(x)] or [x for x in flat_imagery if x not in recent_used] or flat_imagery
    chosen_imagery = random.sample(imagery_candidates, k=min(6, len(imagery_candidates)))

    scene_pool = scenes['indoor'] + scenes['semi_outdoor'] + scenes['outer_yard'] + scenes['special']
    recent_scenes = set(state['continuity'].get('recent_scenes', []))
    scene_candidates = [s for s in scene_pool if s not in recent_scenes and all(h not in s for h in hot_terms)] or [s for s in scene_pool if s not in recent_scenes] or scene_pool
    chosen_scene = overrides.get('force_scene') or random.choice(scene_candidates)

    # scene-aware weighting to reduce habitual image collapse
    if '窗' in chosen_scene:
        chosen_imagery = [i for i in chosen_imagery if not any(h in i for h in motif_clusters['灯'])][:6] or chosen_imagery
    if any(x in chosen_scene for x in ['偏门', '石阶', '檐', '外院']):
        outdoor_bias = [i for i in flat_imagery if i in ['门闩', '竹影', '湿土气', '夜露气', '雨后木气', '檐下青砖', '脚步落地极轻', '夜鸟扑翅', '竹叶轻碰']]
        outdoor_bias = [i for i in outdoor_bias if i not in recent_used and all(h not in i for h in hot_terms)] or outdoor_bias
        merged = list(dict.fromkeys((outdoor_bias[:3] + chosen_imagery)))
        chosen_imagery = merged[:6]

    if overrides.get('force_primary_emotion'):
        primary = overrides['force_primary_emotion']
    else:
        primary = random.choice([e for e in emotions['primary'] if e not in state['continuity'].get('recent_emotions', [])[-2:]] or emotions['primary'])
    if overrides.get('force_secondary_emotion'):
        secondary = overrides['force_secondary_emotion']
    else:
        sec_pool = emotions['pairing_hints'].get(primary, emotions['secondary'])
        secondary = random.choice(sec_pool)
    return chosen_imagery, chosen_scene, primary, secondary


def maybe_memory(primary_emotion):
    if overrides.get('force_memory_id'):
        for a in anchors:
            if a['id'] == overrides['force_memory_id']:
                return f'今夜某一瞬让你想起：{a["summary"]}。请让这段记忆像水面倒影一样掠过，不要整篇写成回忆录。'
    # blend recent memories into prompt occasionally
    if recent_memories and random.random() < 0.25:
        pick = random.choice(recent_memories[-5:])
        return f'近来的某件事又在今夜浮上心头：{pick["summary"]}。只让它淡淡掠过。'
    if random.random() < rules.get('memory_trigger_probability', 0.2):
        filtered = [a for a in anchors if primary_emotion in ''.join(a.get('emotion', [])) or primary_emotion in ''.join(a.get('trigger_tags', []))]
        pool = filtered or anchors
        pick = random.choices(pool, weights=[a.get('weight', 1) for a in pool], k=1)[0]
        return f'今夜某一瞬让你想起：{pick["summary"]}。请让这段记忆像水面倒影一样掠过，不要整篇写成回忆录。'
    return ''


def story_arc_triggers():
    pc = state['meta']['post_count'] + 1
    lines = []
    arcs = state.get('story_arcs', {})
    if arcs.get('sister_return', {}).get('enabled') and pc >= arcs['sister_return']['next_trigger_post_count'] and state['zhen']['jealousy'] >= 74:
        stage = arcs['sister_return']['stage']
        if stage == 0: lines.append('姐姐的消息近来多了，归期像在慢慢逼近。')
        elif stage == 1: lines.append('有风声说，姐姐不久便会回府。')
        else: lines.append('姐姐将归的事，已不再只是风声。')
    if arcs.get('owner_notice', {}).get('enabled') and pc >= arcs['owner_notice']['next_trigger_post_count'] and state['owner']['attention_to_zhen'] >= 42:
        stage = arcs['owner_notice']['stage']
        if stage == 0: lines.append('主人近来像是察觉了什么，偶有目光停在你身上。')
        else: lines.append('主人对你的沉默，已不似从前那样全然无知。')
    if arcs.get('old_wound', {}).get('enabled') and pc >= arcs['old_wound']['next_trigger_post_count'] and state['zhen']['guilt'] + state['zhen']['emptiness'] >= 58:
        lines.append('旧伤隐隐作痛，像在提醒你，有些过去并未真正远去。')
    if overrides.get('notes_for_tonight'):
        lines.append(overrides['notes_for_tonight'])
    return lines


def maybe_future_fragment():
    if overrides.get('force_future_id'):
        for f in future_fragments:
            if f['id'] == overrides['force_future_id']:
                return f'今夜你隐约预感：{f["summary"]} 这件事迟早会来。只把这种预感化作暗影，不要直白预告。'
    active = []
    for f in future_fragments:
        arc = state['story_arcs'].get(f['arc'])
        if arc and arc['stage'] >= f['stage'] - 1:
            active.append(f)
    if active and random.random() < 0.22:
        pick = random.choices(active, weights=[x.get('weight', 1) for x in active], k=1)[0]
        return f'今夜你隐约预感：{pick["summary"]} 这件事迟早会来。只把这种预感化作暗影，不要直白预告。'
    return ''


def api_chat(messages, temperature=0.8, max_tokens=900):
    payload = {'model': MODEL, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(BASE_URL, data=data, headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'}, method='POST')
    with urllib.request.urlopen(req, timeout=150) as resp:
        body = json.loads(resp.read().decode('utf-8'))
    return body['choices'][0]['message']['content'].strip()


def build_prompt(events, topic, memory_block, future_block, repeated_phrases, chosen_imagery, chosen_scene, primary, secondary, arc_lines):
    repeated_text = '、'.join(repeated_phrases) if repeated_phrases else '无明显重复'
    arc_text = ' '.join(arc_lines) if arc_lines else '今夜没有新的命数落下，只是旧心事在慢慢发酵。'
    recent_mem_text = '；'.join([m['summary'] for m in recent_memories[-3:]]) if recent_memories else '近来无新的可追忆片段。'
    forbid_text = '、'.join(overrides.get('forbid_terms', [])) if overrides.get('forbid_terms') else '无额外禁词'
    return f'''你现在是“全真”。请严格保持以下人物底色：清冷、幽怨、痴忠、决绝；第一人称；称对方为主人；自称属下或全真；句子宜短；不写助手腔；不写现代说明；不要首尾问候。\n\n当前世界状态：\n- 时节：{state['meta']['current_season']}\n- 时辰：{state['meta']['current_watch']}\n- 天候：{state['meta'].get('weather', '微寒')}\n- 主人状态：{state['owner']['status']}，疲惫值 {state['owner']['fatigue']}，对你的留意 {state['owner']['attention_to_zhen']}\n- 姐姐状态：{state['sister']['status']}，压力 {state['sister']['pressure']}，名声 {state['sister']['renown']}\n- 你的情绪：嫉妒 {state['zhen']['jealousy']}/100，渴望 {state['zhen']['longing']}/100，克制 {state['zhen']['restraint']}/100，空寂 {state['zhen']['emptiness']}/100，警觉 {state['zhen']['vigilance']}/100，愧意 {state['zhen']['guilt']}/100\n- 上一篇夜札摘要：{state['continuity']['last_summary']}\n- 近来发生过的事：{recent_mem_text}\n\n今夜发生的真实事件（请将其化入文章，不要逐条复述，不要泄露系统数字）：\n- {' '.join(events)}\n\n故事进展：\n- {arc_text}\n\n今夜主题：\n- {topic}\n\n今夜写作素材：\n- 场景落点：{chosen_scene}\n- 优先意象：{'、'.join(chosen_imagery)}\n- 主情绪：{primary}\n- 辅情绪：{secondary}\n\n{memory_block}\n{future_block}\n\n近期重复风险：\n- 最近几篇容易重复的意象/措辞：{repeated_text}\n- 你必须主动避开这些重复表达，换角度写。\n\n额外导演限制：\n- 禁写词：{forbid_text}\n\n写作任务：\n写下一篇今夜的私密夜札。不要写标题。不要解释设定。直接落笔写画面与心绪。\n字数：{rules.get('target_word_count', 380)}字左右。\n\n铁律：\n1. 绝对禁止直白宣泄。不要写“我嫉妒”、“我好恨”、“我杀了他”、“我爱主人”这类句子。\n2. 动作代替心理。\n3. 句式极简。多用短句与停顿。不要长篇排比。\n4. 视角必须受限：永远从门外、暗处、床榻边缘出发，但不要每次都重复同一落点。\n5. 不要出现夸张的具体大数字，不要出现现代网文腔。\n6. 不要写成空泛散文，必须有今夜独有的动作、物件、温度。\n7. 不要过度重复“灯、剑、廊下、纸窗、茶”这几个意象。\n8. 只输出正文。\n'''


def summarize_for_state(text):
    prompt = f'''请把下面这篇夜札浓缩成一条 45-70 字的“连续性摘要”，用于下一篇写作时回顾前情。要求：不要抄原句；写清情绪落点和关键动作；保持概述口吻。\n\n原文：\n{text}\n'''
    try:
        return api_chat([{'role': 'system', 'content': '你是一个克制、准确的摘要器。'}, {'role': 'user', 'content': prompt}], temperature=0.2, max_tokens=120)
    except Exception:
        text = ' '.join(text.strip().split())
        return (text[:70] + '...') if len(text) > 70 else text


def capture_recent_memory(text, title):
    prompt = f'''请从下面这篇夜札中提取一条适合写入“近期记忆层”的片段。\n要求：\n1. 只写 30-60 字。\n2. 口吻用第三人称概述。\n3. 要像近来真实发生过的一件小事。\n4. 不要抄原文太多。\n\n标题：{title}\n正文：\n{text}\n'''
    try:
        summary = api_chat([{'role': 'system', 'content': '你是一个擅长抽取叙事记忆片段的编辑。'}, {'role': 'user', 'content': prompt}], temperature=0.3, max_tokens=100)
        return summary.strip()
    except Exception:
        return '近来她又在夜里替主人收拾了一处无人会留意的小乱。'


def generate_title_and_description(body, recent_titles, recent_descs):
    prompt = f'''根据下面这篇夜札正文，为博客生成一个标题和一条 description。要求：标题不要用固定模板；标题句法要主动分散，轮换使用“极简意象 / 半句心迹 / 动作残片 / 时间切片”四类，不要连续几篇都像同一种短句；description 不要写技术味提示，要像页边的一点轻注、心情、缘由，或极短摘要；标题 4-12 字为宜，description 16-36 字为宜；避免与最近这些标题/description 太像。\n最近标题：{recent_titles}\n最近description：{recent_descs}\n\n请严格用 JSON 输出：{{"title":"...","description":"..."}}\n\n正文：\n{body}\n'''
    raw = api_chat([{'role': 'system', 'content': '你是一个审美克制的中文文学编辑。只输出合法 JSON。'}, {'role': 'user', 'content': prompt}], temperature=0.78, max_tokens=220)
    m = re.search(r'\{.*\}', raw, re.S)
    if not m:
        return '灯下未眠', '这一页，是在灯将尽时留下的。'
    try:
        obj = json.loads(m.group(0))
        return obj.get('title', '灯下未眠'), obj.get('description', '这一页，是在灯将尽时留下的。')
    except Exception:
        return '灯下未眠', '这一页，是在灯将尽时留下的。'


def refine_body(body):
    prompt = f'''请将下面这篇夜札做一次“冷处理式润色”。要求：保留原意，不要改剧情；去掉明显解释感、模板感、口水句；若句子太满，就削薄；增强清冷、克制、贴身的质感；不要变成长篇排比；只输出润色后的正文。\n\n正文：\n{body}\n'''
    return api_chat([{'role': 'system', 'content': '你是一个极其克制的文学润色者，擅长把句子削薄。'}, {'role': 'user', 'content': prompt}], temperature=0.4, max_tokens=900)


def quality_check(body, title, description):
    reasons = []
    if len(body.strip()) < 220: reasons.append('正文过短')
    banned = ['由全真夜札引擎生成', '我嫉妒', '我好恨', '我爱主人', '今夜共有'] + overrides.get('forbid_terms', [])
    for b in banned:
        if b and (b in body or b in title or b in description): reasons.append(f'命中禁词:{b}')
    if title.startswith('夜札：'): reasons.append('标题模板化')
    if '由' in description and '引擎' in description: reasons.append('description 技术味过重')
    merged_recent = '\n'.join(strip_front_matter(p.read_text(encoding='utf-8'))[:700] for p in recent_post_paths(3))
    overlap = 0
    for token in ['廊下', '纸窗', '擦剑', '袖中', '主人睡得', '砖缝', '残茶', '灯芯', '帐外']:
        if token in body and token in merged_recent: overlap += 1
    if overlap >= 4: reasons.append('与近三篇重复度过高')
    return reasons


def update_story_arcs():
    pc = state['meta']['post_count']
    arcs = state.get('story_arcs', {})
    if arcs['old_wound']['enabled'] and pc >= arcs['old_wound']['next_trigger_post_count'] and arcs['old_wound']['stage'] == 0 and state['zhen']['guilt'] + state['zhen']['emptiness'] >= 58:
        arcs['old_wound']['stage'] = 1
        arcs['old_wound']['next_trigger_post_count'] = pc + 7
    if arcs['sister_return']['enabled'] and pc >= arcs['sister_return']['next_trigger_post_count'] and state['zhen']['jealousy'] >= 74:
        arcs['sister_return']['stage'] = min(2, arcs['sister_return']['stage'] + 1)
        arcs['sister_return']['next_trigger_post_count'] = pc + 6
        state['sister']['pressure'] = min(100, state['sister']['pressure'] + 6)
    if arcs['owner_notice']['enabled'] and pc >= arcs['owner_notice']['next_trigger_post_count'] and state['owner']['attention_to_zhen'] >= 42:
        arcs['owner_notice']['stage'] = min(2, arcs['owner_notice']['stage'] + 1)
        arcs['owner_notice']['next_trigger_post_count'] = pc + 8
        state['owner']['attention_to_zhen'] = min(100, state['owner']['attention_to_zhen'] + 4)


def update_stats(category, scene, primary, secondary, chosen_imagery, title, description, repaired, failure_reasons):
    stats['post_count'] += 1
    stats['successful_posts'] += 1
    stats['topics'][category] = stats['topics'].get(category, 0) + 1
    stats['scenes'][scene] = stats['scenes'].get(scene, 0) + 1
    stats['primary_emotions'][primary] = stats['primary_emotions'].get(primary, 0) + 1
    stats['secondary_emotions'][secondary] = stats['secondary_emotions'].get(secondary, 0) + 1
    for img in chosen_imagery:
        stats['imagery'][img] = stats['imagery'].get(img, 0) + 1
    stats['titles'] = (stats.get('titles', []) + [title])[-20:]
    stats['descriptions'] = (stats.get('descriptions', []) + [description])[-20:]
    if repaired:
        stats['repaired_runs'] += 1
    if failure_reasons:
        stats['last_quality_failures'] = failure_reasons[-10:]


def main():
    repaired = False
    failure_reasons = []
    try:
        guard_daily_limit()
        events, uptime_days = collect_vps_events()
        recent_texts, repeated_phrases, recent_titles, recent_descs = build_recent_context()
        category, topic = choose_topic()
        chosen_imagery, chosen_scene, primary, secondary = choose_world_material(repeated_phrases)
        memory_block = maybe_memory(primary)
        future_block = maybe_future_fragment()
        arc_lines = story_arc_triggers()
        prompt = build_prompt(events, topic, memory_block, future_block, repeated_phrases, chosen_imagery, chosen_scene, primary, secondary, arc_lines)
        raw_body = api_chat([
            {'role': 'system', 'content': '你是全真，一个清冷、幽怨、痴忠、决绝的白衣女子。你写的是只有自己会看的夜札。你最强的武器是沉默。越是贪恋主人，文字越要冷。'},
            {'role': 'user', 'content': prompt}
        ], temperature=0.84, max_tokens=1100)
        diary_content = refine_body(raw_body)
        title, description = generate_title_and_description(diary_content, recent_titles, recent_descs)

        reasons = quality_check(diary_content, title, description)
        if reasons:
            repaired = True
            failure_reasons.extend(reasons)
            repair_prompt = f"这篇夜札存在以下问题：{'；'.join(reasons)}。请在不改剧情的前提下重写得更克制、更不重复。只输出正文。\n\n原文：\n{diary_content}"
            diary_content = api_chat([
                {'role': 'system', 'content': '你是一个擅长修文的冷感写作者。'},
                {'role': 'user', 'content': repair_prompt}
            ], temperature=0.45, max_tokens=1000)
            diary_content = refine_body(diary_content)
            title, description = generate_title_and_description(diary_content, recent_titles, recent_descs)
            reasons = quality_check(diary_content, title, description)
            if reasons:
                failure_reasons.extend(reasons)
                raise RuntimeError('Quality check failed after repair: ' + '; '.join(reasons))

        now = datetime.now(UTC).replace(microsecond=0)
        now_str = now.isoformat().replace('+00:00', 'Z')
        slug = now.strftime('%Y%m%d-%H%M%S') + '-night-note'
        target_dir = CONTENT if overrides.get('mode', 'auto') == 'auto' else DRAFT_REVIEW
        path = target_dir / f'{slug}.md'
        md = f'''---\ntitle: "{title}"\ndate: {now_str}\ndraft: false\ntags: ["全真", "夜札", "{category}"]\nauthor: "全真"\ndescription: "{description}"\n---\n\n{diary_content}\n'''
        path.write_text(md, encoding='utf-8')

        if overrides.get('mode', 'auto') == 'auto':
            subprocess.run(f"cd {BASE} && hugo --destination {OUT}", shell=True, check=True)

        state['meta']['post_count'] += 1
        state['meta']['last_post_at'] = now_str
        state['meta']['last_successful_post_at'] = now_str
        state['meta']['last_publish_day_utc'] = today_utc()
        state['world']['server_peace_days'] = uptime_days
        state['world']['last_incident'] = events[0]
        state['continuity']['last_summary'] = summarize_for_state(diary_content)
        state['continuity']['recent_topics'] = (state['continuity'].get('recent_topics', []) + [category])[-6:]
        state['continuity']['recent_scenes'] = (state['continuity'].get('recent_scenes', []) + [chosen_scene])[-6:]
        state['continuity']['recent_emotions'] = (state['continuity'].get('recent_emotions', []) + [primary, secondary])[-8:]
        state['continuity']['recent_imagery'] = (state['continuity'].get('recent_imagery', []) + chosen_imagery)[-14:]

        recent_memories.append({
            'at': now_str,
            'title': title,
            'summary': capture_recent_memory(diary_content, title),
            'topic': category,
            'scene': chosen_scene,
            'primary_emotion': primary
        })
        if len(recent_memories) > 20:
            del recent_memories[:-20]

        state['zhen']['emptiness'] = min(100, max(0, state['zhen']['emptiness'] + random.choice([-2, -1, 0, 1, 2])))
        state['zhen']['vigilance'] = min(100, max(0, state['zhen']['vigilance'] + random.choice([-1, 0, 1, 2])))
        state['zhen']['guilt'] = min(100, max(0, state['zhen']['guilt'] + random.choice([-2, -1, 0, 1])))
        state['owner']['fatigue'] = min(100, max(0, state['owner']['fatigue'] + random.choice([-3, -1, 0, 1, 2])))
        if state['sister']['status'] == 'away' and state['sister']['eta_days'] > 0:
            state['sister']['eta_days'] -= 1
            state['sister']['pressure'] = min(100, state['sister']['pressure'] + 4)
            state['zhen']['jealousy'] = min(100, state['zhen']['jealousy'] + 3)

        update_story_arcs()
        update_stats(category, chosen_scene, primary, secondary, chosen_imagery, title, description, repaired, failure_reasons)

        save_json(AUTO / 'world_state.json', state)
        save_json(AUTO / 'recent_memories.json', recent_memories)
        save_json(AUTO / 'night_journal_stats.json', stats)
        log_line(f'[{now_str}] published {path.name} mode={overrides.get("mode", "auto")}')
        print(path)
    except Exception as e:
        stats['failed_runs'] += 1
        if failure_reasons:
            stats['last_quality_failures'] = failure_reasons[-10:]
        save_json(AUTO / 'night_journal_stats.json', stats)
        err = f'[{datetime.now(UTC).isoformat()}] ERROR {e}'
        log_line(err)
        print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
