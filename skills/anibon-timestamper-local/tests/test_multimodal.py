"""tests/test_multimodal.py — Unit tests for anibon.multimodal module."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from process.multimodal import (
    sec_to_ts,
    build_multimodal_content,
    sample_chunk_keyframes,
    prepare_storyboard_slides,
    unpack_mhtml_storyboard,
)


class TestMultimodal(unittest.TestCase):
    def test_sec_to_ts(self):
        self.assertEqual(sec_to_ts(0), "00:00:00")
        self.assertEqual(sec_to_ts(65), "00:01:05")
        self.assertEqual(sec_to_ts(3988), "01:06:28")
        self.assertEqual(sec_to_ts(7200), "02:00:00")

    def test_build_multimodal_content(self):
        prompt = "Describe these images"
        keyframes = [
            ("00:01:00", Path("/tmp/f1.jpg"), "b64_data_1"),
            ("00:02:00", Path("/tmp/f2.jpg"), "b64_data_2"),
        ]
        content = build_multimodal_content(prompt, keyframes)
        # 1 initial prompt text + (1 timestamp label + 1 image_url) per keyframe = 5
        self.assertEqual(len(content), 5)
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[0]["text"], prompt)
        self.assertEqual(content[1]["type"], "text")
        self.assertIn("00:01:00", content[1]["text"])
        self.assertEqual(content[2]["type"], "image_url")
        self.assertEqual(content[2]["image_url"]["url"], "data:image/jpeg;base64,b64_data_1")
        self.assertEqual(content[3]["type"], "text")
        self.assertIn("00:02:00", content[3]["text"])
        self.assertEqual(content[4]["type"], "image_url")
        self.assertEqual(content[4]["image_url"]["url"], "data:image/jpeg;base64,b64_data_2")

    def test_select_target_seconds_incomplete_cues(self):
        from process.multimodal import select_target_seconds
        items = [
            {"start": 10, "text": "สวัสดีครับทุกคน วันนี้มาคุยกัน"},
            {"start": 60, "text": "เนี่ยดูดิ อันนี้ในจอคืออะไร"},
            {"start": 120, "text": "ส่วนอันนี้เป็นอีกเกมหนึ่ง"},
            {"start": 200, "text": "ขอบคุณทุกคนที่ติดตามครับ"},
        ]
        res = select_target_seconds(0, 270, num_frames=2, items=items)
        self.assertEqual(len(res), 2)
        # Should pick the cues at 60 and 120
        self.assertIn(60, res)
        self.assertIn(120, res)

    def test_select_target_seconds_full_context_interesting(self):
        from process.multimodal import select_target_seconds
        items = [
            {"start": 30, "text": "วันนี้เราจะมาวิเคราะห์ระบบเศรษฐกิจและการเมืองระยะยาว"},
            {"start": 110, "text": "ปัญหาคือว่ามันกระทบกับทุกคนมาก 555 ไม่น่าเชื่อเลย!"},
            {"start": 220, "text": "สรุปคือแนวทางนี้ต้องปรับแก้ใหม่ทั้งหมด"},
        ]
        res = select_target_seconds(0, 270, num_frames=2, items=items)
        self.assertEqual(len(res), 2)

    def test_select_target_seconds_dynamic_min_max(self):
        from process.multimodal import select_target_seconds
        # 1 cue -> ensures at least 3 frames
        items_few = [{"start": 50, "text": "ดูอันนี้ดิ"}]
        res_few = select_target_seconds(0, 270, min_frames=3, max_frames=5, items=items_few)
        self.assertGreaterEqual(len(res_few), 3)

        # 4 distinct cues -> returns 4 frames
        items_many = [
            {"start": 30, "text": "ดูอันนี้ดิ"},
            {"start": 70, "text": "ตัวนี้คือใคร"},
            {"start": 120, "text": "ในจอนี้มีอะไร"},
            {"start": 180, "text": "เปิดดูรูปนี้"},
        ]
        res_many = select_target_seconds(0, 270, min_frames=3, max_frames=5, items=items_many)
        self.assertEqual(len(res_many), 4)

    def test_sample_chunk_keyframes_empty_dir(self):
        empty_dir = Path("/tmp/non_existent_slides_dir_12345")
        res = sample_chunk_keyframes(0, 270, empty_dir, Path("/tmp"))
        self.assertEqual(res, [])

    def test_prepare_storyboard_slides_not_found(self):
        dummy_ws = Path("/tmp/empty_workspace_12345")
        self.assertIsNone(prepare_storyboard_slides(dummy_ws))

    def test_unpack_mhtml_dummy(self):
        dummy_mhtml = Path("/tmp/dummy_non_existent.mhtml")
        self.assertEqual(unpack_mhtml_storyboard(dummy_mhtml, Path("/tmp")), 0)

    def test_prepare_storyboard_slides_auto_downloads_when_video_url_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            (ws / ".video_url").write_text("https://www.youtube.com/watch?v=dQw4w9WgXcQ", encoding="utf-8")

            def fake_download(url, workspace):
                frames = Path(workspace) / "frames"
                frames.mkdir(parents=True, exist_ok=True)
                slides = frames / "slides_clean"
                slides.mkdir(parents=True, exist_ok=True)
                for i in range(1, 15):
                    (slides / f"slide_{i:04d}.jpg").write_bytes(b"jpeg")
                return frames / "storyboard.mhtml"

            with patch("process.multimodal.download_storyboard", side_effect=fake_download) as mock_dl:
                res = prepare_storyboard_slides(ws)
                mock_dl.assert_called_once_with("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)
                self.assertIsNotNone(res)
                self.assertEqual(res.name, "slides_clean")

    def test_download_storyboard_does_not_skip_download_and_guards_empty_dir(self):
        import tempfile
        from download.ytdlp import download_storyboard
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            # Create an empty frames/slides_clean dir
            empty_slides = ws / "frames" / "slides_clean"
            empty_slides.mkdir(parents=True, exist_ok=True)

            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                download_storyboard("https://www.youtube.com/watch?v=dQw4w9WgXcQ", ws)

                self.assertTrue(mock_run.called)
                cmd = mock_run.call_args[0][0]
                self.assertNotIn("--skip-download", cmd)



    def test_compute_frame_budget_scales_with_eval_batch(self):
        from process.multimodal import compute_frame_budget
        # 2500 text tokens in 8192 batch -> (8192 - 2500) // 260 = 21 -> capped at max_frames=16
        self.assertEqual(compute_frame_budget(2500, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 16)
        # 7500 text tokens in 8192 batch -> (8192 - 7500) // 260 = 2
        self.assertEqual(compute_frame_budget(7500, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 2)
        # Overflowing text tokens -> clamps to min_frames=1
        self.assertEqual(compute_frame_budget(9000, eval_batch_size=8192, tokens_per_image=260, min_frames=1, max_frames=16), 1)

    def test_compute_tile_visual_delta_identical_vs_distinct(self):
        import shutil, subprocess, tempfile
        from process.multimodal import compute_tile_visual_delta, Image
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "black.jpg"
            p2 = Path(tmp) / "black_copy.jpg"
            p3 = Path(tmp) / "white.jpg"
            if Image is not None:
                Image.new("RGB", (320, 180), (10, 10, 10)).save(p1)
                Image.new("RGB", (320, 180), (10, 10, 10)).save(p2)
                Image.new("RGB", (320, 180), (240, 240, 240)).save(p3)
            else:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180", "-frames:v", "1", str(p1)], check=True)
                shutil.copyfile(p1, p2)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=320x180", "-frames:v", "1", str(p3)], check=True)

            self.assertLess(compute_tile_visual_delta(p1, p2), 0.01)
            self.assertGreater(compute_tile_visual_delta(p1, p3), 0.80)

    def test_sample_chunk_keyframes_scene_dedup_drops_static_and_keeps_changes(self):
        import shutil, subprocess, tempfile
        from process.multimodal import sample_chunk_keyframes, Image
        with tempfile.TemporaryDirectory() as tmp:
            slides_dir = Path(tmp) / "slides"
            out_dir = Path(tmp) / "tiles"
            slides_dir.mkdir()
            slide_file = slides_dir / "slide_0001.jpg"
            if Image is not None:
                slide = Image.new("RGB", (960, 540), (20, 20, 20))
                red_tile = Image.new("RGB", (320, 180), (240, 20, 20))
                slide.paste(red_tile, (0, 360))
                slide.save(slide_file)
            else:
                cmd = [
                    "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "color=c=0x141414:s=960x540",
                    "-vf", "drawbox=x=0:y=360:w=320:h=180:color=red@1.0:t=fill",
                    "-frames:v", "1", str(slide_file)
                ]
                subprocess.run(cmd, check=True)

            # Static chunk (0..50s, all dark gray tiles) -> only 1 frame kept
            res_static = sample_chunk_keyframes(
                0, 50, slides_dir, out_dir, scene_dedup=True, delta_threshold=0.06, text_tokens=3000
            )
            self.assertEqual(len(res_static), 1)

            # Chunk spanning 0..80s (includes red tile at ~60s) -> keeps anchor + red scene change
            res_change = sample_chunk_keyframes(
                0, 80, slides_dir, out_dir, scene_dedup=True, delta_threshold=0.06, text_tokens=3000
            )
            self.assertGreaterEqual(len(res_change), 2)

    def test_compute_tile_visual_delta_unreadable_fallback(self):
        from process.multimodal import compute_tile_visual_delta
        # Missing file should gracefully return 1.0
        delta = compute_tile_visual_delta(Path("/tmp/nonexistent_1.jpg"), Path("/tmp/nonexistent_2.jpg"))
        self.assertEqual(delta, 1.0)

    def test_sample_chunk_keyframes_pinned_cues_and_budget_cap(self):
        import subprocess, tempfile
        from process.multimodal import sample_chunk_keyframes, Image
        with tempfile.TemporaryDirectory() as tmp:
            slides_dir = Path(tmp) / "slides"
            out_dir = Path(tmp) / "tiles"
            slides_dir.mkdir()
            slide_file = slides_dir / "slide_0001.jpg"
            if Image is not None:
                slide = Image.new("RGB", (960, 540), (20, 20, 20))
                slide.save(slide_file)
            else:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x141414:s=960x540", "-frames:v", "1", str(slide_file)],
                    check=True,
                )

            # Static slide with 1 pinned cue at 30s -> keeps anchor + pinned cue (2 frames)
            items = [{"start": 30, "text": "ดูอันนี้สิในจอ"}]
            res = sample_chunk_keyframes(
                0, 60, slides_dir, out_dir, items=items, scene_dedup=True, delta_threshold=0.06, text_tokens=3000
            )
            self.assertEqual(len(res), 2)
            self.assertEqual(res[0][0], "00:00:00")
            self.assertEqual(res[1][0], "00:00:30")

            # With strict budget num_frames=1, anchor and pinned cannot exceed 1 frame
            res_capped = sample_chunk_keyframes(
                0, 60, slides_dir, out_dir, items=items, scene_dedup=True, num_frames=1, delta_threshold=0.06, text_tokens=3000
            )
            self.assertEqual(len(res_capped), 1)

    def test_get_tile_downsampled_bytes_writes_and_reuses_rgb_sidecar(self):
        import subprocess, tempfile
        from process.multimodal import _get_tile_downsampled_bytes, _THUMB_CACHE, Image
        with tempfile.TemporaryDirectory() as tmp:
            tile_path = Path(tmp) / "tile_000010.jpg"
            sidecar = Path(tmp) / "tile_000010.rgb"
            if Image is not None:
                Image.new("RGB", (320, 180), (30, 60, 90)).save(tile_path)
            else:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1e3c5a:s=320x180", "-frames:v", "1", str(tile_path)],
                    check=True,
                )

            # Write corrupted 10-byte sidecar first -> must be ignored and overwritten with 432 bytes
            sidecar.write_bytes(b"corrupted!")
            _THUMB_CACHE.clear()

            raw1 = _get_tile_downsampled_bytes(tile_path)
            self.assertIsNotNone(raw1)
            self.assertEqual(len(raw1), 432)
            self.assertTrue(sidecar.is_file())
            self.assertEqual(sidecar.stat().st_size, 432)

            # Clear memory cache -> should load directly from valid .rgb sidecar
            _THUMB_CACHE.clear()
            raw2 = _get_tile_downsampled_bytes(tile_path)
            self.assertEqual(raw1, raw2)

    def test_sample_chunk_keyframes_default_scene_dedup_is_true(self):
        import subprocess, tempfile
        from process.multimodal import sample_chunk_keyframes, Image
        with tempfile.TemporaryDirectory() as tmp:
            slides_dir = Path(tmp) / "slides"
            out_dir = Path(tmp) / "tiles"
            slides_dir.mkdir()
            slide_file = slides_dir / "slide_0001.jpg"
            if Image is not None:
                slide = Image.new("RGB", (960, 540), (20, 20, 20))
                slide.save(slide_file)
            else:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x141414:s=960x540", "-frames:v", "1", str(slide_file)],
                    check=True,
                )

            # Without passing scene_dedup, default should be True -> static screen produces 1 frame
            res = sample_chunk_keyframes(0, 50, slides_dir, out_dir, text_tokens=3000)
            self.assertEqual(len(res), 1)

    def test_download_storyboard_falls_back_to_144p_ffmpeg_tiling_when_sb_missing(self):
        import tempfile
        from download.ytdlp import download_storyboard
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            clean_dir = ws / "frames" / "slides_clean"

            def fake_run(cmd, **kwargs):
                if "sb0/sb1/sb2/sb3" in cmd:
                    return MagicMock(returncode=1)
                if "video_144p.mp4" in " ".join(str(c) for c in cmd) and "yt-dlp" in str(cmd[0]):
                    (ws / "frames" / "video_144p.mp4").write_bytes(b"mp4")
                    return MagicMock(returncode=0)
                if "ffmpeg" in str(cmd[0]):
                    clean_dir.mkdir(parents=True, exist_ok=True)
                    (clean_dir / "slide_0001.jpg").write_bytes(b"jpg")
                    return MagicMock(returncode=0)
                return MagicMock(returncode=0)

            with patch("subprocess.run", side_effect=fake_run):
                result = download_storyboard("https://www.youtube.com/watch?v=XBtoCdurZ_Y", ws)
                self.assertEqual(result, clean_dir)
                self.assertTrue((clean_dir / "slide_0001.jpg").is_file())


if __name__ == "__main__":
    unittest.main()


