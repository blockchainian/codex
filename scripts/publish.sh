#!/usr/bin/env bash
set -euo pipefail

source_dir="${1:?usage: publish.sh RELEASE_DIR BUILD_WORKTREE}"
build_dir="${2:?usage: publish.sh RELEASE_DIR BUILD_WORKTREE}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install_dir="$HOME/.local/share/codex-customized/bin"
legacy_dir="$HOME/Code/blockchainian/dot/darwin/bin"
link_dirs=("$HOME/.local/bin" "$HOME/.codex/packages/standalone/current")
binaries=(codex codex-code-mode-host codex-responses-api-proxy)
staged=()
copy_temps=()
copy_names=()

fail() { echo "publish.sh: $*" >&2; exit 1; }
cleanup() {
    for path in "${staged[@]-}"; do
        [[ -n "$path" ]] || continue
        if [[ -e "$path" || -L "$path" ]]; then
            rm -f "$path"
        fi
    done
}
trap cleanup EXIT

[[ "$(uname -s)" == Darwin ]] || fail "macOS required"
[[ "$build_dir" == "$(cd "$script_dir/.." && pwd)/.worktrees/build" ]] || fail "unexpected build worktree: $build_dir"
[[ -d "$source_dir" ]] || fail "release directory missing: $source_dir"
for binary in "${binaries[@]}"; do
    [[ -x "$source_dir/$binary" ]] || fail "missing binary: $source_dir/$binary"
    for dir in "${link_dirs[@]}"; do
        link="$dir/$binary"
        if [[ -L "$link" ]]; then
            target="$(readlink "$link")"
            [[ "$target" == "$legacy_dir/$binary" || "$target" == "$install_dir/$binary" ]] || fail "unexpected link: $link -> $target"
        elif [[ -e "$link" ]]; then
            fail "existing non-symlink: $link"
        fi
    done
done
version="$("$source_dir/codex" --version)"
[[ "$version" == codex-cli\ * ]] || fail "unexpected version: $version"

mkdir -p "$install_dir" "${link_dirs[@]}"
changed=false
for binary in "${binaries[@]}"; do
    if ! cmp -s "$source_dir/$binary" "$install_dir/$binary"; then
        temp="$(mktemp "$install_dir/.$binary.XXXXXX")"
        staged+=("$temp")
        copy_temps+=("$temp")
        copy_names+=("$binary")
        cp "$source_dir/$binary" "$temp"
        chmod 0755 "$temp"
    fi
done
for index in "${!copy_temps[@]}"; do
    mv -f "${copy_temps[$index]}" "$install_dir/${copy_names[$index]}"
    changed=true
done
for binary in "${binaries[@]}"; do
    for dir in "${link_dirs[@]}"; do
        link="$dir/$binary"
        if [[ ! -L "$link" || "$(readlink "$link")" != "$install_dir/$binary" ]]; then
            temp="$(mktemp "$dir/.$binary.XXXXXX")"
            staged+=("$temp")
            rm "$temp"
            ln -s "$install_dir/$binary" "$temp"
            mv -f "$temp" "$link"
            changed=true
        fi
    done
done

finish_args=(--codex "$install_dir/codex" --worktree "$build_dir")
if [[ "$changed" == true ]]; then
    echo "Published $version to $install_dir"
    finish_args+=(--restart)
else
    echo "Already published: $version"
fi
restart_log="$HOME/.codex/app-server-daemon/customized-app-server.stderr.log"
mkdir -p "$(dirname "$restart_log")"
(
    cd "$HOME/Code"
    nohup "$script_dir/finish-build.sh" "${finish_args[@]}" \
        </dev/null >"$restart_log" 2>&1 &
)
echo "Completion task started; final COMPLETE, FAILED, or TIMEOUT result: $restart_log"
