import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from anibon.lmstudio import (
    SYSTEM_PROMPT,
    resolve_endpoint,
    resolve_model,
    encode_image_base64,
    build_chat_payload,
    build_vision_payload,
)


class TestLMStudio(unittest.TestCase):

    @patch("anibon.lmstudio.is_host_reachable")
    def test_resolve_endpoint_primary_reachable(self, mock_reachable):
        mock_reachable.return_value = True
        ep = resolve_endpoint("http://100.115.25.30:1234/v1/chat/completions")
        self.assertEqual(ep, "http://100.115.25.30:1234/v1/chat/completions")
        mock_reachable.assert_called_once_with("100.115.25.30", 1234, timeout=1.0)

    @patch("anibon.lmstudio.is_host_reachable")
    def test_resolve_endpoint_fallback_when_unreachable(self, mock_reachable):
        mock_reachable.return_value = False
        ep = resolve_endpoint("http://100.115.25.30:1234/v1/chat/completions")
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")

    @patch("anibon.lmstudio.is_host_reachable")
    def test_resolve_endpoint_default_none(self, mock_reachable):
        mock_reachable.return_value = False
        ep = resolve_endpoint(None)
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")

        mock_reachable.return_value = True
        ep2 = resolve_endpoint("")
        self.assertEqual(ep2, "http://100.115.25.30:1234/v1/chat/completions")

    @patch("anibon.lmstudio.is_host_reachable")
    def test_resolve_endpoint_localhost_skips_check(self, mock_reachable):
        ep = resolve_endpoint("http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(ep, "http://127.0.0.1:1234/v1/chat/completions")
        mock_reachable.assert_not_called()

    @patch("anibon.lmstudio.is_host_reachable")
    def test_resolve_endpoint_normalizes_missing_scheme_and_path(self, mock_reachable):
        mock_reachable.return_value = True
        ep = resolve_endpoint("100.115.25.30")
        self.assertEqual(ep, "http://100.115.25.30:1234/v1/chat/completions")

    @patch("anibon.lmstudio.get_loaded_models")
    def test_resolve_model_auto(self, mock_get_loaded):
        mock_get_loaded.return_value = ["unsloth/gemma-4-26b-a4b-it@q2_k_x", "other-model"]
        chosen = resolve_model("auto", "http://127.0.0.1:1234")
        self.assertEqual(chosen, "unsloth/gemma-4-26b-a4b-it@q2_k_x")

    @patch("anibon.lmstudio.get_loaded_models")
    def test_resolve_model_fallback(self, mock_get_loaded):
        mock_get_loaded.return_value = ["qwen/qwen3.5-9b"]
        chosen = resolve_model("unsloth/gemma-4-26b-a4b-it@q2_k_x", "http://127.0.0.1:1234", force=False)
        self.assertEqual(chosen, "qwen/qwen3.5-9b")

    @patch("anibon.lmstudio.get_loaded_models")
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
