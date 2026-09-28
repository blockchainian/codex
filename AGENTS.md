# Personal Codex distribution

- 说中文，别废话；准确完成任务，保护不属于本次工作的修改。
- This independent repository belongs to `blockchainian/codex`. Keep only personal
  patches, workflow scripts, and their documentation here. Never import upstream
  source or history into this repository.
- `official/` is the `https://github.com/openai/codex.git` submodule. Its committed
  pointer is the build baseline. Commit pointer changes when upgrading upstream.
- Preserve all existing stashes and local upstream branches. Never push personal
  development commits to the official remote.
- Keep `official/` clean. Develop in a separate worktree created by
  `scripts/develop.sh`; follow that source tree's upstream `AGENTS.md` instructions.
- Apply patches in filename order. Export a new patch relative to the committed
  patched development baseline, never relative to the unpatched official tree.
- Keep patches focused. Do not put generated workspace version or lockfile
  changes into a feature patch. Intentional dependency changes must follow
  upstream dependency and lockfile rules.
- Builds use the committed submodule version and `.work/build`, sharing the
  `official/codex-rs/target` cache. Never edit a worktree during an active build.
- Successful publication cleans only the dedicated build worktree, after a
  successful daemon restart when binaries or links changed. Failures preserve
  diagnostic state. Never use broad cleanup against a development worktree.
- Verify script changes by running `bash -n` on each `scripts/*.sh` file.
  Verify patch changes with `scripts/check-patches.sh`; run relevant upstream
  tests for changed Codex behavior. Keep this patch repository's checks minimal.
- Commit each coherent verified change and push it to this repository.
