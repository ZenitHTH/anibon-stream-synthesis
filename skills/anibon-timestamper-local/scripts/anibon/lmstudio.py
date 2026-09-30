"""LM Studio / OpenAI-compatible client module for local text and vision inference.

Supports:
- Model auto-resolution & JIT eviction prevention on Pascal/P100 GPUs
- Text completions with system prompt constraints
- Multi-modal Vision API calls (Base64 data URI image_url) for Gemma 3/4 12B Vision, Qwen-VL
"""
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

SYSTEM_PROMPT = """\
You are an expert livestream editor for Thai livestreams by Pu Boat (Anibon Official).
CRITICAL INSTRUCTION: Keep your internal thinking under 2 sentences. \
Do NOT list items or transcribe text in your thinking. \
Proceed immediately to outputting the final decision."""


def get_loaded_models(endpoint: Optional[str] = None) -> List[str]:
    """Query LM Studio for currently loaded models in memory (via HTTP API or CLI)."""
    if endpoint:
        try:
            m = re.match(r"(https?://[^/]+)", endpoint)
            base = m.group(1) if m else endpoint
            url = f"{base}/api/v0/models"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                loaded = [m.get("id") for m in data.get("data", []) if m.get("state") == "loaded"]
                if loaded:
                    return loaded
        except Exception:
            pass

    try:
        res = subprocess.run(
            ["lms", "ps", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return [m.get("identifier") for m in data if m.get("identifier")]
    except Exception:
        pass
    return []


def resolve_model(requested_model: str, endpoint: str, force: bool = False) -> str:
    """Resolve which model to use, preventing JIT eviction on Tesla P100."""
    preferred_models = (
        "unsloth/gemma-4-26b-a4b-it@q2_k_x",
        "gemma-4-26b-a4b-it@q2_k_xl",
        "gemma-4-26b-a4b-it@q2_k_x",
        "google/gemma-4-12b-qat",
        "google/gemma-3-12b-it",
        "qwen/qwen3.5-9b",
    )
    loaded = get_loaded_models(endpoint)
    if loaded:
        print(f"[init] LM Studio loaded model(s): {', '.join(loaded)}")
        if not requested_model or requested_model.lower() == "auto":
            for preferred in preferred_models:
                for lm in loaded:
                    if preferred in lm or lm in preferred:
                        print(f"[init] Auto-selected loaded model: {lm}")
                        return lm
            return loaded[0]

        for lm in loaded:
            if requested_model == lm or requested_model in lm or lm in requested_model:
                print(f"[init] Using requested loaded model: {lm}")
                return lm

        if force:
            return requested_model

        fallback = loaded[0]
        for preferred in preferred_models:
            for lm in loaded:
                if preferred in lm or lm in preferred:
                    fallback = lm
                    break
        print(f"[warn] '{requested_model}' not loaded; using '{fallback}' to prevent eviction.", file=sys.stderr)
        return fallback

    return "unsloth/gemma-4-26b-a4b-it@q2_k_x" if (not requested_model or requested_model.lower() == "auto") else requested_model


def encode_image_base64(image_path: Union[str, Path]) -> str:
    """Read a local image file and encode it as a base64 data URI."""
    p = Path(image_path)
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")
    suffix = p.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def build_chat_payload(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str = SYSTEM_PROMPT,
) -> Dict[str, Any]:
    """Construct standard OpenAI-compatible text chat payload."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def build_vision_payload(
    model: str,
    prompt: str,
    image_url_or_data: str,
    max_tokens: int = 500,
    temperature: float = 0.2,
    system_prompt: str = SYSTEM_PROMPT,
) -> Dict[str, Any]:
    """Construct standard OpenAI multi-modal vision payload."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url_or_data},
                    },
                ],
            },
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


def call_local(
    endpoint: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: str = SYSTEM_PROMPT,
    timeout: int = 180,
    retries: int = 2,
) -> str:
    """Call local OpenAI-compatible API for text generation."""
    payload = build_chat_payload(model, prompt, max_tokens, temperature, system_prompt)
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            msg = data["choices"][0]["message"]
            content = msg.get("content", "").strip()

            if not content and msg.get("reasoning_content"):
                rc = msg["reasoning_content"]
                if "ส่วนที่" in rc or "════" in rc:
                    content = rc
                else:
                    m = re.findall(r"(\d{2}:\d{2}:\d{2}\s*-\s*\[[\w]+\]\s*[^\n]+)", rc)
                    if m:
                        content = "\n".join(m)
                    elif "CONTINUATION" in rc.upper() or "SKIP" in rc.upper():
                        content = "CONTINUATION"
                    else:
                        content = rc
            return content
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2)

    raise last_err or RuntimeError("Failed to call local model endpoint")


def call_vision(
    endpoint: str,
    model: str,
    prompt: str,
    image_path: Union[str, Path],
    max_tokens: int = 500,
    temperature: float = 0.2,
    timeout: int = 180,
) -> str:
    """Call local LM Studio vision endpoint with an image file."""
    data_uri = encode_image_base64(image_path)
    payload = build_vision_payload(model, prompt, data_uri, max_tokens, temperature)
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data["choices"][0]["message"]
    return msg.get("content", "").strip()
