#!/usr/bin/env python3
"""Finish a published build independently of the active Codex session."""

import argparse
from pathlib import Path
import subprocess
import sys


def finish(codex: str, worktree: Path, restart: bool) -> None:
    expected = Path(__file__).resolve().parents[1] / '.work' / 'build'
    if worktree.resolve() != expected:
        raise ValueError(f'unexpected build worktree: {worktree}')
    common_args = ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir']
    official_common = subprocess.check_output(common_args, cwd=expected.parents[1] / 'official')
    build_common = subprocess.check_output(common_args, cwd=worktree)
    if build_common != official_common:
        raise ValueError('build worktree does not belong to official')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD:official'], cwd=expected.parents[1])
    build_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=worktree)
    if build_commit != commit:
        raise ValueError('build worktree does not match the committed official pointer')
    # Reject foreign files before restarting or changing the worktree.
    untracked = subprocess.check_output(
        ['git', 'ls-files', '--others', '--exclude-standard'], cwd=worktree, text=True
    )
    if untracked:
        raise ValueError(f'untracked files preserved; inspect {worktree}')
    if restart:
        subprocess.run(
            [codex, 'app-server', 'daemon', 'restart'],
            cwd=Path.home() / 'Code',
            check=True,
            timeout=120,
        )
    subprocess.run(
        ['git', 'restore', '--source=HEAD', '--staged', '--worktree', '--', '.'],
        cwd=worktree,
        check=True,
    )
    status = subprocess.check_output(
        ['git', 'status', '--porcelain', '--untracked-files=all'], cwd=worktree, text=True
    )
    if status:
        raise ValueError(f'worktree is still dirty: {worktree}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', required=True)
    parser.add_argument('--worktree', required=True, type=Path)
    parser.add_argument('--restart', action='store_true')
    args = parser.parse_args()
    try:
        finish(args.codex, args.worktree, args.restart)
    except subprocess.TimeoutExpired:
        print('TIMEOUT: daemon restart exceeded 120 seconds; source preserved', flush=True)
        return 1
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'FAILED: {error}; inspect the build worktree', flush=True)
        return 1
    print('COMPLETE: publication finished and build source is clean', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
