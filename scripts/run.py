#!/usr/bin/env python3
"""
全真夜札引擎 - 主入口脚本

用法:
    python scripts/run.py                    # 自动模式（发布）
    python scripts/run.py --mode review      # 审稿模式（存草稿）
    python scripts/run.py --root /path/to/blog  # 指定项目根目录

环境变量:
    ENGINE_ROOT           # 项目根目录
    BLOG_OUTPUT_DIR       # Hugo 输出目录
    LOG_DIR               # 日志目录
    OPENAI_API_KEY        # OpenAI API 密钥
    OPENAI_BASE_URL       # OpenAI API 基础 URL
    OPENAI_MODEL          # 使用的模型
    ENABLE_GIT_PUSH       # 是否自动 git push (true/false)
"""

import argparse
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from night_journal.application import run

def _load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        k = k.strip()
        if k not in os.environ:
            os.environ[k] = v.strip()



def parse_args():
    parser = argparse.ArgumentParser(
        description='全真夜札引擎 - 自动化博客发文系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--root', '-r',
        type=Path,
        default=None,
        help='项目根目录路径（默认：ENGINE_ROOT 环境变量或当前脚本所在目录的父目录）'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['auto', 'review', 'manual-only'],
        default=None,
        help='运行模式（覆盖 manual_overrides.json 中的设置）'
    )
    parser.add_argument(
        '--force-topic',
        type=str,
        default=None,
        help='强制指定主题'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式：不实际写入文件'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 确定项目根目录
    _load_env(project_root / '.env')
    root = args.root or Path(os.getenv('ENGINE_ROOT', project_root)).resolve()
    print(f'项目根目录: {root}')

    # 显示关键配置
    print(f'OpenAI 模型: {os.getenv("OPENAI_MODEL", "gpt-5.4")}')
    print(f'日志目录: {os.getenv("LOG_DIR", root / "logs")}')

    # 传递命令行参数给引擎
    mode_override = args.mode if args.mode else None
    force_topic_override = args.force_topic if args.force_topic else None

    # 运行引擎
    try:
        result = run(
            base_path=root,
            mode_override=mode_override,
            force_topic=force_topic_override,
            dry_run=args.dry_run,
        )

        if result.ok:
            print(f'\n✓ 夜札生成成功!')
            print(f'  文件: {result.message}')
            print(f'  模式: {result.data.get("mode")}')
            print(f'  标题: {result.data.get("title")}')
            print(f'  分类: {result.data.get("category")}')
            print(f'  主题: {result.data.get("topic")}')
            if result.data.get('repaired'):
                print(f'  已修复问题: {result.data.get("failure_reasons")}')
            return 0
        else:
            print(f'\n✗ 运行失败: {result.message}')
            print(f'  阶段: {result.stage}')
            return 1

    except RuntimeError as e:
        print(f'\n✗ 运行时错误: {e}')
        return 1
    except Exception as e:
        print(f'\n✗ 未预期的错误: {e}')
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
