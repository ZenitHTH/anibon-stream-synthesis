import json
import os
import tempfile
import unittest
from pathlib import Path
from anibon.config import (
    load_config,
    cfg_int,
    cfg_float,
    cfg_str,
    SKILL_CONFIG_PATH,
    CHUNK_MAX_TOKENS,
    SUMMARIZER_MAX_TOKENS,
    PRUNE_MAX_TOKENS,
    BYTE_CAP_LIMIT,
)


class TestConfig(unittest.TestCase):
    def tearDown(self):
        if SKILL_CONFIG_PATH.is_file():
            load_config(SKILL_CONFIG_PATH, override=True)

    def test_skill_config_json_exists_and_loads_defaults(self):
        self.assertTrue(SKILL_CONFIG_PATH.is_file())
        self.assertEqual(CHUNK_MAX_TOKENS, 4096)
        self.assertEqual(SUMMARIZER_MAX_TOKENS, 4096)
        self.assertEqual(PRUNE_MAX_TOKENS, 4000)
        self.assertEqual(BYTE_CAP_LIMIT, 3500)

    def test_load_config_parses_json_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "config.json"
            cfg_file.write_text(
                json.dumps({
                    "primary_host": "192.168.1.50",
                    "chunk_max_tokens": 2048,
                    "temperature": 0.25,
                }),
                encoding="utf-8",
            )
            parsed = load_config(cfg_file, override=True)
            self.assertEqual(parsed["primary_host"], "192.168.1.50")
            self.assertEqual(cfg_str("primary_host", "100.115.25.30"), "192.168.1.50")
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 2048)
            self.assertAlmostEqual(cfg_float("temperature", 0.1), 0.25)

    def test_malformed_json_or_bad_types_fall_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_file = Path(tmp) / "bad.json"
            bad_file.write_text("{invalid json", encoding="utf-8")
            self.assertEqual(load_config(bad_file, override=True), {})

            type_file = Path(tmp) / "types.json"
            type_file.write_text(
                json.dumps({"chunk_max_tokens": "not_a_number", "temperature": ""}),
                encoding="utf-8",
            )
            load_config(type_file, override=True)
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 4096)
            self.assertAlmostEqual(cfg_float("temperature", 0.1), 0.1)

    def test_os_environ_overrides_config_json_when_not_forced(self):
        os.environ["ANIBON_CHUNK_MAX_TOKENS"] = "8192"
        try:
            if SKILL_CONFIG_PATH.is_file():
                load_config(SKILL_CONFIG_PATH, override=False)
            self.assertEqual(cfg_int("chunk_max_tokens", 4096), 8192)
        finally:
            os.environ.pop("ANIBON_CHUNK_MAX_TOKENS", None)

    def test_modules_use_config_defaults(self):
        import inspect
        from anibon import config, summarizer, lmstudio, prompts, multimodal, timestamps

        self.assertEqual(
            inspect.signature(summarizer.run_local_summarizer_pass).parameters["max_tokens"].default,
            config.SUMMARIZER_MAX_TOKENS,
        )
        self.assertEqual(
            inspect.signature(summarizer.prune_essential).parameters["min_input"].default,
            config.PRUNE_MIN_INPUT,
        )
        self.assertEqual(
            inspect.signature(summarizer.enforce_byte_cap).parameters["limit"].default,
            config.BYTE_CAP_LIMIT,
        )
        self.assertEqual(
            inspect.signature(lmstudio.call_local).parameters["timeout"].default,
            config.CHUNK_TIMEOUT_SEC,
        )
        self.assertEqual(
            inspect.signature(prompts.build_chunk_entity_context).parameters["max_tokens"].default,
            config.ENTITY_CONTEXT_MAX_TOKENS,
        )
        self.assertEqual(
            inspect.signature(multimodal.call_multimodal).parameters["timeout"].default,
            config.MULTIMODAL_TIMEOUT_SEC,
        )
        self.assertEqual(
            inspect.signature(timestamps.deduplicate_consecutive_timestamps).parameters["min_gap_sec"].default,
            config.DEDUP_MIN_GAP_SEC,
        )

    def test_process_chunks_has_config_flag(self):
        import subprocess
        res = subprocess.run(
            ["python3", "scripts/process_chunks_local.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(SKILL_CONFIG_PATH.parent),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--config", res.stdout)
        self.assertIn("--env-file", res.stdout)

    def test_cfg_bool_and_default_multimodal_chunks(self):
        from anibon.config import cfg_bool, DEFAULT_MULTIMODAL_CHUNKS
        self.assertTrue(DEFAULT_MULTIMODAL_CHUNKS)
        self.assertTrue(cfg_bool("multimodal_chunks", False))

        os.environ["ANIBON_MULTIMODAL_CHUNKS"] = "false"
        try:
            self.assertFalse(cfg_bool("multimodal_chunks", True))
        finally:
            os.environ.pop("ANIBON_MULTIMODAL_CHUNKS", None)

        os.environ["ANIBON_MULTIMODAL_CHUNKS"] = "invalid_bool"
        try:
            self.assertTrue(cfg_bool("multimodal_chunks", True))
            self.assertFalse(cfg_bool("multimodal_chunks", False))
        finally:
            os.environ.pop("ANIBON_MULTIMODAL_CHUNKS", None)

    def test_process_chunks_multimodal_default_and_opt_out_flag(self):
        import subprocess
        res = subprocess.run(
            ["python3", "scripts/process_chunks_local.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(SKILL_CONFIG_PATH.parent),
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("--no-multimodal", res.stdout)
        self.assertIn("--text-only", res.stdout)

    def test_process_chunks_config_file_overrides_multimodal_chunks(self):
        import subprocess, tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            ws = tmp_path / "ws"
            ws.mkdir()
            (ws / "chunks").mkdir()
            (ws / "chunks" / "chunk_00.txt").write_text("dummy", encoding="utf-8")
            custom_cfg = tmp_path / "custom.json"
            custom_cfg.write_text(json.dumps({"multimodal_chunks": False}), encoding="utf-8")

            res = subprocess.run(
                [
                    "python3", "scripts/process_chunks_local.py",
                    str(ws), "--config", str(custom_cfg), "--dry-run"
                ],
                capture_output=True,
                text=True,
                cwd=str(SKILL_CONFIG_PATH.parent),
            )
            self.assertEqual(res.returncode, 0)
            self.assertIn("multimodal  : disabled (text-only)", res.stdout)


if __name__ == "__main__":
    unittest.main()



