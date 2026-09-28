#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
source_root="$repo_root/.work/build"
official_root="$repo_root/official"

fail() { echo "build.sh: $*" >&2; exit 1; }

cd "$repo_root"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "commit repository changes before building"
commit="$(git rev-parse HEAD:official)"
cd "$official_root"
[[ "$(git rev-parse HEAD)" == "$commit" ]] || fail "official does not match the committed submodule pointer"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "official must be clean"
common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
mkdir -p "$repo_root/.work"
if [[ -e "$source_root" ]]; then
    cd "$source_root"
    [[ "$(git rev-parse --show-toplevel)" == "$source_root" ]] || fail "unexpected build worktree location"
    [[ "$(git rev-parse --path-format=absolute --git-common-dir)" == "$common_dir" ]] || fail "build worktree does not belong to official"
    [[ -z "$(git status --porcelain --untracked-files=all)" ]] || fail "previous build is dirty; inspect it before retrying"
    git checkout --detach "$commit"
else
    cd "$official_root"
    git worktree add --detach "$source_root" "$commit"
fi
"$script_dir/apply-patches.sh" "$source_root"
cd "$source_root"

version="$(git ls-remote --tags origin 'rust-v*' | python3 -c '
import re
import sys
versions = [tuple(map(int, match.groups())) for line in sys.stdin
            if (match := re.fullmatch(r"refs/tags/rust-v(\d+)\.(\d+)\.(\d+)", line.split()[-1]))]
if not versions:
    raise SystemExit("no stable rust-v release tag found")
print(".".join(map(str, max(versions))))
')"
python3 - "$version" <<'PY'
from pathlib import Path
import re
import sys

path = Path('codex-rs/Cargo.toml')
text = path.read_text()
start = text.index('[workspace.package]\n')
line_start = text.index('version = ', start)
line_end = text.index('\n', line_start)
line = text[line_start:line_end]
if not re.fullmatch(r'version = "[0-9]+\.[0-9]+\.[0-9]+"', line):
    raise SystemExit(f'unexpected workspace version: {line}')
path.write_text(text[:line_start] + f'version = "{sys.argv[1]}"' + text[line_end:])
PY
echo "Building Codex version $version"

codex_rs_dir="$source_root/codex-rs"
export CARGO_TARGET_DIR="$official_root/codex-rs/target"
v8_version="$(python3 "$source_root/.github/scripts/rusty_v8_bazel.py" resolved-v8-crate-version)"
v8_target="$(rustc -vV | sed -n 's/^host: //p')"
v8_profile="ptrcomp_sandbox_release"
v8_dir="$CARGO_TARGET_DIR/rusty_v8/$v8_version/$v8_target"
v8_release_url="https://github.com/openai/codex/releases/download/rusty-v8-v${v8_version}"

case "$v8_target" in
    *-pc-windows-msvc) archive_name="rusty_v8_${v8_profile}_${v8_target}.lib.gz" ;;
    *-apple-darwin | *-unknown-linux-gnu | *-unknown-linux-musl)
        archive_name="librusty_v8_${v8_profile}_${v8_target}.a.gz" ;;
    *) fail "unsupported rusty_v8 target: $v8_target" ;;
esac

binding_name="src_binding_${v8_profile}_${v8_target}.rs"
checksums_name="rusty_v8_${v8_profile}_${v8_target}.sha256"
archive_path="$v8_dir/$archive_name"
binding_path="$v8_dir/$binding_name"
checksums_path="$v8_dir/$checksums_name"

download() {
    local name="$1"
    local destination="$v8_dir/$name"
    echo "Downloading $name"
    curl --fail --location --silent --show-error --retry 3 \
        "$v8_release_url/$name" --output "$destination.tmp"
    mv "$destination.tmp" "$destination"
}

verify_artifacts() {
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$v8_dir" && tr -d '\r' < "$checksums_name" | sha256sum -c -)
    else
        (cd "$v8_dir" && tr -d '\r' < "$checksums_name" | shasum -a 256 -c -)
    fi
}

mkdir -p "$v8_dir"
[[ -f "$checksums_path" ]] || download "$checksums_name"
checksum_count="$(awk 'NF { count++ } END { print count + 0 }' "$checksums_path")"
[[ "$checksum_count" -eq 2 ]] || fail "expected two checksums in $checksums_path"
if ! verify_artifacts >/dev/null 2>&1; then
    download "$archive_name"
    download "$binding_name"
fi
verify_artifacts

unset V8_FROM_SOURCE
cd "$codex_rs_dir"
RUSTY_V8_ARCHIVE="$archive_path" \
RUSTY_V8_SRC_BINDING_PATH="$binding_path" \
    cargo build --release \
        --bin codex \
        --bin codex-code-mode-host \
        --bin codex-responses-api-proxy

for binary in codex codex-code-mode-host codex-responses-api-proxy; do
    path="$CARGO_TARGET_DIR/release/$binary"
    [[ -x "$path" ]] || fail "missing built binary: $path"
    echo "$path"
done

"$script_dir/publish.sh" "$CARGO_TARGET_DIR/release" "$source_root"
