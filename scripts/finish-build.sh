#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/.." && pwd -P)"
codex=""
worktree=""
restart=false
watchdog_pid=""

fail() { echo "FAILED: $*; inspect the build worktree" >&2; exit 1; }
cleanup() {
    if [[ -n "$watchdog_pid" ]]; then
        kill "$watchdog_pid" 2>/dev/null || true
        wait "$watchdog_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'status=$?; echo "FAILED: command exited with $status; inspect the build worktree" >&2; exit "$status"' ERR

while [[ $# -gt 0 ]]; do
    case "$1" in
        --codex | --worktree)
            [[ $# -ge 2 && -n "$2" ]] || fail "missing value for $1"
            if [[ "$1" == --codex ]]; then codex="$2"; else worktree="$2"; fi
            shift 2
            ;;
        --restart) restart=true; shift ;;
        *) fail "unknown argument: $1" ;;
    esac
done
[[ -n "$codex" && -n "$worktree" ]] || fail "--codex and --worktree are required"
worktree="$(cd "$worktree" && pwd -P)"
[[ "$worktree" == "$repo_root/.work/build" ]] || fail "unexpected build worktree: $worktree"

cd "$repo_root/official"
official_common="$(git rev-parse --path-format=absolute --git-common-dir)"
cd "$repo_root"
commit="$(git rev-parse HEAD:official)"
cd "$worktree"
[[ "$(git rev-parse --path-format=absolute --git-common-dir)" == "$official_common" ]] || fail "build worktree does not belong to official"
[[ "$(git rev-parse HEAD)" == "$commit" ]] || fail "build worktree does not match the committed official pointer"
[[ -z "$(git ls-files --others --exclude-standard)" ]] || fail "untracked files preserved"

if [[ "$restart" == true ]]; then
    (cd "$HOME/Code" && exec "$codex" app-server daemon restart) &
    restart_pid=$!
    parent_pid=$$
    trap 'kill -KILL "$restart_pid" 2>/dev/null || true; wait "$restart_pid" 2>/dev/null || true; echo "TIMEOUT: daemon restart exceeded 120 seconds; source preserved"; exit 124' ALRM
    # Block on completion, with a cancellable watchdog for the fixed deadline.
    (
        sleep 120 &
        sleep_pid=$!
        trap 'kill "$sleep_pid" 2>/dev/null || true; wait "$sleep_pid" 2>/dev/null || true; exit 0' TERM
        wait "$sleep_pid"
        kill -ALRM "$parent_pid" 2>/dev/null || true
    ) &
    watchdog_pid=$!
    wait "$restart_pid"
    cleanup
    watchdog_pid=""
    trap - ALRM
fi

git restore --source=HEAD --staged --worktree -- .
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "worktree is still dirty"
echo "COMPLETE: publication finished and build source is clean"
