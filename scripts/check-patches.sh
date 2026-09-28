#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
worktree="$repo_root/.work/check-patches"

[[ ! -e "$worktree" ]] || { echo "Inspect existing check worktree: $worktree" >&2; exit 1; }
cd "$repo_root/official"
commit="$(git rev-parse HEAD)"
mkdir -p "$repo_root/.work"
git worktree add --detach "$worktree" "$commit"
"$script_dir/apply-patches.sh" "$worktree"
cd "$worktree"
git restore --source=HEAD --staged --worktree -- .
cd "$repo_root/official"
git worktree remove "$worktree"
echo "All patches apply in order to $commit"
