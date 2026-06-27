import sys
import subprocess
import json
import re

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print("youtube-transcript-api not found. Installing...", file=sys.stderr)
    subprocess.check_call([sys.executable, "-m", "pip", "install", "youtube-transcript-api"])
    from youtube_transcript_api import YouTubeTranscriptApi

def get_transcript(video_id, languages=['th', 'en']):
    # Try calling as classmethod (older versions of the library)
    if hasattr(YouTubeTranscriptApi, 'get_transcript'):
        try:
            return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        except Exception as e:
            print(f"Error fetching transcript via classmethod: {e}", file=sys.stderr)
    
    # Try calling on an instance (newer versions of the library, e.g. 1.2.4+)
    try:
        api = YouTubeTranscriptApi()
        if hasattr(api, 'fetch'):
            res = api.fetch(video_id, languages=languages)
            if res is not None and not isinstance(res, (list, dict)) and hasattr(res, 'to_raw_data'):
                return res.to_raw_data()
            return res
    except Exception as e:
        print(f"Error fetching transcript via instance: {e}", file=sys.stderr)
        
    # Fallback: list transcripts and fetch first available
    try:
        if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        else:
            api = YouTubeTranscriptApi()
            transcript_list = api.list(video_id)
            
        for tr in transcript_list:
            res = tr.fetch()
            if res is not None and not isinstance(res, (list, dict)) and hasattr(res, 'to_raw_data'):
                return res.to_raw_data()
            return res
    except Exception as e:
        print(f"Fallback error: {e}", file=sys.stderr)
        return None



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch_transcript.py <youtube_video_url_or_id>", file=sys.stderr)
        sys.exit(1)
        
    input_str = sys.argv[1]
    video_id = input_str
    
    # Extract video ID from URL if full URL is provided
    if "youtube.com" in input_str or "youtu.be" in input_str:
        match = re.search(r"(?:v=|\/|embed\/|shorts\/|e\/|youtu\.be\/|v%3D)([0-9A-Za-z_-]{11})", input_str)
        if match:
            video_id = match.group(1)
            
    print(f"Fetching transcript for video ID: {video_id}...", file=sys.stderr)
    transcript = get_transcript(video_id)
    if transcript:
        print(json.dumps(transcript, ensure_ascii=False, indent=2))
    else:
        print("Failed to fetch transcript.", file=sys.stderr)
        sys.exit(1)
