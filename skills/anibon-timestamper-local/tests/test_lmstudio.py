import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from common.lmstudio import (
    SYSTEM_PROMPT,
    resolve_endpoint,
    resolve_model,
    encode_image_base64,
    build_chat_payload,
    build_vision_payload,
)


class TestLMStudio(unittest.TestCase):

    @patch("common.lmstudio.is_host_reachable")
    def test_resolve_endpoint_primary_reachable(self, mock_reachable):
        mock_reachable.return_value = True
        ep = resolve_endpoint("http://100.115.25.30:1234/v1/chat/completions")
        self.assertEqual(ep, "http://100.115.25.30:1234/v1/chat/completions")
        mock_reachable.assert_called_once_with("100.115.25.30", 1234, timeout=1.0)

    @patch("common.lmstudio.is_host_reachable")
    def test_resolve_endpoint_fallback_when_unreachable(self, mock_reachable):
        mock_reachable.return_value = False
        ep = resolve_endpoint("http://100.115.25.30:1234/v1/chat/completions")
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")

    @patch("common.lmstudio.is_host_reachable")
    def test_resolve_endpoint_default_none(self, mock_reachable):
        mock_reachable.return_value = False
        ep = resolve_endpoint(None)
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")

        mock_reachable.return_value = True
        ep2 = resolve_endpoint("")
        self.assertEqual(ep2, "http://100.115.25.30:1234/v1/chat/completions")

    @patch("common.lmstudio.is_host_reachable")
    def test_resolve_endpoint_localhost_skips_check(self, mock_reachable):
        ep = resolve_endpoint("http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")
        mock_reachable.assert_not_called()

    @patch("common.lmstudio.is_host_reachable")
    def test_resolve_endpoint_normalizes_missing_scheme_and_path(self, mock_reachable):
        mock_reachable.return_value = True
        ep = resolve_endpoint("100.115.25.30")
        self.assertEqual(ep, "http://100.115.25.30:1234/v1/chat/completions")

    @patch("common.lmstudio.get_loaded_models")
    def test_resolve_model_auto(self, mock_get_loaded):
        mock_get_loaded.return_value = ["unsloth/gemma-4-26b-a4b-it@q2_k_x", "other-model"]
        chosen = resolve_model("auto", "http://127.0.0.1:1234")
        self.assertEqual(chosen, "unsloth/gemma-4-26b-a4b-it@q2_k_x")

    @patch("common.lmstudio.get_loaded_models")
    def test_resolve_model_fallback(self, mock_get_loaded):
        mock_get_loaded.return_value = ["qwen/qwen3.5-9b"]
        chosen = resolve_model("unsloth/gemma-4-26b-a4b-it@q2_k_x", "http://127.0.0.1:1234", force=False)
        self.assertEqual(chosen, "qwen/qwen3.5-9b")

    @patch("common.lmstudio.get_loaded_models")
    def test_resolve_model_shorthand_alias(self, mock_get_loaded):
        mock_get_loaded.return_value = ["gemma-4-26b-a4b-it@q2_k_xl", "qwen/qwen3.5-9b"]
        chosen = resolve_model("gemma4 26b q2", "http://127.0.0.1:1234")
        self.assertEqual(chosen, "gemma-4-26b-a4b-it@q2_k_xl")

        mock_get_loaded.return_value = []
        chosen_offline = resolve_model("gemma4 26b q2", "http://127.0.0.1:1234")
        self.assertEqual(chosen_offline, "unsloth/gemma-4-26b-a4b-it@q2_k_x")

    def test_build_chat_payload(self):
        payload = build_chat_payload("test-model", "Test prompt", 256, 0.2)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["content"], "Test prompt")
        self.assertNotIn("reasoning_effort", payload)

    def test_build_chat_payload_disable_reasoning(self):
        payload = build_chat_payload("test-model", "Test prompt", 256, 0.2, disable_reasoning=True)
        self.assertEqual(payload["reasoning_effort"], "none")

    def test_prepare_request_sets_reasoning_effort_for_local_only(self):
        import json
        from common.lmstudio import _prepare_request

        local_req = _prepare_request(
            "http://100.115.25.30:1234/v1/chat/completions", "test-model", "Hi", 64, 0.1, "sys"
        )
        remote_req = _prepare_request(
            "https://tokenme.example/v1/chat/completions", "test-model", "Hi", 64, 0.1, "sys"
        )
        self.assertEqual(json.loads(local_req.data.decode("utf-8")).get("reasoning_effort"), "none")
        self.assertNotIn("reasoning_effort", json.loads(remote_req.data.decode("utf-8")))

    @patch("common.lmstudio._try_fallback_native_chat", return_value=None)
    @patch("common.lmstudio._execute_http_call")
    def test_call_local_retries_without_reasoning_on_http_400(self, mock_exec, _mock_native):
        import urllib.error
        from common.lmstudio import call_local

        err_400 = urllib.error.HTTPError("http://127.0.0.1:1234/v1/chat/completions", 400, "Bad Request", {}, None)
        mock_exec.side_effect = [err_400, "Recovered"]
        res = call_local("http://127.0.0.1:1234/v1/chat/completions", "test-model", "Hi", 64, 0.1, retries=0)
        self.assertEqual(res, "Recovered")
        self.assertEqual(mock_exec.call_count, 2)

    def test_build_vision_payload(self):
        payload = build_vision_payload(
            "test-vision-model",
            "Identify this game",
            "data:image/jpeg;base64,dGVzdA==",
            max_tokens=300,
        )
        self.assertEqual(payload["model"], "test-vision-model")
        user_msg = payload["messages"][1]
        self.assertIsInstance(user_msg["content"], list)
        self.assertEqual(user_msg["content"][0]["type"], "text")
        self.assertEqual(user_msg["content"][1]["type"], "image_url")
        self.assertEqual(
            user_msg["content"][1]["image_url"]["url"],
            "data:image/jpeg;base64,dGVzdA==",
        )


if __name__ == "__main__":
    unittest.main()
