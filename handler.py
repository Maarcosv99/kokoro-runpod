"""RunPod Serverless Queue Worker for Kokoro TTS (PT-BR focus)."""

from __future__ import annotations

import base64
import io
import os
import threading
import traceback
from typing import Any

import numpy as np
import runpod
import soundfile as sf
import torch
from kokoro import KPipeline

SAMPLE_RATE = 24000
KOKORO_REPO_ID = "hexgrad/Kokoro-82M"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

SUPPORTED_FORMATS = {"wav", "flac", "opus"}

# Kokoro accepts single-letter codes; accept common aliases coming from N8N
# clients or misconfigured RunPod env-vars (e.g. DEFAULT_LANG=pt) and map them.
LANG_CODE_ALIASES = {
    "pt": "p",
    "pt-br": "p",
    "pt_br": "p",
    "ptbr": "p",
    "en": "a",
    "en-us": "a",
    "en_us": "a",
    "en-gb": "b",
    "en_gb": "b",
    "es": "e",
    "fr": "f",
    "fr-fr": "f",
    "fr_fr": "f",
    "hi": "h",
    "it": "i",
    "ja": "j",
    "jp": "j",
    "zh": "z",
    "zh-cn": "z",
    "zh_cn": "z",
}
SUPPORTED_LANG_CODES = frozenset(LANG_CODE_ALIASES.values())


def normalize_lang_code(code: str) -> str:
    return LANG_CODE_ALIASES.get(code.strip().lower(), code)


DEFAULT_LANG = normalize_lang_code(os.getenv("DEFAULT_LANG", "p"))
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "pf_dora")

PIPELINES: dict[str, KPipeline] = {}
_PIPELINE_LOCK = threading.Lock()


def get_pipeline(lang_code: str) -> KPipeline:
    """Thread-safe lazy-load of KPipeline per language."""
    pipeline = PIPELINES.get(lang_code)
    if pipeline is not None:
        return pipeline
    with _PIPELINE_LOCK:
        pipeline = PIPELINES.get(lang_code)
        if pipeline is None:
            pipeline = KPipeline(lang_code=lang_code, repo_id=KOKORO_REPO_ID, device=DEVICE)
            PIPELINES[lang_code] = pipeline
    return pipeline


def encode_audio(audio: np.ndarray, fmt: str) -> bytes:
    """Encode a float32 array into bytes of the chosen format (wav/flac/opus)."""
    buf = io.BytesIO()
    if fmt == "wav":
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    elif fmt == "flac":
        sf.write(buf, audio, SAMPLE_RATE, format="FLAC")
    elif fmt == "opus":
        sf.write(buf, audio, SAMPLE_RATE, format="OGG", subtype="OPUS")
    else:
        raise ValueError(f"unsupported format: {fmt!r}. Use one of {sorted(SUPPORTED_FORMATS)}")
    return buf.getvalue()


def _to_numpy(chunk: Any) -> np.ndarray:
    if hasattr(chunk, "cpu"):
        chunk = chunk.cpu().numpy()
    return np.asarray(chunk, dtype=np.float32)


def handler(event: dict[str, Any]) -> dict[str, Any]:
    """RunPod handler: generate TTS from event['input']."""
    try:
        payload = event.get("input") or {}
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"error": "field 'text' is required and cannot be empty"}

        voice = payload.get("voice") or DEFAULT_VOICE
        raw_lang_code = payload.get("lang_code") or DEFAULT_LANG
        lang_code = normalize_lang_code(raw_lang_code)
        speed = float(payload.get("speed") or 1.0)
        fmt = (payload.get("format") or "opus").lower()

        if fmt not in SUPPORTED_FORMATS:
            return {
                "error": f"invalid format: {fmt!r}. Use one of {sorted(SUPPORTED_FORMATS)}",
            }

        if lang_code not in SUPPORTED_LANG_CODES:
            return {
                "error": (
                    f"invalid lang_code: {raw_lang_code!r}. "
                    f"Use one of {sorted(SUPPORTED_LANG_CODES)} "
                    f"or aliases like {sorted(LANG_CODE_ALIASES)}"
                ),
            }

        pipeline = get_pipeline(lang_code)
        chunks = [_to_numpy(audio) for _, _, audio in pipeline(text, voice=voice, speed=speed)]
        if not chunks:
            return {"error": "pipeline produced no audio for the given text"}

        audio = np.concatenate(chunks).astype(np.float32, copy=False)
        audio_bytes = encode_audio(audio, fmt)

        return {
            "audio_base64": base64.b64encode(audio_bytes).decode("ascii"),
            "format": fmt,
            "sample_rate": SAMPLE_RATE,
            "duration_seconds": round(len(audio) / SAMPLE_RATE, 3),
            "voice": voice,
            "lang_code": lang_code,
        }
    except Exception as exc:
        traceback.print_exc()
        return {"error": str(exc)}


def concurrency_modifier(_current: int) -> int:
    """Allow up to 4 concurrent jobs per worker (Kokoro 82M is light)."""
    return 4


if __name__ == "__main__":
    # Pre-load the default language at boot to avoid cold start on the first job.
    try:
        get_pipeline(DEFAULT_LANG)
    except Exception:
        traceback.print_exc()

    runpod.serverless.start(
        {
            "handler": handler,
            "concurrency_modifier": concurrency_modifier,
        }
    )
