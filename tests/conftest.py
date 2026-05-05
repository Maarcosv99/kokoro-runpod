"""Global fixtures and mocks.

CRITICAL: we replace `torch` and `kokoro` in `sys.modules` BEFORE the first
import of the `handler` module. This lets the tests run without installing
those heavy deps (~hundreds of MB) locally.
"""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# Mock heavy deps before any `import handler`.
_torch_mock = MagicMock()
_torch_mock.cuda.is_available = MagicMock(return_value=False)
sys.modules.setdefault("torch", _torch_mock)
sys.modules.setdefault("kokoro", MagicMock())


@pytest.fixture
def dummy_audio() -> np.ndarray:
    """Synthetic float32 audio: 1 second of a 440 Hz sine wave at 24 kHz."""
    sr = 24000
    duration = 1.0
    t = np.linspace(0.0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    return (0.2 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)


@pytest.fixture
def fake_pipeline_factory(dummy_audio: np.ndarray):
    """Build a mock pipeline that yields (graphemes, phonemes, audio)."""

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
    """Replace `handler.get_pipeline` with a mock pipeline."""
    import handler  # late import: torch/kokoro are already mocked

    def _patch(num_chunks: int = 1) -> Any:
        pipeline = fake_pipeline_factory(num_chunks)
        monkeypatch.setattr(handler, "get_pipeline", lambda lang_code: pipeline)
        return pipeline

    return _patch
