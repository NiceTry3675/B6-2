import io
import json
import unittest
import urllib.error
from unittest import mock

from gitgen.ai_client import AIError, GeminiClient, GenerationParams, describe_http_error, parse_response


def make_client(model="gemini-3.8-flash"):
    return GeminiClient("test-key", GenerationParams(model=model, temperature=0.2, max_tokens=256))


class RequestBodyTest(unittest.TestCase):
    def test_params_mapped(self):
        body = make_client().build_request_body("sys", "user")
        cfg = body["generationConfig"]
        self.assertEqual(cfg["temperature"], 0.2)
        self.assertEqual(cfg["maxOutputTokens"], 256)
        self.assertEqual(cfg["thinkingConfig"], {"thinkingBudget": 0})
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "sys")

    def test_no_thinking_config_for_other_models(self):
        body = make_client("gemini-2.5-pro").build_request_body("s", "u")
        self.assertNotIn("thinkingConfig", body["generationConfig"])


class ParseResponseTest(unittest.TestCase):
    def test_ok(self):
        result = parse_response({
            "candidates": [{"content": {"parts": [{"text": "think", "thought": True}, {"text": "feat: x"}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        })
        self.assertEqual(result.text, "feat: x")
        self.assertEqual(result.output_tokens, 5)
        self.assertFalse(result.truncated)

    def test_truncated_flag(self):
        result = parse_response({"candidates": [{"content": {"parts": [{"text": "fe"}]}, "finishReason": "MAX_TOKENS"}]})
        self.assertTrue(result.truncated)

    def test_empty_due_to_max_tokens(self):
        with self.assertRaisesRegex(AIError, "max-tokens"):
            parse_response({"candidates": [{"content": {}, "finishReason": "MAX_TOKENS"}]})

    def test_blocked(self):
        with self.assertRaisesRegex(AIError, "차단"):
            parse_response({"promptFeedback": {"blockReason": "SAFETY"}})


class HttpErrorTest(unittest.TestCase):
    def test_invalid_key(self):
        body = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.",
                          "details": [{"reason": "API_KEY_INVALID"}]}}
        self.assertIn("인증 실패", describe_http_error(400, body, "m"))

    def test_other_codes(self):
        self.assertIn("모델을 찾을 수 없습니다", describe_http_error(404, {}, "nope"))
        self.assertIn("요청 한도", describe_http_error(429, {}, "m"))
        self.assertIn("서버 오류", describe_http_error(503, {}, "m"))

    def test_generate_wraps_network_error(self):
        client = make_client()
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("no route")):
            with self.assertRaisesRegex(AIError, "네트워크 오류"):
                client.generate("s", "u")
        self.assertEqual(client.call_count, 1)

    def test_generate_wraps_http_error(self):
        payload = json.dumps({"error": {"message": "quota"}}).encode()
        err = urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(payload))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaisesRegex(AIError, "HTTP 429: quota"):
                make_client().generate("s", "u")


if __name__ == "__main__":
    unittest.main()
