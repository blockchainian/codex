import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('finish_build', ROOT / 'scripts/finish-build.py')
FINISH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINISH)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'Code').mkdir()
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts')
        (self.root / 'patches').mkdir()
        self.source = self.root / 'official'
        self.source.mkdir()
        self.git(self.source, 'init', '-b', 'main')
        self.git(self.source, 'config', 'user.name', 'Workflow test')
        self.git(self.source, 'config', 'user.email', 'test@localhost')
        (self.source / 'codex-rs').mkdir()
        (self.source / 'codex-rs/Cargo.toml').write_text('[workspace.package]\nversion = "0.0.0"\n')
        (self.source / 'feature').write_text('official\n')
        (self.source / '.gitignore').write_text('/codex-rs/target/\n')
        v8_script = self.source / '.github/scripts/rusty_v8_bazel.py'
        v8_script.parent.mkdir(parents=True)
        v8_script.write_text('print("1.0.0")\n')
        self.git(self.source, 'add', '.')
        self.git(self.source, 'commit', '-m', 'official')
        self.commit = self.git(self.source, 'rev-parse', 'HEAD').strip()
        for number, new in (
            ('0001', 'patched'),
            ('0002', 'stacked'),
        ):
            (self.source / 'feature').write_text(f'{new}\n')
            diff = self.git(self.source, 'diff')
            (self.root / 'patches' / f'{number}-feature.patch').write_text(diff)
            self.git(self.source, 'add', 'feature')
            self.git(self.source, 'commit', '-m', new)
        self.git(self.source, 'checkout', '--detach', self.commit)
        self.git(self.root, 'init', '-b', 'main')
        self.git(self.root, 'config', 'user.name', 'Workflow test')
        self.git(self.root, 'config', 'user.email', 'test@localhost')
        (self.root / '.gitmodules').write_text(
            '[submodule "official"]\n\tpath = official\n\turl = https://github.com/openai/codex.git\n'
        )
        (self.root / '.gitignore').write_text('/.work/\n__pycache__/\n')
        self.git(self.root, 'add', '.gitmodules', '.gitignore', 'scripts', 'patches')
        self.git(self.root, 'update-index', '--add', '--cacheinfo', f'160000,{self.commit},official')
        self.git(self.root, 'commit', '-m', 'pin official')

    def git(self, cwd, *args):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL)

    def script(self, name, *args):
        return subprocess.run(
            ['bash', str(self.root / 'scripts' / name), *map(str, args)],
            cwd=self.root, text=True, capture_output=True, timeout=30,
        )

    def build_worktree(self):
        worktree = self.root / '.work/build'
        worktree.parent.mkdir()
        self.git(self.source, 'worktree', 'add', '--detach', str(worktree), self.commit)
        result = self.script('apply-patches.sh', worktree)
        self.assertEqual(result.returncode, 0, result.stderr)
        return worktree

    def test_stack_order_and_cleanup(self):
        worktree = self.build_worktree()
        self.assertEqual((worktree / 'feature').read_text(), 'stacked\n')
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            FINISH.finish('/unused/codex', worktree, restart=False)
        self.assertEqual((worktree / 'feature').read_text(), 'official\n')
        self.assertEqual(self.git(worktree, 'status', '--porcelain'), '')
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), '')

    def test_dirty_source_is_preserved(self):
        (self.source / 'feature').write_text('unfinished user work\n')
        result = self.script('apply-patches.sh', self.source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.source / 'feature').read_text(), 'unfinished user work\n')

    def test_build_uses_pinned_source_and_shared_cache(self):
        tools = self.root / '.work/tools'
        tools.mkdir(parents=True)
        git_path = shutil.which('git')
        scripts = {
            'git': f'#!/bin/sh\nif [ "$1" = ls-remote ]; then echo "123 refs/tags/rust-v1.2.3"; else exec "{git_path}" "$@"; fi\n',
            'rustc': '#!/bin/sh\necho "host: x86_64-apple-darwin"\n',
            'cargo': '#!/bin/sh\nmkdir -p "$CARGO_TARGET_DIR/release"\nfor name in codex codex-code-mode-host codex-responses-api-proxy; do\n  printf "#!/bin/sh\\nexit 0\\n" > "$CARGO_TARGET_DIR/release/$name"\n  chmod +x "$CARGO_TARGET_DIR/release/$name"\ndone\n',
        }
        for name, content in scripts.items():
            path = tools / name
            path.write_text(content)
            path.chmod(0o755)
        artifacts = self.source / 'codex-rs/target/rusty_v8/1.0.0/x86_64-apple-darwin'
        artifacts.mkdir(parents=True)
        names = (
            'librusty_v8_ptrcomp_sandbox_release_x86_64-apple-darwin.a.gz',
            'src_binding_ptrcomp_sandbox_release_x86_64-apple-darwin.rs',
        )
        checksums = []
        for name in names:
            content = name.encode()
            (artifacts / name).write_bytes(content)
            checksums.append(f'{hashlib.sha256(content).hexdigest()}  {name}\n')
        (artifacts / 'rusty_v8_ptrcomp_sandbox_release_x86_64-apple-darwin.sha256').write_text(''.join(checksums))
        # Exercise real build preparation and cleanup with compilation/publication stubs.
        (self.root / 'scripts/publish.sh').write_text(
            '#!/bin/sh\nset -eu\nscript_dir="$(dirname "$0")"\n'
            'python3 "$script_dir/finish-build.py" --codex "$1/codex" --worktree "$2"\n'
        )
        (self.root / 'scripts/publish.sh').chmod(0o755)
        self.git(self.root, 'add', 'scripts/publish.sh')
        self.git(self.root, 'commit', '-m', 'stub publication')
        result = subprocess.run(
            ['bash', str(self.root / 'scripts/build.sh')], cwd=self.root,
            env={**os.environ, 'PATH': f'{tools}:{os.environ["PATH"]}'},
            text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Building Codex version 1.2.3', result.stdout)
        self.assertTrue((self.source / 'codex-rs/target/release/codex').exists())
        self.assertEqual(self.git(self.root / '.work/build', 'rev-parse', 'HEAD').strip(), self.commit)
        self.assertEqual(self.git(self.root / '.work/build', 'status', '--porcelain'), '')
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), '')

    def test_build_rejects_uncommitted_submodule_upgrade(self):
        self.git(self.source, 'checkout', 'main')
        result = self.script('build.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / '.work/build').exists())

    def test_cleanup_removes_files_added_by_patch(self):
        worktree = self.build_worktree()
        (worktree / 'new-feature').write_text('new\n')
        self.git(worktree, 'add', 'new-feature')
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            FINISH.finish('/unused/codex', worktree, restart=False)
        self.assertFalse((worktree / 'new-feature').exists())
        self.assertEqual(self.git(worktree, 'status', '--porcelain'), '')

    def test_patch_failure_preserves_previous_patches(self):
        (self.root / 'patches/0002-feature.patch').write_text('invalid patch\n')
        result = self.script('apply-patches.sh', self.source)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.source / 'feature').read_text(), 'patched\n')

    def test_development_baseline_exports_only_new_feature(self):
        result = self.script('develop.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        worktree = self.root / '.work/develop'
        self.assertEqual(self.git(worktree, 'status', '--porcelain'), '')
        (worktree / 'feature').write_text('new feature\n')
        diff = self.git(worktree, 'diff', 'HEAD')
        self.assertIn('-stacked\n+new feature\n', diff)
        self.assertNotIn('-official\n', diff)
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), '')

    def test_check_removes_only_its_clean_worktree(self):
        result = self.script('check-patches.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / '.work/check-patches').exists())
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), '')

    def test_successful_restart_occurs_once_before_cleanup(self):
        worktree = self.build_worktree()
        codex = self.root / 'codex'
        marker = self.root / 'restart-count'
        codex.write_text(f'#!/bin/sh\necho restart >> "{marker}"\n')
        codex.chmod(0o755)
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            with patch.object(FINISH.Path, 'home', return_value=self.root):
                FINISH.finish(str(codex), worktree, restart=True)
        self.assertEqual(marker.read_text(), 'restart\n')
        self.assertEqual(self.git(worktree, 'status', '--porcelain'), '')

    def test_failed_restart_preserves_patch_state(self):
        worktree = self.build_worktree()
        codex = self.root / 'codex'
        codex.write_text('#!/bin/sh\nexit 7\n')
        codex.chmod(0o755)
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            with patch.object(FINISH.Path, 'home', return_value=self.root):
                with self.assertRaises(subprocess.CalledProcessError):
                    FINISH.finish(str(codex), worktree, restart=True)
        self.assertEqual((worktree / 'feature').read_text(), 'stacked\n')

    def test_restart_timeout_preserves_patch_state(self):
        worktree = self.build_worktree()
        run = subprocess.run

        def timeout_on_restart(args, **kwargs):
            if args[0] == 'codex':
                raise subprocess.TimeoutExpired('codex', 120)
            return run(args, **kwargs)

        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            with patch.object(FINISH.subprocess, 'run', side_effect=timeout_on_restart):
                with self.assertRaises(subprocess.TimeoutExpired):
                    FINISH.finish('codex', worktree, restart=True)
        self.assertEqual((worktree / 'feature').read_text(), 'stacked\n')

    def test_untracked_files_are_preserved(self):
        worktree = self.build_worktree()
        (worktree / 'user-note').write_text('keep me\n')
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            with self.assertRaises(ValueError):
                FINISH.finish('/unused/codex', worktree, restart=False)
        self.assertEqual((worktree / 'user-note').read_text(), 'keep me\n')
        self.assertEqual((worktree / 'feature').read_text(), 'stacked\n')

    def test_development_worktree_cannot_be_cleaned(self):
        with patch.object(FINISH, '__file__', str(self.root / 'scripts/finish-build.py')):
            with self.assertRaises(ValueError):
                FINISH.finish('/unused/codex', self.source, restart=False)


if __name__ == '__main__':
    unittest.main()
