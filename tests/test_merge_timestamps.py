import pytest
import tempfile
import os
import sys

sys.path.insert(0, "/Users/zenithth/.gemini/config/plugins/anibon-stream-synthesis/skills/anibon-timestamper/scripts")
from merge_timestamps import merge_logic

def test_merge_logic():
    with tempfile.NamedTemporaryFile("w", delete=False) as f1, \
         tempfile.NamedTemporaryFile("w", delete=False) as f2:
        f1.write("00:05:00 - [Talk] Hello\n00:01:00 No Tag\n")
        f2.write("00:01:00 No Tag\n00:10:00 - [News] Update\n")
        
    try:
        results = merge_logic([f1.name, f2.name])
        assert len(results) == 3
        assert results[0].startswith("00:01:00")
        assert results[1].startswith("00:05:00")
        assert results[2].startswith("00:10:00")
    finally:
        os.remove(f1.name)
        os.remove(f2.name)
