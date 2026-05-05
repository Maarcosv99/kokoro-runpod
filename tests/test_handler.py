"""Testes do handler RunPod do Kokoro.

`torch` e `kokoro` são mockados em `conftest.py` antes do import do handler,
então os testes rodam sem instalar essas deps pesadas.
"""

from __future__ import annotations

import base64
import io

import numpy as np
import pytest
import soundfile as sf

import handler


def _decode_response_audio(resp: dict, expected_format: str) -> np.ndarray:
    assert resp.get("error") is None, f"resposta com erro: {resp.get('error')}"
    assert resp["format"] == expected_format
    audio_bytes = base64.b64decode(resp["audio_base64"])
    decoded, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    assert sr == handler.SAMPLE_RATE
    return decoded


def test_concurrency_modifier_returns_4() -> None:
    assert handler.concurrency_modifier(0) == 4
    assert handler.concurrency_modifier(99) == 4


def test_handler_happy_path_opus(patch_pipeline) -> None:
    patch_pipeline()
    event = {"input": {"text": "Olá, teste."}}

    resp = handler.handler(event)

    assert resp["format"] == "opus"
    assert resp["lang_code"] == "p"
    assert resp["voice"] == "pf_dora"
    assert resp["sample_rate"] == 24000
    assert resp["duration_seconds"] == pytest.approx(1.0, abs=0.05)
    audio_bytes = base64.b64decode(resp["audio_base64"])
    # OGG container começa com magic bytes "OggS".
    assert audio_bytes[:4] == b"OggS"


def test_handler_wav_round_trip(patch_pipeline, dummy_audio) -> None:
    patch_pipeline()
    event = {"input": {"text": "wav round trip", "format": "wav"}}

    resp = handler.handler(event)
    decoded = _decode_response_audio(resp, "wav")

    # WAV PCM_16 round-trip: tolerância pelo quantization noise.
    assert decoded.shape == dummy_audio.shape
    np.testing.assert_allclose(decoded, dummy_audio, atol=2e-4)


def test_handler_flac_round_trip(patch_pipeline, dummy_audio) -> None:
    patch_pipeline()
    event = {"input": {"text": "flac round trip", "format": "flac"}}

    resp = handler.handler(event)
    decoded = _decode_response_audio(resp, "flac")

    # FLAC é lossless mas converte float32 → int16 → float32: pequena perda.
    assert decoded.shape == dummy_audio.shape
    np.testing.assert_allclose(decoded, dummy_audio, atol=2e-4)


def test_handler_concatenates_multiple_chunks(patch_pipeline, dummy_audio) -> None:
    patch_pipeline(num_chunks=4)
    event = {"input": {"text": "vários chunks", "format": "wav"}}

    resp = handler.handler(event)
    decoded = _decode_response_audio(resp, "wav")

    assert decoded.shape == dummy_audio.shape


def test_handler_missing_text_returns_error() -> None:
    resp = handler.handler({"input": {}})
    assert "error" in resp
    assert "text" in resp["error"].lower()


def test_handler_empty_text_returns_error() -> None:
    resp = handler.handler({"input": {"text": "   "}})
    assert "error" in resp
    assert "text" in resp["error"].lower()


def test_handler_invalid_format_returns_error(patch_pipeline) -> None:
    patch_pipeline()
    resp = handler.handler({"input": {"text": "x", "format": "mp3"}})
    assert "error" in resp
    assert "format" in resp["error"].lower()


def test_handler_pipeline_returns_no_chunks(monkeypatch) -> None:
    def empty_pipeline(*args, **kwargs):
        return iter([])

    monkeypatch.setattr(handler, "get_pipeline", lambda lang_code: empty_pipeline)
    resp = handler.handler({"input": {"text": "vazio"}})

    assert "error" in resp
    assert "áudio" in resp["error"].lower() or "audio" in resp["error"].lower()


def test_handler_propagates_pipeline_exception(monkeypatch) -> None:
    def boom_pipeline(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "get_pipeline", lambda lang_code: boom_pipeline)
    resp = handler.handler({"input": {"text": "ué"}})

    assert "error" in resp
    assert "boom" in resp["error"]


def test_encode_audio_unknown_format_raises(dummy_audio) -> None:
    with pytest.raises(ValueError, match="formato não suportado"):
        handler.encode_audio(dummy_audio, "mp3")


def test_handler_respects_custom_voice_and_lang(patch_pipeline) -> None:
    patch_pipeline()
    resp = handler.handler({"input": {"text": "x", "voice": "pm_alex", "lang_code": "p"}})
    assert resp["voice"] == "pm_alex"
    assert resp["lang_code"] == "p"
