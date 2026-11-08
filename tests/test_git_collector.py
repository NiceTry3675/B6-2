import subprocess
import tempfile
import unittest
from pathlib import Path

from gitgen.git_collector import GitError, collect_changes, ensure_repo_root, parse_status


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


class GitRepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name).resolve()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "commit.gpgsign", "false")
        (self.repo / "a.py").write_text("print('a')\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()


class CollectTest(GitRepoTestCase):
    def test_no_changes(self):
        self.assertTrue(collect_changes(self.repo).is_empty)

    def test_working_tree_includes_untracked(self):
        (self.repo / "a.py").write_text("print('b')\n")
        (self.repo / "새파일.py").write_text("x = 1\n")
        changes = collect_changes(self.repo)
        self.assertEqual(changes.mode, "working-tree")
        self.assertEqual({f.path for f in changes.files}, {"a.py", "새파일.py"})
        self.assertIn("+print('b')", changes.diff)
        self.assertIn("+x = 1", changes.diff)

    def test_staged_preferred(self):
        (self.repo / "a.py").write_text("print('staged')\n")
        git(self.repo, "add", "a.py")
        (self.repo / "b.py").write_text("unstaged\n")
        changes = collect_changes(self.repo)
        self.assertEqual(changes.mode, "staged")
        self.assertEqual([f.path for f in changes.files], ["a.py"])
        self.assertNotIn("unstaged", changes.diff)

    def test_base_branch_diff(self):
        git(self.repo, "checkout", "-q", "-b", "feature")
        (self.repo / "c.py").write_text("feature\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "feat")
        changes = collect_changes(self.repo, base="main")
        self.assertEqual(changes.branch, "feature")
        self.assertEqual([f.path for f in changes.files], ["c.py"])
        self.assertIn("+feature", changes.diff)


class RepoRootTest(GitRepoTestCase):
    def test_root_ok(self):
        self.assertEqual(ensure_repo_root(self.repo), self.repo)

    def test_subdirectory_rejected(self):
        sub = self.repo / "sub"
        sub.mkdir()
        with self.assertRaises(GitError):
            ensure_repo_root(sub)

    def test_not_a_repo(self):
        with tempfile.TemporaryDirectory() as d, self.assertRaises(GitError):
            ensure_repo_root(Path(d))


class ParseStatusTest(unittest.TestCase):
    def test_parse(self):
        staged, unstaged, untracked = parse_status("M  a.py\n M b.py\nR  old.py -> new.py\n?? c.py\n")
        self.assertEqual([(f.status, f.path) for f in staged], [("M", "a.py"), ("R", "new.py")])
        self.assertEqual([f.path for f in unstaged], ["b.py"])
        self.assertEqual([f.path for f in untracked], ["c.py"])


if __name__ == "__main__":
    unittest.main()
