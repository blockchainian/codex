#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
worktree="${1:-$repo_root/.worktrees/develop}"
[[ "$worktree" = /* ]] || worktree="$PWD/$worktree"

[[ ! -e "$worktree" ]] || { echo "Worktree already exists: $worktree" >&2; exit 1; }
cd "$repo_root"
commit="$(git rev-parse HEAD:official)"
mkdir -p "$(dirname "$worktree")"
cd "$repo_root/official"
git worktree add --detach "$worktree" "$commit"
"$script_dir/apply-patches.sh" "$worktree"
cd "$worktree"
git -c user.name='Codex patch baseline' -c user.email='patch-baseline@localhost' \
    commit -m 'Apply personal Codex patch baseline'
echo "Develop and test in: $worktree"
echo "Export only your new changes with: git diff --binary HEAD"
