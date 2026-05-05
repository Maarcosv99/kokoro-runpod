"""Fixtures e mocks globais.

CRÍTICO: substituímos `torch` e `kokoro` em `sys.modules` ANTES do primeiro
import do módulo `handler`. Isso permite rodar os testes sem instalar essas
deps pesadas (~hundreds of MB) localmente.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# Mocka deps pesadas antes de qualquer `import handler`.
_torch_mock = MagicMock()
_torch_mock.cuda.is_available = MagicMock(return_value=False)
sys.modules.setdefault("torch", _torch_mock)
sys.modules.setdefault("kokoro", MagicMock())


@pytest.fixture
def dummy_audio() -> np.ndarray:
    """Áudio float32 sintético: 1 segundo de senoide a 440 Hz, 24 kHz."""
    sr = 24000
    duration = 1.0
    t = np.linspace(0.0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    return (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


@pytest.fixture
def fake_pipeline_factory(dummy_audio: np.ndarray):
    """Cria um pipeline-mock que yielda (graphemes, phonemes, audio)."""

    def _make(num_chunks: int = 1) -> Any:
        chunk_size = len(dummy_audio) // max(num_chunks, 1)

        def _pipeline(text: str, voice: str | None = None, speed: float | None = None):
            for i in range(num_chunks):
                start = i * chunk_size
                end = start + chunk_size if i < num_chunks - 1 else len(dummy_audio)
                yield ("g", "p", dummy_audio[start:end])

        return _pipeline

    return _make


@pytest.fixture
def patch_pipeline(monkeypatch: pytest.MonkeyPatch, fake_pipeline_factory):
    """Substitui `handler.get_pipeline` por um pipeline mock."""
    import handler  # import tardio: já com torch/kokoro mockados

    def _patch(num_chunks: int = 1) -> Any:
        pipeline = fake_pipeline_factory(num_chunks)
        monkeypatch.setattr(handler, "get_pipeline", lambda lang_code: pipeline)
        return pipeline

    return _patch
