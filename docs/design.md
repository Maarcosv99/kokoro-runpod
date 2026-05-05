# Design decisions

Each section lists the decision, alternatives considered, and the rationale.

## Why Queue Worker, not Load Balancer?

**Decision**: use the Queue format (`runpod.serverless.start(...)`) instead of Load Balancer (FastAPI behind an LB).

**Alternative**: run FastAPI/Uvicorn inside the container and expose a `/tts` route. RunPod offers this mode via Load Balancer.

**Rationale**:
- Queue is simpler — no HTTP infrastructure, no graceful shutdown to worry about.
- Queue handles spikes better: jobs sit in RunPod's queue without forcing reactive worker scaling.
- The consumer already calls the RunPod HTTP API (`/run`, `/runsync`, `/status`), so we don't need to serve HTTP ourselves.
- Cost is the same: billing is by GPU-time, not by request count.

## Why `concurrency_modifier=4`?

**Decision**: each worker handles up to 4 jobs in parallel.

**Alternative**: 1 job per worker (RunPod's default).

**Rationale**:
- Kokoro 82M is light: ~300 MB VRAM per inference. 4 in parallel fit in 16 GB with room to spare.
- TTS inference is partially I/O-bound (espeak-ng phonemization runs on CPU). 4 threads keep the CPU busy while the GPU works on a chunk.
- Cuts cost ~75% for the same throughput vs. 1:1.

**Mitigated risk**: if we observe OOM, we just lower the returned value.

## Why pre-download the model in the Dockerfile?

**Decision**: `RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='p')"` during build.

**Alternative**: download at boot (`handler.py`) or use a Network Volume for the weights.

**Rationale**:
- The build embeds the weights into the image (~330 MB). Cold start drops to ~5s instead of 30–60s.
- Network Volumes add network latency at boot and a recurring monthly cost.
- The model is stable (versioned by the image tag), so embedding it is fine.

## Why a single language (PT-BR)?

**Decision**: defaults, warmup, and docs are all PT-BR. Other languages still work but aren't pre-warmed.

**Rationale**:
- Current use case is 100% PT-BR.
- Pre-warming multiple languages doubles build time and image size.
- Keeping the door open (the `kokoro` library accepts any `lang_code` at runtime) costs nothing.

## Why `soundfile` instead of `pydub` or `ffmpeg-python`?

**Decision**: `soundfile` for WAV/FLAC/OPUS encoding.

**Rationale**:
- No subprocess dependencies (`pydub` shells out to `ffmpeg`).
- Native `BytesIO` support — no temp files.
- Already an indirect dependency of `kokoro`.

**Trade-off**: MP3 isn't natively supported by `soundfile` (needs LAME). Since OPUS is lighter and higher quality, MP3 was left out.

## `/run` (async + polling) vs `/runsync` (sync)

**Decision**: the repo doesn't ship a client. The consumer (N8N) picks the endpoint per situation.

**Rationale**:
- `/runsync` is the natural path for short texts (up to ~30s of audio): a single HTTP call from the N8N HTTP Request node and the audio comes back in the response.
- `/runsync` has a connection timeout (~30s on RunPod). Long texts blow past it.
- `/run` + polling on `/status/{id}` (or webhook) covers long texts. In N8N, this means an initial HTTP node plus a sub-workflow / loop with Wait + HTTP until `status === "COMPLETED"`.

## Why mock `kokoro` and `torch` in tests?

**Decision**: `tests/conftest.py` injects `MagicMock` into `sys.modules` before importing `handler`.

**Rationale**:
- `torch` on macOS arm64 is ~200 MB. `kokoro` pulls `transformers`, `huggingface_hub`, etc. — heavy install.
- Tests validate handler logic (input parsing, encoding, response shape), not the model itself.
- Avoids requiring `espeak-ng` on the host to run tests.
- CI runs on Python 3.11 and finishes in seconds.

**Trade-off**: bugs that only show up with real `kokoro` (e.g. a changed `KPipeline.__call__` signature) only get caught at integration time. Mitigated by the Docker build itself, which imports `kokoro` for real.

## Why GitHub Integration instead of RunPod Hub?

**Decision**: deploy via Custom Source → GitHub Repository.

**Rationale**:
- The Hub is geared toward publishing reusable templates for other users.
- GitHub Integration auto-builds on every push to `main`.
- No extra effort to publish (and no "public" version we don't want).
