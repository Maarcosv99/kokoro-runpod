"""RunPod Serverless Queue Worker para Kokoro TTS (PT-BR foco)."""

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
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "p")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "pf_dora")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

SUPPORTED_FORMATS = {"wav", "flac", "opus"}

PIPELINES: dict[str, KPipeline] = {}
_PIPELINE_LOCK = threading.Lock()


def get_pipeline(lang_code: str) -> KPipeline:
    """Lazy-load thread-safe de KPipeline por idioma."""
    pipeline = PIPELINES.get(lang_code)
    if pipeline is not None:
        return pipeline
    with _PIPELINE_LOCK:
        pipeline = PIPELINES.get(lang_code)
        if pipeline is None:
            pipeline = KPipeline(lang_code=lang_code, device=DEVICE)
            PIPELINES[lang_code] = pipeline
    return pipeline


def encode_audio(audio: np.ndarray, fmt: str) -> bytes:
    """Codifica um array float32 em bytes do formato escolhido (wav/flac/opus)."""
    buf = io.BytesIO()
    if fmt == "wav":
        sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    elif fmt == "flac":
        sf.write(buf, audio, SAMPLE_RATE, format="FLAC")
    elif fmt == "opus":
        sf.write(buf, audio, SAMPLE_RATE, format="OGG", subtype="OPUS")
    else:
        raise ValueError(f"formato não suportado: {fmt!r}. Use um de {sorted(SUPPORTED_FORMATS)}")
    return buf.getvalue()


def _to_numpy(chunk: Any) -> np.ndarray:
    if hasattr(chunk, "cpu"):
        chunk = chunk.cpu().numpy()
    return np.asarray(chunk, dtype=np.float32)


def handler(event: dict[str, Any]) -> dict[str, Any]:
    """Handler RunPod: gera TTS a partir de event['input']."""
    try:
        payload = event.get("input") or {}
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return {"error": "campo 'text' é obrigatório e não pode ser vazio"}

        voice = payload.get("voice") or DEFAULT_VOICE
        lang_code = payload.get("lang_code") or DEFAULT_LANG
        speed = float(payload.get("speed") or 1.0)
        fmt = (payload.get("format") or "opus").lower()

        if fmt not in SUPPORTED_FORMATS:
            return {
                "error": f"format inválido: {fmt!r}. Use um de {sorted(SUPPORTED_FORMATS)}",
            }

        pipeline = get_pipeline(lang_code)
        chunks = [_to_numpy(audio) for _, _, audio in pipeline(text, voice=voice, speed=speed)]
        if not chunks:
            return {"error": "pipeline não produziu áudio para o texto fornecido"}

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
    """Permite até 4 jobs concorrentes por worker (Kokoro 82M é leve)."""
    return 4


if __name__ == "__main__":
    # Pré-carrega o idioma default no boot pra evitar cold start no primeiro job.
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
