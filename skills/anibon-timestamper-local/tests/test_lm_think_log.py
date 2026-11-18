"""Unit tests for LM thinking/reasoning trace logger and anomaly detection."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from common.lm_think_log import (  # noqa: E402
    analyze_lm_response,
    configure_lm_think_logging,
    record_lm_response,
    summarize_lm_trace,
)
from common.lmstudio import extract_chat_response  # noqa: E402
from process.multimodal import _post_multimodal  # noqa: E402


class TestLmThinkLog(unittest.TestCase):
    """Verify inline/structured think extraction, error flags, JSONL writing, and summary."""

    def tearDown(self) -> None:
        configure_lm_think_logging(None, verbose=False)

    def test_extracts_reasoning_content_and_gemma_channel_tags(self) -> None:
        payload = {
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "content": "<|channel>thought\nCheck webcam grid<channel|>00:05:00 - [Talk] เปิดสตรีม",
                    "reasoning_content": "Step 1: confirm topic",
                },
            }],
            "usage": {"prompt_tokens": 120, "completion_tokens": 25, "completion_tokens_details": {"reasoning_tokens": 9}},
        }
        res = analyze_lm_response(payload)
        self.assertEqual(res.clean_content, "00:05:00 - [Talk] เปิดสตรีม")
        self.assertIn("Step 1: confirm topic", res.think_text)
        self.assertIn("Check webcam grid", res.think_text)
        self.assertEqual(res.reasoning_tokens, 9)
        self.assertEqual(res.errors, ())
        self.assertEqual(extract_chat_response(payload), "00:05:00 - [Talk] เปิดสตรีม")

    def test_detects_empty_unclosed_truncated_overflow_and_repetition_errors(self) -> None:
        loop = "Check frame panel alignment again. " * 6
        bad_payload = {
            "choices": [{
                "finish_reason": "length",
                "message": {"content": "<think>still thinking forever", "reasoning_content": loop * 4},
            }],
            "usage": {"prompt_tokens": 300, "completion_tokens": 500, "completion_tokens_details": {"reasoning_tokens": 500}},
        }
        res = analyze_lm_response(bad_payload)
        self.assertIn("UNCLOSED_THINK_TAG", res.errors)
        self.assertIn("TRUNCATED_LENGTH", res.errors)
        self.assertIn("THINK_OVERFLOW", res.errors)
        self.assertIn("REPETITION_LOOP", res.errors)

        empty_payload = {
            "choices": [{"finish_reason": "stop", "message": {"content": "", "reasoning_content": "only thought"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 12},
        }
        self.assertIn("EMPTY_CONTENT", analyze_lm_response(empty_payload).errors)

    def test_writes_jsonl_trace_summarizes_and_hooks_multimodal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "lm_think_trace.jsonl"
            configure_lm_think_logging(trace, verbose=True)
            ok_resp = {
                "choices": [{"finish_reason": "stop", "message": {"content": "CONTINUATION", "reasoning_content": ""}}],
                "usage": {"prompt_tokens": 200, "completion_tokens": 10},
            }
            record_lm_response(ok_resp, "text", "google/gemma-4-12b-qat", 2.0)

            mm_resp = json.dumps({
                "choices": [{"finish_reason": "stop", "message": {"content": "<think>Inspect cam</think>OK", "reasoning_content": ""}}],
                "usage": {"prompt_tokens": 400, "completion_tokens": 20, "completion_tokens_details": {"reasoning_tokens": 8}},
            }).encode("utf-8")
            with patch("urllib.request.urlopen", return_value=BytesIO(mm_resp)):
                out = _post_multimodal("http://local/v1/chat/completions", {"model": "gemma4"}, {}, 10)
            self.assertEqual(out, "OK")
            summary = summarize_lm_trace(trace)
            self.assertEqual(summary["calls"], 2)
            self.assertEqual(summary["completion_tokens"], 30)
            self.assertEqual(summary["reasoning_tokens"], 8)
            self.assertEqual(summary["errors"], {})


if __name__ == "__main__":
    unittest.main()
