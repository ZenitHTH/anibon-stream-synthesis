import json, re, sys

def format_time(s): 
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

def get_mapreduce_chunks(transcript, block_sec=600, overlap_sec=120):
    for start in range(0, int(transcript[-1]['start'] + transcript[-1]['duration']), block_sec - overlap_sec):
        yield start, start + block_sec, " ".join(f"({format_time(i['start'])}) {i['text'].strip()}" for i in transcript if start <= i['start'] < start + block_sec)

def analyze(path, config_path=None):
    transcript = json.load(open(path, 'r', encoding='utf-8'))
    sections = json.load(open(config_path, 'r', encoding='utf-8')) if config_path else [{"name": "All", "start": 0, "end": float('inf'), "keywords": []}]
    for sec in sections:
        print(f"=== {sec.get('name', 'Section')} ===")
        combined = " ".join(i['text'] for i in transcript if sec.get('start', 0) <= i['start'] < sec.get('end', float('inf')))
        for kw in sec.get("keywords", []):
            if any(re.search(re.escape(pat), combined, re.IGNORECASE) for pat in kw.get('patterns', [])):
                print(f"  Matched: {kw['title']}")

