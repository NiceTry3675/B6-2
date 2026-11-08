import unittest

from gitgen.safe_mode import SafeModeConfig, apply_safe_mode, is_sensitive_file


def file_diff(path: str, added: list[str]) -> str:
    body = "".join(f"+{line}\n" for line in added)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n+++ b/{path}\n"
        f"@@ -0,0 +1,{len(added)} @@\n{body}"
    )


class MaskingTest(unittest.TestCase):
    def run_safe(self, diff, **kw):
        return apply_safe_mode(diff, SafeModeConfig(**kw))

    def test_masks_api_keys_and_pii(self):
        google_key = "AIza" + "A" * 35
        diff = file_diff("app.py", [
            f'KEY = "{google_key}"',
            'contact = "dev@example.com"',
            'phone = "010-1234-5678"',
            'aws = "AKIAABCDEFGHIJKLMNOP"',
        ])
        out, report = self.run_safe(diff)
        self.assertNotIn(google_key, out)
        self.assertNotIn("dev@example.com", out)
        self.assertNotIn("010-1234-5678", out)
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", out)
        self.assertEqual(report.masked["google_api_key"], 1)
        self.assertEqual(report.masked["email"], 1)

    def test_secret_assignment_keeps_key_name(self):
        diff = file_diff("config.py", ['password = "hunter2hunter2"', "API_TOKEN=abcdef123456"])
        out, _ = self.run_safe(diff)
        self.assertIn('password = "[MASKED:secret_literal]"', out)
        self.assertIn("API_TOKEN=[MASKED:env_secret]", out)

    def test_does_not_mask_ordinary_code(self):
        line = '"maxOutputTokens": self.params.max_tokens,'
        out, report = self.run_safe(file_diff("client.py", [line, "max_tokens = args.max_tokens"]))
        self.assertIn(line, out)
        self.assertEqual(sum(report.masked.values()), 0)

    def test_no_double_masking(self):
        key = "AIza" + "B" * 35
        out, report = self.run_safe(file_diff(".env.example", [f"GEMINI_API_KEY={key}"]))
        self.assertIn("GEMINI_API_KEY=[MASKED:google_api_key]", out)
        self.assertEqual(sum(report.masked.values()), 1)

    def test_custom_pattern(self):
        out, report = self.run_safe(file_diff("a.py", ["emp_id = EMP-00123"]), extra_patterns=[r"EMP-\d+"])
        self.assertIn("[MASKED:custom_1]", out)
        self.assertEqual(report.masked["custom_1"], 1)

    def test_invalid_custom_pattern(self):
        with self.assertRaises(ValueError):
            self.run_safe(file_diff("a.py", ["x"]), extra_patterns=["("])


class SensitiveFileTest(unittest.TestCase):
    def test_detection(self):
        self.assertTrue(is_sensitive_file(".env"))
        self.assertTrue(is_sensitive_file("config/.env.production"))
        self.assertTrue(is_sensitive_file("certs/server.pem"))
        self.assertFalse(is_sensitive_file(".env.example"))
        self.assertFalse(is_sensitive_file("app/environment.py"))

    def test_sensitive_file_content_not_sent(self):
        diff = file_diff(".env", ["SECRET=supersecretvalue"]) + file_diff("a.py", ["print(1)"])
        out, report = apply_safe_mode(diff, SafeModeConfig())
        self.assertNotIn("supersecretvalue", out)
        self.assertEqual(report.excluded_files, [".env"])
        self.assertIn("print(1)", out)


class LimitTest(unittest.TestCase):
    def test_max_files(self):
        diff = "".join(file_diff(f"f{i}.py", ["x"]) for i in range(5))
        out, report = apply_safe_mode(diff, SafeModeConfig(max_files=2))
        self.assertEqual(report.sent_files, 2)
        self.assertEqual(report.total_files, 5)
        self.assertIn("3개 파일 생략", out)
        self.assertNotIn("f2.py", out)

    def test_max_lines(self):
        diff = file_diff("big.py", [f"line{i}" for i in range(100)])
        out, report = apply_safe_mode(diff, SafeModeConfig(max_lines=20))
        self.assertIn("줄 수 제한", out)
        self.assertNotIn("line50", out)
        self.assertEqual(report.sent_lines, 20)


if __name__ == "__main__":
    unittest.main()
