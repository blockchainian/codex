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

## Tools

- `./scripts/develop.sh` — creates the patched development worktree in `.worktrees/develop`
- `./scripts/check-patches.sh` — checks that all patches apply in order
- `./scripts/build.sh` — builds the committed submodule version in `.worktrees/build` and publishes it, sharing the `official/codex-rs/target` cache

> **Warning**
>
> - Keep `official/` clean; develop only in the worktree created by `scripts/develop.sh`
> - Never edit a worktree during an active build
> - Successful publication cleans only the build worktree, after a successful daemon restart when binaries or links changed
> - Failures preserve diagnostic state; never use broad cleanup against a development worktree

## Checks

- **scripts**: `bash -n scripts/<name>.sh` for each script — checks syntax only, does not run it
- **patches**: `./scripts/check-patches.sh`
- **Codex behavior**: the relevant upstream tests

Keep this repository's own checks minimal.

## Version control

- Commit each coherent verified change and push it to this repository.
- Commit `official` pointer changes when upgrading upstream.
- Preserve all existing stashes and local upstream branches.
- Never push personal development commits to the official remote.
