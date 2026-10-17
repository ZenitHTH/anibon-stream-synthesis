import os
import tempfile
import unittest
from pathlib import Path
from anibon.config import (
    load_dotenv,
    env_int,
    env_float,
    env_str,
    SKILL_DOTENV_PATH,
    CHUNK_MAX_TOKENS,
    SUMMARIZER_MAX_TOKENS,
    PRUNE_MAX_TOKENS,
    BYTE_CAP_LIMIT,
)


class TestConfig(unittest.TestCase):
    def test_skill_dotenv_file_exists_and_loads_defaults(self):
        self.assertTrue(SKILL_DOTENV_PATH.is_file())
        self.assertEqual(CHUNK_MAX_TOKENS, 4096)
        self.assertEqual(SUMMARIZER_MAX_TOKENS, 4096)
        self.assertEqual(PRUNE_MAX_TOKENS, 4000)
        self.assertEqual(BYTE_CAP_LIMIT, 3500)

    def test_dotenv_parses_quotes_comments_and_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "# Comment line\n"
                "export TEST_HOST=\"100.115.25.30\" # inline comment\n"
                "TEST_TOKENS=2048 # token limit\n"
                "TEST_TEMP='0.25'\n",
                encoding="utf-8",
            )
            parsed = load_dotenv(env_file, override=True)
            self.assertEqual(parsed["TEST_HOST"], "100.115.25.30")
            self.assertEqual(env_int("TEST_TOKENS", 100), 2048)
            self.assertAlmostEqual(env_float("TEST_TEMP", 0.1), 0.25)
            for k in ("TEST_HOST", "TEST_TOKENS", "TEST_TEMP"):
                os.environ.pop(k, None)

    def test_malformed_or_empty_env_falls_back_to_default(self):
        os.environ["TEST_BAD_INT"] = "not_a_number"
        os.environ["TEST_EMPTY_FLOAT"] = ""
        try:
            self.assertEqual(env_int("TEST_BAD_INT", 4096), 4096)
            self.assertAlmostEqual(env_float("TEST_EMPTY_FLOAT", 0.1), 0.1)
        finally:
            os.environ.pop("TEST_BAD_INT", None)
            os.environ.pop("TEST_EMPTY_FLOAT", None)

    def test_os_environ_takes_precedence_over_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("TEST_PREC=100\n", encoding="utf-8")
            os.environ["TEST_PREC"] = "999"
            try:
                load_dotenv(env_file, override=False)
                self.assertEqual(env_int("TEST_PREC", 0), 999)
            finally:
                os.environ.pop("TEST_PREC", None)

    def test_load_dotenv_override_updates_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text("TEST_OVER=555\n", encoding="utf-8")
            os.environ["TEST_OVER"] = "111"
            try:
                load_dotenv(env_file, override=True)
                self.assertEqual(env_int("TEST_OVER", 0), 555)
            finally:
                os.environ.pop("TEST_OVER", None)


if __name__ == "__main__":
    unittest.main()
