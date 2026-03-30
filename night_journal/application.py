from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import load_settings
from .logging_utils import get_logger
from .models import RunResult
from .inputs.state_store import StateStore
from .inputs.content_catalog import ContentCatalog
from .inputs.vps_signals import collect_vps_signals, VpsSignals
from .inputs.recent_posts import build_recent_context
from .narrative.topic_selector import choose_topic
from .narrative.material_selector import choose_world_material
from .narrative.memory_selector import maybe_memory
from .narrative.future_selector import maybe_future_fragment
from .narrative.story_arcs import story_arc_triggers
from .generation import (
    api_chat,
    build_prompt,
    refine_body,
    generate_title_and_description,
)
from .quality.checker import quality_check, guard_publish
from .publishing.writer import write_post
from .publishing.hugo import build_hugo, git_push
from .publishing.registry import get_active_publisher

UTC = timezone.utc


def _translate_vps_events(vps: VpsSignals, event_map: dict) -> list[str]:
    """Translate raw VPS metrics into 古风意象 via event_map_rules."""
    signals = event_map['signals']
    events: list[str] = []

    # SSH intrusions → 江湖宵小
    m = signals['ssh_intrusion']['mapping']
    if vps.ssh_bad <= 0:
        events.append(m[0])
    elif vps.ssh_bad <= 5:
        events.append(m[1])
    elif vps.ssh_bad <= 50:
        events.append(m[2])
    else:
        events.append(m[3])

    # Server load → 堂上风雨
    m = signals['server_load']['mapping']
    pressure = max(vps.load1, vps.mem_pct / 50.0)
    if pressure < 0.5:
        events.append(m[0])
    elif pressure <= 2.0:
        events.append(m[1])
    else:
        events.append(m[2])

    # Uptime → 守夜天数
    m = signals['uptime']['mapping']
    if vps.uptime_days < 30:
        events.append(m[0])
    elif vps.uptime_days < 120:
        events.append(m[1])
    else:
        events.append(m[2])

    # Disk usage
    if vps.disk_pct >= 80:
        events.append(random.choice(signals['disk_usage']['mapping']))

    # Site traffic
    if vps.nginx_hits >= 500:
        events.append(random.choice(signals['site_traffic']['mapping']))

    # Service restarts
    if vps.service_restart_hits > 20:
        events.append(random.choice(signals['service_restart']['mapping']))

    # Certificate renewal (rare)
    if vps.cert_hits > 0 and random.random() < 0.15:
        events.append(signals['certificate_renewal']['mapping'][0])

    return events


def _summarize_for_state(base_url: str, api_key: str, model: str, text: str, max_retries: int, timeout: int) -> str:
    """Use LLM to generate a concise continuity summary for the next run."""
    prompt = (
        '请把下面这篇夜札浓缩成一条 45-70 字的"连续性摘要"，用于下一篇写作时回顾前情。'
        '要求：不要抄原句；写清情绪落点和关键动作；保持概述口吻。\n\n'
        f'原文：\n{text}\n'
    )
    try:
        return api_chat(
            base_url, api_key, model,
            [
                {'role': 'system', 'content': '你是一个克制、准确的摘要器。'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.2, max_tokens=120,
            max_retries=max_retries, timeout=timeout,
        )
    except Exception:
        text = ' '.join(text.strip().split())
        return (text[:70] + '...') if len(text) > 70 else text


def _capture_recent_memory(base_url: str, api_key: str, model: str, text: str, title: str, max_retries: int, timeout: int) -> str:
    """Use LLM to extract a narrative memory fragment from generated post."""
    prompt = (
        '请从下面这篇夜札中提取一条适合写入"近期记忆层"的片段。\n'
        '要求：\n'
        '1. 只写 30-60 字。\n'
        '2. 口吻用第三人称概述。\n'
        '3. 要像近来真实发生过的一件小事。\n'
        '4. 不要抄原文太多。\n\n'
        f'标题：{title}\n正文：\n{text}\n'
    )
    try:
        summary = api_chat(
            base_url, api_key, model,
            [
                {'role': 'system', 'content': '你是一个擅长抽取叙事记忆片段的编辑。'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.3, max_tokens=100,
            max_retries=max_retries, timeout=timeout,
        )
        return summary.strip()
    except Exception:
        return '近来她又在夜里替主人收拾了一处无人会留意的小乱。'


def _update_story_arcs(state: dict) -> None:
    pc = state['meta']['post_count']
    arcs = state.get('story_arcs', {})
    if not arcs:
        return
    dims = state.get('character', {}).get('dimensions', {})
    relations = state.get('relations', {})
    ow = arcs.get('old_wound', {})
    if ow.get('enabled') and pc >= ow.get('next_trigger_post_count', 9999) and ow.get('stage') == 0 and dims.get('guilt', 0) + dims.get('emptiness', 0) >= 58:
        arcs['old_wound']['stage'] = 1
        arcs['old_wound']['next_trigger_post_count'] = pc + 7
    sr = arcs.get('sister_return', {})
    if sr.get('enabled') and pc >= sr.get('next_trigger_post_count', 9999) and dims.get('jealousy', 0) >= 74:
        arcs['sister_return']['stage'] = min(2, sr.get('stage', 0) + 1)
        arcs['sister_return']['next_trigger_post_count'] = pc + 6
        if 'sister' in relations:
            relations['sister']['pressure'] = min(100, relations['sister']['pressure'] + 6)
    on = arcs.get('owner_notice', {})
    owner = relations.get('owner', {})
    if on.get('enabled') and pc >= on.get('next_trigger_post_count', 9999) and owner.get('attention_to_zhen', 0) >= 42:
        arcs['owner_notice']['stage'] = min(2, on.get('stage', 0) + 1)
        arcs['owner_notice']['next_trigger_post_count'] = pc + 8
        owner['attention_to_zhen'] = min(100, owner.get('attention_to_zhen', 0) + 4)


def _drift_state(state: dict, drift_config: dict | None = None) -> None:
    """Apply random emotional drift to world state."""
    dims = state.setdefault('character', {}).setdefault('dimensions', {})
    # Use drift ranges from persona.json if provided, else sensible defaults
    default_drift = {
        'jealousy': [-1, 0, 1, 2, 3],
        'longing': [-1, 0, 1, 2],
        'restraint': [-2, -1, 0, 1],
        'emptiness': [-2, -1, 0, 1, 2],
        'vigilance': [-1, 0, 1, 2],
        'guilt': [-2, -1, 0, 1],
    }
    ranges = drift_config or default_drift
    for dim, choices in ranges.items():
        if dim in dims:
            dims[dim] = min(100, max(0, dims[dim] + random.choice(choices)))
    relations = state.get('relations', {})
    owner = relations.get('owner', {})
    if owner:
        owner['fatigue'] = min(100, max(0, owner.get('fatigue', 0) + random.choice([-3, -1, 0, 1, 2])))
    sister = relations.get('sister', {})
    if sister.get('status') == 'away' and sister.get('eta_days', 0) > 0:
        sister['eta_days'] -= 1
        sister['pressure'] = min(100, sister.get('pressure', 0) + 4)
        if 'jealousy' in dims:
            dims['jealousy'] = min(100, dims['jealousy'] + 3)


def run(
    base_path: Path | None = None,
    mode_override: str | None = None,
    force_topic: str | None = None,
    dry_run: bool = False,
) -> RunResult:
    """
    Main application entry point.
    Orchestrates full night-journal generation pipeline.

    Args:
        base_path: Project root directory path.
        mode_override: Override mode from command line ('auto', 'review', 'manual-only').
        force_topic: Override topic from command line.
    """
    settings = load_settings(base_path)
    logger = get_logger(settings.log_dir)

    store = StateStore(settings)
    catalog = ContentCatalog(settings)

    # --- Load state ---
    state = store.load_world_state()
    overrides = store.load_overrides()

    # Apply command-line overrides if provided
    if mode_override:
        overrides['mode'] = mode_override
    if force_topic:
        overrides['force_topic'] = force_topic
    if dry_run:
        overrides['mode'] = 'manual-only'
        os.environ['MOCK_LLM'] = 'true'

    rules = catalog.load_topic_rules()
    imagery = catalog.load_imagery_pool()
    scenes = catalog.load_scene_pool()
    emotions = catalog.load_emotion_pool()
    recent_memories = store.load_recent_memories()
    future_fragments = store.load_future_fragments()
    stats = store.load_stats()
    persona_cfg = catalog._load_persona().get('character', {})

    # --- Guard: daily limit and mode checks ---
    _today = datetime.now(UTC).strftime('%Y-%m-%d')
    if not dry_run:
        guard_publish(overrides, state, _today)

    base_url = settings.openai_base_url
    api_key = settings.openai_api_key
    model = settings.openai_model

    # --- Collect inputs ---
    vps = collect_vps_signals()
    event_map = catalog.load_event_map_rules()
    events = _translate_vps_events(vps, event_map)
    recent_texts, repeated_phrases, recent_titles, recent_descs = build_recent_context(settings)

    # --- Narrative decisions ---
    category, topic = choose_topic(rules, state, overrides)
    chosen_imagery, chosen_scene, primary, secondary = choose_world_material(
        imagery, scenes, emotions, state, overrides, repeated_phrases
    )
    anchors = store.load_memory_anchors()
    memory_block = maybe_memory(primary, overrides, anchors, recent_memories, rules)
    future_block = maybe_future_fragment(overrides, future_fragments, state.get('story_arcs', {}))
    arc_lines = story_arc_triggers(state, overrides)

    # --- Generation ---
    prompt = build_prompt(
        state=state,
        overrides=overrides,
        rules=rules,
        recent_memories=recent_memories,
        events=events,
        topic=topic,
        memory_block=memory_block,
        future_block=future_block,
        repeated_phrases=repeated_phrases,
        chosen_imagery=chosen_imagery,
        chosen_scene=chosen_scene,
        primary=primary,
        secondary=secondary,
        arc_lines=arc_lines,
        persona_md_path=settings.persona_md_path,
        persona_cfg=persona_cfg,
    )
    system_msg = persona_cfg.get('system_message', '你是一个克制、精炼的叙事者。')
    max_retries = int(os.getenv('MAX_RETRIES', '3'))
    api_timeout = int(os.getenv('API_TIMEOUT', '150'))
    model_fast = settings.openai_model_fast

    raw_body = api_chat(
        base_url, api_key, model,
        [{'role': 'system', 'content': system_msg}, {'role': 'user', 'content': prompt}],
        temperature=0.84, max_tokens=1100,
        max_retries=max_retries, timeout=api_timeout,
    )
    diary_content = refine_body(base_url, api_key, model, raw_body, max_retries=max_retries, timeout=api_timeout)
    title, description = generate_title_and_description(
        base_url, api_key, model, diary_content, recent_titles, recent_descs,
        max_retries=max_retries, timeout=api_timeout,
    )

    # --- Quality check & repair ---
    repaired = False
    failure_reasons: list[str] = []
    from .inputs.recent_posts import recent_posts as _rp
    recent_post_paths_fn = lambda n: [post.path for post in _rp(settings, limit=n)]
    reasons = [] if dry_run else quality_check(diary_content, title, description, overrides, recent_post_paths_fn)
    if reasons:
        repaired = True
        failure_reasons.extend(reasons)
        repair_prompt = f"这篇夜札存在以下问题：{'；'.join(reasons)}。请在不改剧情的前提下重写得更克制、更不重复。只输出正文。\n\n原文：\n{diary_content}"
        diary_content = api_chat(
            base_url, api_key, model,
            [{'role': 'system', 'content': '你是一个擅长修文的冷感写作者。'}, {'role': 'user', 'content': repair_prompt}],
            temperature=0.45, max_tokens=1000,
            max_retries=max_retries, timeout=api_timeout,
        )
        diary_content = refine_body(base_url, api_key, model, diary_content, max_retries=max_retries, timeout=api_timeout)
        title, description = generate_title_and_description(
            base_url, api_key, model, diary_content, recent_titles, recent_descs,
            max_retries=max_retries, timeout=api_timeout,
        )
        reasons = quality_check(diary_content, title, description, overrides, recent_post_paths_fn)
        if reasons:
            failure_reasons.extend(reasons)
            raise RuntimeError('Quality check failed after repair: ' + '; '.join(reasons))

    # --- Output ---
    mode = overrides.get('mode', 'auto')
    path, now_str, slug = write_post(
        title=title,
        description=description,
        category=category,
        body=diary_content,
        overrides=overrides,
        content_dir=settings.content_dir,
        draft_review_dir=settings.draft_review_dir,
    )

    # manual-only mode: skip build/state update
    if path is None:
        if dry_run:
            logger.info(f'[dry-run mode: no files written, no real API calls] skipped topic "{topic}"')
        else:
            logger.info(f'manual-only mode: no file written for topic "{topic}"')
        return RunResult(
            ok=True,
            stage='skipped',
            message=f'Skipped (manual-only mode)',
            data={
                'title': title,
                'slug': slug,
                'mode': mode,
                'category': category,
                'topic': topic,
            },
        )

    # --- Build & Deploy (auto mode only) ---
    if mode == 'auto':
        publisher = get_active_publisher(settings.automation_dir)
        if publisher is not None:
            pub_ok, pub_msg = publisher.publish(title, diary_content, description, category)
            if not pub_ok:
                logger.error(f'Publish failed: {pub_msg}')
                return RunResult(
                    ok=False,
                    stage='publish',
                    message=f'Publish failed: {pub_msg}',
                    data={'path': str(path), 'mode': mode},
                )
            logger.info(f'Published via {type(publisher).__name__}: {pub_msg}')
        else:
            # fallback: hugo
            success, msg = build_hugo(settings.engine_root, destination=settings.output_dir)
            if not success:
                logger.error(f'Hugo build failed: {msg}')
                return RunResult(
                    ok=False,
                    stage='build',
                    message=f'Hugo build failed: {msg}',
                    data={'path': str(path), 'mode': mode},
                )
            logger.info('Hugo build succeeded')

            # Optional: git push if configured
            if os.getenv('ENABLE_GIT_PUSH', 'false').lower() == 'true':
                commit_msg = f'夜札: {title} [{now_str}]'
                push_success, push_msg = git_push(settings.engine_root, commit_msg)
                if push_success:
                    logger.info(f'Git push succeeded: {push_msg}')
                else:
                    logger.warning(f'Git push failed: {push_msg}')

    # --- State update ---
    state['meta']['post_count'] = state['meta'].get('post_count', 0) + 1
    state['meta']['last_post_at'] = now_str
    state['meta']['last_successful_post_at'] = now_str
    state['meta']['last_publish_day_utc'] = _today
    state['world']['server_peace_days'] = vps.uptime_days
    state['world']['last_incident'] = events[0] if events else ''
    state['continuity']['last_summary'] = _summarize_for_state(base_url, api_key, model_fast, diary_content, max_retries, api_timeout)
    state['continuity']['recent_topics'] = (state['continuity'].get('recent_topics', []) + [category])[-6:]
    state['continuity']['recent_scenes'] = (state['continuity'].get('recent_scenes', []) + [chosen_scene])[-6:]
    state['continuity']['recent_emotions'] = (state['continuity'].get('recent_emotions', []) + [primary, secondary])[-8:]
    state['continuity']['recent_imagery'] = (state['continuity'].get('recent_imagery', []) + chosen_imagery)[-14:]
    _drift_state(state, persona_cfg.get('dimension_drift'))
    _update_story_arcs(state)

    # Append new memory to recent_memories
    recent_memories.append({
        'at': now_str,
        'title': title,
        'summary': _capture_recent_memory(base_url, api_key, model_fast, diary_content, title, max_retries, api_timeout),
        'topic': category,
        'scene': chosen_scene,
        'primary_emotion': primary,
    })
    if len(recent_memories) > 20:
        del recent_memories[:-20]

    stats['post_count'] = stats.get('post_count', 0) + 1
    stats['successful_posts'] = stats.get('successful_posts', 0) + 1
    stats.setdefault('topics', {})
    stats['topics'][category] = stats['topics'].get(category, 0) + 1
    if repaired:
        stats['repaired_posts'] = stats.get('repaired_posts', 0) + 1
    if failure_reasons:
        stats['last_quality_failures'] = failure_reasons[-10:]

    store.save_world_state(state)
    store.save_recent_memories(recent_memories)
    store.save_stats(stats)

    logger.info(f'published {path.name} mode={mode} repaired={repaired}')

    return RunResult(
        ok=True,
        stage='complete',
        message=str(path),
        data={
            'title': title,
            'slug': slug,
            'mode': mode,
            'repaired': repaired,
            'failure_reasons': failure_reasons,
            'category': category,
            'topic': topic,
        },
    )
