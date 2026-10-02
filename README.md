# Personal Codex

Personal patches and build tooling for [OpenAI Codex](https://github.com/openai/codex).
The `official/` submodule pins the upstream commit. This repository does not
contain a copy of the upstream source or upstream commit history.

```text
AGENTS.md        Instructions for this repository
patches/         Ordered personal patches
scripts/         Build, publish, and development tools
official/        Pinned OpenAI Codex submodule
```

## Setup and build

```sh
git clone --recurse-submodules https://github.com/blockchainian/codex.git
cd codex
./scripts/build.sh
```

For an existing clone, run `git submodule update --init official` first.
Install the prerequisites listed by the official source repository. Publication
uses the existing macOS CLI and standalone installation locations.

The build requires a clean parent repository and clean submodule at the committed
pointer. It applies the patches in `.worktrees/build`, sets the package version from
the latest stable official release tag, and builds three release binaries using
`official/codex-rs/target` as the shared cache. Outputs are copied to
`~/.local/share/codex-customized/bin` and the existing installation links updated.

A detached `scripts/finish-build.sh` task restarts the managed daemon once if
binaries or links changed, then restores the dedicated build source to its original commit. It
does not remove build caches or development worktrees. The restart has a
120-second deadline. Check the final result:

```sh
cat ~/.codex/log/customized-daemon-restart.log
```

`COMPLETE` means publication finished and the source is clean. `FAILED` or
`TIMEOUT` means inspection is required; source is preserved after a failed
restart. Do not start another build until the completion task has finished.
Patch or compile failures also preserve `.worktrees/build`; inspect or save the
changes before restoring that disposable worktree and retrying.

## Upgrade official Codex

```sh
cd official
git fetch origin main
git checkout --detach origin/main
cd ..
./scripts/check-patches.sh
```

The check applies patches in order in a temporary worktree. A conflict leaves the
worktree available for inspection. Repair the relevant patch, run applicable
upstream tests, and commit the patch changes and `official` pointer together:

```sh
git add official patches
git commit -m 'Update official Codex and refresh patches'
./scripts/build.sh
git push
```

Do not run `git submodule update --remote` during a normal build: builds must use
the committed pointer. To return to the committed baseline after an abandoned
upgrade, first preserve any changes, then run `git submodule update official`.

## Develop a new patch

```sh
./scripts/develop.sh
cd .worktrees/develop/codex-rs
```

This creates a detached development worktree at the committed official version,
applies all patches in order, and creates a local baseline commit. Implement the
feature on this patched baseline and run upstream's formatter and relevant tests,
including snapshot review for UI changes. Follow the worktree's `AGENTS.md`.

To export a new patch, return to the development worktree root and stage only the
intended feature files, including new files and snapshot updates:

```sh
git add <feature-files>
git diff --binary --cached HEAD > ../../patches/0009-my-feature.patch
```

Export before creating further development commits, so `HEAD` still names the
patched baseline. The resulting patch contains only the new feature. Back at the
parent repository, run `./scripts/check-patches.sh`, then commit the new patch.
If other patches changed while you were developing, test the new complete stack
in a fresh worktree before publishing.

For an existing patch, recreate its preceding patch baseline and amend that
patch; avoid adding a patch that simply undoes another patch.

## Checks

```sh
for script in scripts/*.sh; do bash -n "$script"; done
./scripts/check-patches.sh
```

These checks cover Shell syntax and patch applicability. They do not replace
the relevant upstream tests or a release build for changed Codex behavior.
