#!/usr/bin/env python3
"""全真夜札系统 - 健康检查脚本"""
import json
import os
import sys
from pathlib import Path

BASE = Path(os.getenv('ENGINE_ROOT', Path(__file__).resolve().parent.parent))
AUTO = BASE / 'automation'
CONTENT = BASE / 'content' / 'posts'
DRAFT = BASE / 'draft_review'

def check_file(path, name):
    if path.exists():
        print(f"✅ {name}: {path}")
        return True
    else:
        print(f"❌ {name}: {path} (缺失)")
        return False

def check_json(path, name):
    if not path.exists():
        print(f"❌ {name}: {path} (缺失)")
        return False
    try:
        json.loads(path.read_text(encoding='utf-8'))
        print(f"✅ {name}: {path}")
        return True
    except Exception as e:
        print(f"❌ {name}: {path} (JSON 错误: {e})")
        return False

def main():
    print("== 全真夜札系统健康检查 ==\n")
    
    print("1. 核心配置文件检查:")
    all_good = True
    all_good &= check_json(AUTO / 'world_state.json', "世界状态机")
    all_good &= check_json(AUTO / 'topic_rules.json', "主题规则")
    all_good &= check_json(AUTO / 'event_map_rules.json', "现实映射规则")
    all_good &= check_json(AUTO / 'manual_overrides.json', "手动覆盖")
    all_good &= check_json(AUTO / 'night_journal_stats.json', "统计信息")
    
    print("\n2. 素材池检查:")
    all_good &= check_json(AUTO / 'imagery_pool.json', "意象池")
    all_good &= check_json(AUTO / 'scene_pool.json', "场景池")
    all_good &= check_json(AUTO / 'emotion_pool.json', "情绪池")
    all_good &= check_json(AUTO / 'memory_anchors.json', "核心记忆锚点")
    all_good &= check_json(AUTO / 'future_fragments.json', "未来片段")
    all_good &= check_json(AUTO / 'recent_memories.json', "中期记忆层")
    
    print("\n3. 目录结构检查:")
    all_good &= check_dir(CONTENT, "文章发布目录")
    all_good &= check_dir(DRAFT, "审稿目录")
    all_good &= check_dir(BASE / 'logs', "日志目录")
    all_good &= check_file(BASE / 'hugo.toml', "Hugo 配置")
    
    print("\n4. 环境变量检查:")
    env_vars = ['OPENAI_API_KEY', 'OPENAI_MODEL', 'ENGINE_ROOT']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:10]}...")
        else:
            print(f"⚠️  {var}: 未设置（将使用默认值）")
    
    print("\n5. 内容文件检查:")
    posts = list(CONTENT.glob('*.md')) + list(DRAFT.glob('*.md'))
    print(f"✅ 找到 {len(posts)} 篇文章")
    
    if len(posts) > 0:
        latest = sorted(posts, key=lambda p: p.stat().st_mtime, reverse=True)[0]
        print(f"✅ 最新文章: {latest.name}")
    
    print("\n6. 配置文件内容检查:")
    # 检查 world_state 关键字段
    try:
        state = json.loads((AUTO / 'world_state.json').read_text(encoding='utf-8'))
        required_keys = ['meta', 'owner', 'sister', 'zhen', 'continuity', 'story_arcs']
        for key in required_keys:
            if key in state:
                print(f"✅ world_state.{key}")
            else:
                print(f"❌ world_state.{key} (缺失)")
                all_good = False
    except Exception as e:
        print(f"❌ 无法解析 world_state.json: {e}")
        all_good = False
    
    print(f"\n== 检查结果: {'✅ 系统健康' if all_good else '❌ 存在问题'} ==")
    return 0 if all_good else 1

def check_dir(path, name):
    if path.exists() and path.is_dir():
        print(f"✅ {name}: {path}")
        return True
    else:
        print(f"❌ {name}: {path} (目录不存在)")
        return False

if __name__ == '__main__':
    sys.exit(main())
