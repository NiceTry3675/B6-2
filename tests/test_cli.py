import contextlib
import io
import os
import unittest
from unittest import mock

from gitgen import cli
from gitgen.ai_client import GenerationResult

from tests.test_git_collector import GitRepoTestCase


def result(text):
    return GenerationResult(text=text, finish_reason="STOP")


def truncated(text):
    return GenerationResult(text=text, finish_reason="MAX_TOKENS")


class CliTest(GitRepoTestCase):
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        os.chdir(self.repo)
        self._env = mock.patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}, clear=False)
        self._env.start()
        os.environ.pop("AI_API_KEY", None)
        # 도구 폴더의 실제 .env 를 읽지 않도록 막는다.
        self._dotenv = mock.patch.object(cli, "load_dotenv")
        self._dotenv.start()

    def tearDown(self):
        self._dotenv.stop()
        self._env.stop()
        os.chdir(self._cwd)
        super().tearDown()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.run(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_missing_api_key(self):
        os.environ.pop("GEMINI_API_KEY")
        code, _, err = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertIn("GEMINI_API_KEY 환경변수가 설정되지 않았습니다", err)

    def test_no_changes(self):
        with mock.patch.object(cli.GeminiClient, "generate") as gen:
            code, _, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("변경 사항이 없습니다", err)
        gen.assert_not_called()

    def test_commit_single_call(self):
        (self.repo / "a.py").write_text("print('changed')\n")
        with mock.patch.object(cli.GeminiClient, "generate", return_value=result("feat: a.py 수정\n\n- a.py 출력 변경")) as gen:
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertEqual(gen.call_count, 1)
        self.assertIn("--- Commit Message ---\nfeat: a.py 수정\n\n- a.py 출력 변경", out)
        self.assertIn("M  a.py", err)  # 변경 파일 목록이 로그에 나온다
        self.assertIn("언급 파일 1개", err)

    def test_pr_retries_once_then_fills(self):
        (self.repo / "a.py").write_text("print('changed')\n")
        bad = result("TITLE: feat: x\n## Why\n- 이유\n")

        def fake_generate(self_client, system, user):
            self_client.call_count += 1
            return bad

        with mock.patch.object(cli.GeminiClient, "generate", autospec=True, side_effect=fake_generate) as gen:
            code, out, err = self.run_cli("pr")
        self.assertEqual(code, 0)
        self.assertEqual(gen.call_count, 2)  # 최초 1회 + 재생성 1회, 그 이상은 없음
        self.assertIn("1회 재생성", err)
        self.assertIn("AI API 호출 횟수: 2회", err)
        for header in ("## Why", "## What", "## How to Test"):
            self.assertIn(header, out)

    def test_truncated_title_is_error(self):
        (self.repo / "a.py").write_text("print('changed')\n")
        with mock.patch.object(cli.GeminiClient, "generate", return_value=truncated("feat: a.py 수정 및 타")):
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")  # 끊긴 제목을 결과로 내보내지 않는다
        self.assertIn("제목이 완성되지 않았을 수 있어", err)

    def test_truncated_bullet_keeps_complete_title(self):
        (self.repo / "a.py").write_text("print('changed')\n")
        cut = truncated("feat: a.py 수정\n\n- a.py 출력 변")
        with mock.patch.object(cli.GeminiClient, "generate", return_value=cut):
            code, out, err = self.run_cli("commit")
        self.assertEqual(code, 0)
        self.assertIn("feat: a.py 수정", out)
        self.assertNotIn("출력 변", out)
        self.assertIn("미완성 불릿", err)

    def test_dry_run_with_safe_mode_does_not_call_api(self):
        (self.repo / ".env").write_text("SECRET=abcdefghijk\n")
        (self.repo / "a.py").write_text('email = "me@example.com"\n')
        with mock.patch.object(cli.GeminiClient, "generate") as gen:
            code, out, err = self.run_cli("commit", "--dry-run", "--safe-mode")
        self.assertEqual(code, 0)
        gen.assert_not_called()
        self.assertNotIn("abcdefghijk", out)
        self.assertNotIn("me@example.com", out)
        self.assertIn("[SAFE]", err)


if __name__ == "__main__":
    unittest.main()
