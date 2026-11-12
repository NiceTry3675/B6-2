import unittest

from gitgen.formatter import (
    COMMIT_TITLE_MAX,
    PLACEHOLDER_BULLET,
    PR_TITLE_MAX,
    count_file_mentions,
    drop_truncated_tail,
    finalize_commit,
    finalize_pr,
    parse_commit,
    parse_pr,
    title_may_be_cut,
    truncate_title,
)


class CommitFormatTest(unittest.TestCase):
    def test_parses_title_and_bullets(self):
        msg, problems = parse_commit("feat: 로그인 추가\n\n- auth.py 추가\n* 세션 처리\n")
        self.assertEqual(problems, [])
        self.assertEqual(msg.title, "feat: 로그인 추가")
        self.assertEqual(msg.body, ["auth.py 추가", "세션 처리"])
        self.assertEqual(msg.render(), "feat: 로그인 추가\n\n- auth.py 추가\n- 세션 처리")

    def test_strips_code_fence_and_label(self):
        msg, _ = parse_commit("```\n제목: fix: 버그 수정.\n```")
        final, _ = finalize_commit(msg)
        self.assertEqual(final.title, "fix: 버그 수정")

    def test_empty_output_is_problem(self):
        _, problems = parse_commit("   \n")
        self.assertTrue(problems)

    def test_long_title_is_truncated_to_max(self):
        msg, _ = parse_commit("feat: " + "아주 긴 제목 " * 20)
        final, notes = finalize_commit(msg)
        self.assertLessEqual(len(final.title), COMMIT_TITLE_MAX)
        self.assertTrue(any("잘랐습니다" in n for n in notes))

    def test_body_trimmed_to_two_bullets(self):
        msg, _ = parse_commit("feat: x\n\n- 첫째\n- 둘째\n- 셋째\n- 넷째")
        final, notes = finalize_commit(msg)
        self.assertEqual(final.body, ["첫째", "둘째"])
        self.assertTrue(any("셋째 / 넷째" in n for n in notes))

    def test_two_bullets_untouched(self):
        msg, _ = parse_commit("feat: x\n\n- 첫째\n- 둘째")
        final, notes = finalize_commit(msg)
        self.assertEqual(final.body, ["첫째", "둘째"])
        self.assertEqual(notes, [])

    def test_count_file_mentions(self):
        paths = ["gitgen/cli.py", "gitgen/formatter.py", "README.md", "tests/test_cli.py"]
        body = ["cli.py 로그 개선 (gitgen/formatter.py)", "README.md 갱신"]
        self.assertEqual(count_file_mentions(body, paths), 3)
        self.assertEqual(count_file_mentions(["test_cli.py"], ["cli.py"]), 0)

    def test_count_file_mentions_with_korean_particle(self):
        paths = ["gitgen/cli.py"]
        self.assertEqual(count_file_mentions(["gitgen/cli.py의 기본값 변경"], paths), 1)
        self.assertEqual(count_file_mentions(["cli.py에 로그 추가"], paths), 1)
        self.assertEqual(count_file_mentions(["cli.pyc 정리"], paths), 0)

    def test_warns_when_over_recommended(self):
        msg, _ = parse_commit("feat: " + "가" * 50)
        _, notes = finalize_commit(msg)
        self.assertTrue(any("권장" in n for n in notes))


class PRFormatTest(unittest.TestCase):
    GOOD = """TITLE: feat: PR 생성기 추가

## Why
- 배경

## What
- main.py 추가
- cli 구현

## How to Test
- python main.py pr
"""

    def test_parses_good_output(self):
        draft, problems = parse_pr(self.GOOD)
        self.assertEqual(problems, [])
        self.assertEqual(draft.title, "feat: PR 생성기 추가")
        self.assertEqual(draft.sections["What"], ["main.py 추가", "cli 구현"])

    def test_header_variants(self):
        text = "TITLE: x\n### Why (변경 배경)\n- a\n**What**\n- b\n## how to test\n1. c\n"
        draft, problems = parse_pr(text)
        self.assertEqual(problems, [])
        self.assertEqual(draft.sections["How to Test"], ["c"])

    def test_missing_section_reported_and_filled(self):
        draft, problems = parse_pr("TITLE: x\n## Why\n- a\n## What\n")
        self.assertIn("'## What' 섹션에 불릿이 없습니다.", problems)
        self.assertIn("'## How to Test' 섹션이 없습니다.", problems)
        final, notes = finalize_pr(draft)
        self.assertEqual(final.sections["How to Test"], [PLACEHOLDER_BULLET])
        self.assertEqual(len(notes), 2)
        body = final.render_body()
        self.assertIn("## Why\n- a", body)
        self.assertIn("## How to Test\n- ", body)

    def test_pr_title_truncated(self):
        draft, _ = parse_pr("TITLE: " + "word " * 40 + "\n" + self.GOOD.split("\n", 1)[1])
        final, _ = finalize_pr(draft)
        self.assertLessEqual(len(final.title), PR_TITLE_MAX)


class TruncatedTailTest(unittest.TestCase):
    def test_commit_drops_last_bullet(self):
        msg, _ = parse_commit("feat: x\n\n- 완성된 불릿\n- 잘린 불")
        self.assertIsNotNone(drop_truncated_tail(msg))
        self.assertEqual(msg.body, ["완성된 불릿"])

    def test_pr_drops_last_bullet_of_last_section(self):
        draft, _ = parse_pr("TITLE: x\n## Why\n- a\n## What\n- b\n- 잘")
        drop_truncated_tail(draft)
        self.assertEqual(draft.sections["What"], ["b"])
        self.assertEqual(draft.sections["Why"], ["a"])


    def test_pr_keeps_complete_bullet_when_cut_after_next_header(self):
        draft, _ = parse_pr("TITLE: x\n## Why\n- 완성된 이유\n\n## What\n")
        self.assertIsNone(drop_truncated_tail(draft))
        self.assertEqual(draft.sections["Why"], ["완성된 이유"])


class TitleMayBeCutTest(unittest.TestCase):
    def test_commit_title_only(self):
        msg, _ = parse_commit("feat: 로그 문서 추가 및 타")
        self.assertTrue(title_may_be_cut(msg))

    def test_commit_with_bullet_started(self):
        msg, _ = parse_commit("feat: x\n\n- 잘린 불")
        self.assertFalse(title_may_be_cut(msg))

    def test_pr_without_sections(self):
        draft, _ = parse_pr("TITLE: feat: 커밋 본문 불")
        self.assertTrue(title_may_be_cut(draft))

    def test_pr_with_section_started(self):
        draft, _ = parse_pr("TITLE: feat: x\n\n## Why\n- 잘")
        self.assertFalse(title_may_be_cut(draft))


class TruncateTest(unittest.TestCase):
    def test_short_title_unchanged(self):
        self.assertEqual(truncate_title("abc", 10), "abc")

    def test_cuts_on_word_boundary(self):
        self.assertEqual(truncate_title("hello wonderful world", 15), "hello wonderful")


if __name__ == "__main__":
    unittest.main()
