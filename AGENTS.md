# AGENTS.md

> Before working in a Codex source worktree, read its `AGENTS.md`.

This repo is `blockchainian/codex`, personal patches and build tooling for OpenAI Codex.

说中文，别废话；准确完成任务，保护不属于本次工作的修改。

## Modules

- patches/ -- ordered personal patches
- scripts/ -- develop, check, build, and publish tools
- official/ -- the `https://github.com/openai/codex.git` submodule; its committed pointer is the build baseline
- .worktrees/ -- disposable worktrees: `build`, `develop`, `check-patches`

Keep only personal patches, workflow scripts, and their documentation here. Never import upstream source or history.

## Patches

Apply patches in filename order.

Export a new patch relative to the committed patched development baseline, never relative to the unpatched official tree.

Keep patches focused. Do not put generated workspace version or lockfile changes into a feature patch. Intentional dependency changes must follow upstream dependency and lockfile rules.

To change an existing patch, recreate the baseline before it and amend that patch. Never add a patch that undoes another.

## Tools

### Set up official Codex

- `git clone --recurse-submodules https://github.com/blockchainian/codex.git` — clones the repo with the submodule
- `git submodule update --init official` — fetches the submodule in an existing clone

### Upgrade official Codex

- `git -C official fetch origin main` — fetches the latest official commits
- `git -C official checkout --detach origin/main` — moves the submodule to them
- `./scripts/check-patches.sh` — checks the patches against the new baseline; a conflict leaves `.worktrees/check-patches` for inspection
- `git add official patches` — stages the pointer and the repaired patches for one commit
- `./scripts/build.sh` — builds and publishes the upgraded version

> **Warning**
>
> - Never run `git submodule update --remote`; builds must use the committed pointer
> - To abandon an upgrade, preserve any changes, then run `git submodule update official`

### Develop a patch

- `./scripts/develop.sh` — creates the development worktree in `.worktrees/develop`, with all patches committed as the baseline
- `git add <feature-files>` — stages the feature in the worktree root, including new files and snapshot updates
- `git diff --binary --cached HEAD > ../../patches/<NNNN>-<name>.patch` — exports the staged feature as a patch
- `./scripts/check-patches.sh` — checks that all patches apply in order

> **Warning**
>
> - Keep `official/` clean; develop only in the worktree created by `scripts/develop.sh`
> - Export before committing in the worktree, so `HEAD` still names the patched baseline
> - If other patches changed while you were developing, test the complete stack in a fresh worktree

### Build and publish

- `./scripts/build.sh` — builds the committed submodule version in `.worktrees/build` and publishes it, sharing the `official/codex-rs/target` cache
- `cat ~/.codex/app-server-daemon/customized-app-server.stderr.log` — shows the final result: `COMPLETE`, `FAILED`, or `TIMEOUT`

The build needs a clean repository and a clean `official/` at the committed pointer. It takes the package version from the latest stable official release tag, and publishes the binaries to `~/.local/share/codex-customized/bin`.

> **Warning**
>
> - Never edit a worktree during an active build
> - Do not start another build until the log shows a result; the daemon restart runs detached, with a 120-second deadline
> - Successful publication cleans only the build worktree, after a successful daemon restart when binaries or links changed
> - Failures preserve diagnostic state; inspect or save it before retrying
> - Never use broad cleanup against a development worktree

## Checks

Keep this repository's own checks minimal.

- **patches**: `./scripts/check-patches.sh`
- **Codex**: the relevant upstream tests

## Version control

- Commit each coherent verified change and push it to this repository.
- Commit `official` pointer changes when upgrading upstream.
- Preserve all existing stashes and local upstream branches.
- Never push personal development commits to the official remote.
