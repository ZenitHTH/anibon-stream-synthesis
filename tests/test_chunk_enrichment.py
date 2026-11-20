from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(_ROOT / "lib"))
if str(_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_ROOT / "scripts"))

import prepare_video
from process.chunk_enrichment import ChunkEnrichConfig, enrich_single_chunk, enrich_workspace_chunks
from process.music.chunk_scanner import SongRecoveryResult
from video.audio_webcam_cues import AudioWebcamCue


class TestChunkEnrichment(unittest.TestCase):
    def test_prepare_video_keep_silent_chunks_emits_empty_window(self) -> None:
        transcript = [
            {"start": 5.0, "duration": 2.0, "timestamp": "00:00:05", "text": "เปิดไลฟ์"},
            {"start": 320.0, "duration": 2.0, "timestamp": "00:05:20", "text": "กลับมาพูดต่อ"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            with patch("prepare_video.load_transcript", return_value=transcript), \
                 patch("prepare_video.load_default_mappings", return_value={"mappings": []}), \
                 patch("prepare_video.load_replacements", return_value=[]):
                n = prepare_video.chunk_transcript_with_silent_windows(
                    ws, prepare_video.ChunkBuildOptions(block=150, overlap=15, fmt="txt")
                )
            self.assertEqual(n, 3)
            self.assertTrue((ws / "chunks" / "chunk_01.txt").is_file())

    def test_enrich_single_chunk_writes_sidecars_and_preserves_existing_activity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "activity").mkdir()
            chunk_path = ws / "chunks" / "chunk_00.txt"
            chunk_path.write_text("CHUNK 00 | 00:00:00–00:02:30 | cutoff=00:02:15\n(00:00:10) เริ่ม", encoding="utf-8")
            (ws / "activity" / "activity_chunk_00.txt").write_text("- 00:00:00 - 00:02:30: Elden Ring [Gameplay]", encoding="utf-8")

            cues = (AudioWebcamCue(45, "silence_drop", 3.0, "silence_drop"),)
            wc_fake = [("00:00:45", ws / "frames" / "webcam_chunk" / "wc_000045.jpg", "b64", "WEBCAM CLOSEUP")]
            song = SongRecoveryResult("Idol", "YOASOBI", ({"start": 60.0, "timestamp": "00:01:00", "text": "พูดแทรก"},), None)
            cfg = ChunkEnrichConfig(workspace=ws, audio_source=Path("a.m4a"), video_source=Path("v.mp4"))

            with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=cues), \
                 patch("process.chunk_enrichment.sample_chunk_webcam_frames", return_value=wc_fake), \
                 patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=True), \
                 patch("process.chunk_enrichment.scan_and_recover_chunk_song", return_value=song):
                data = enrich_single_chunk(chunk_path, cfg)

            self.assertEqual(data["song"]["title"], "Idol")
            act_text = (ws / "activity" / "activity_chunk_00.txt").read_text(encoding="utf-8")
            self.assertIn("Elden Ring [Gameplay]", act_text)
            self.assertIn("[SILENCE_SHOCK] 00:00:45", act_text)
            self.assertIn("[SHAZAM_SONG] Idol - YOASOBI", act_text)
            self.assertTrue((ws / "enrichment" / "chunk_00.json").is_file())
            self.assertIn("(00:00:10) เริ่ม", chunk_path.read_text(encoding="utf-8"))
            self.assertNotIn("YOASOBI", chunk_path.read_text(encoding="utf-8"))

            with patch("process.chunk_enrichment.select_audio_webcam_cues", side_effect=AssertionError("should use cache")):
                count = enrich_workspace_chunks(cfg)
            self.assertEqual(count, 1)

    def test_skips_cache_without_media_handles_corrupt_json_and_force_strips_stale_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / "chunks").mkdir()
            (ws / "activity").mkdir()
            chunk_path = ws / "chunks" / "chunk_00.txt"
            chunk_path.write_text("CHUNK 00 | 00:00:00–00:02:30 | cutoff=00:02:15\n(00:00:10) เริ่ม", encoding="utf-8")

            # 1. No media -> does not poison cache
            no_media_cfg = ChunkEnrichConfig(workspace=ws, audio_source=None, video_source=None)
            enrich_single_chunk(chunk_path, no_media_cfg)
            self.assertFalse((ws / "enrichment" / "chunk_00.json").exists())

            # 2. Corrupt cache + stale activity marker + stale scratch whisper json -> force cleans all
            (ws / "enrichment").mkdir(parents=True, exist_ok=True)
            (ws / "enrichment" / "chunk_00.json").write_text("{corrupt", encoding="utf-8")
            scratch = ws / "enrichment" / "scratch" / "chunk_00"
            scratch.mkdir(parents=True)
            stale_whisper = scratch / "vocals_16k.json"
            stale_whisper.write_text("{}", encoding="utf-8")
            (ws / "activity" / "activity_chunk_00.txt").write_text(
                "- 00:00:00 - 00:02:30: Game [Gameplay]\n--- PRE-CHUNK AUDIO/SONG ---\n- [AUDIO_PEAK] 00:00:20",
                encoding="utf-8",
            )

            # Without force: corrupt JSON falls back to fresh computation or {} without crashing
            force_cfg = ChunkEnrichConfig(workspace=ws, audio_source=Path("a.m4a"), force=True)
            with patch("process.chunk_enrichment.select_audio_webcam_cues", return_value=()), \
                 patch("process.chunk_enrichment.should_scan_chunk_for_song", return_value=False):
                enrich_single_chunk(chunk_path, force_cfg)

            self.assertFalse(stale_whisper.exists())
            act_text = (ws / "activity" / "activity_chunk_00.txt").read_text(encoding="utf-8")
            self.assertIn("Game [Gameplay]", act_text)
            self.assertNotIn("PRE-CHUNK AUDIO/SONG", act_text)
            self.assertNotIn("[AUDIO_PEAK]", act_text)


if __name__ == "__main__":
    unittest.main()
