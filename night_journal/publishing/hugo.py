from __future__ import annotations

import subprocess
from pathlib import Path


def build_hugo(site_root: Path, destination: Path | None = None, timeout: int = 60) -> tuple[bool, str]:
    """
    Run `hugo` in the given site root directory.
    Returns (success, output_or_error_message).
    """
    try:
        cmd = ['hugo']
        if destination:
            cmd.extend(['--destination', str(destination)])
        result = subprocess.run(
            cmd,
            cwd=site_root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr or result.stdout).strip()
    except FileNotFoundError:
        return False, 'hugo binary not found'
    except subprocess.TimeoutExpired:
        return False, f'hugo build timed out after {timeout}s'
    except Exception as e:
        return False, str(e)


def git_push(site_root: Path, commit_msg: str, timeout: int = 60) -> tuple[bool, str]:
    """
    Stage all changes, commit, and push in the given directory.
    Returns (success, output_or_error_message).
    """
    try:
        for cmd in [
            ['git', 'add', '-A'],
            ['git', 'commit', '-m', commit_msg],
            ['git', 'push'],
        ]:
            result = subprocess.run(
                cmd,
                cwd=site_root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and 'nothing to commit' not in result.stdout:
                return False, (result.stderr or result.stdout).strip()
        return True, 'pushed'
    except Exception as e:
        return False, str(e)
