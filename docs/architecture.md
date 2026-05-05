# Architecture

## Overview

```mermaid
flowchart LR
    N8N[N8N HTTP Request node]

    N8N -->|POST /runsync or /run| RUNPOD_API[RunPod API]
    N8N -->|GET /status/&#123;id&#125; polling| RUNPOD_API
    RUNPOD_API --> QUEUE[(Job Queue)]

    subgraph RunPod_Serverless
        QUEUE --> WORKER1[Worker GPU #1]
        QUEUE --> WORKER2[Worker GPU #2]
        WORKER1 --> H1[handler.py]
        WORKER2 --> H2[handler.py]
        H1 -->|KPipeline 'p'| KOKORO1[(Kokoro 82M)]
        H2 -->|KPipeline 'p'| KOKORO2[(Kokoro 82M)]
        KOKORO1 --> AUDIO1[soundfile encode opus/wav/flac]
        KOKORO2 --> AUDIO2[soundfile encode opus/wav/flac]
    end

    AUDIO1 -->|audio_base64| RUNPOD_API
    AUDIO2 -->|audio_base64| RUNPOD_API
    RUNPOD_API -->|JSON response| N8N
```

## Components

- **N8N (consumer)**: an **HTTP Request** node calls `POST /v2/{endpoint}/runsync` (synchronous, up to 30s) or `POST /v2/{endpoint}/run` + polling on `/status/{id}` (asynchronous). The JSON response carries `output.audio_base64`, decoded into binary by a **Code** or **Move Binary Data** node.
- **RunPod API**: routes jobs to free workers in the configured endpoint's queue.
- **Worker** (`handler.py`): handles up to 4 concurrent jobs per worker via `concurrency_modifier`.
- **`KPipeline`** (`kokoro` lib): tokenizes the text, generates phonemes (via `misaki[pt]`), synthesizes audio chunk by chunk.
- **`soundfile`**: encodes the final numpy array into OPUS/WAV/FLAC without touching disk (`io.BytesIO`).

## Cold-start flow

1. RunPod spins up an idle container (FlashBoot skips this step when a snapshot exists).
2. The container runs `CMD ["python3.11", "-u", "handler.py"]`.
3. The `if __name__ == "__main__"` block calls `get_pipeline(DEFAULT_LANG)` → loads the PT-BR model into the GPU.
4. `runpod.serverless.start(...)` enters the queue-fetch loop.
5. The first job is processed.

**Without the pre-load (step 3)**, the first job would pay ~10s of HF download + ~5s of model loading. Because the weights are already on the filesystem (cached by the `RUN python -c ...` line in the Dockerfile), we only pay the load.

**With FlashBoot**, RunPod snapshots the container once it reaches the post-load state. Cold start drops from ~10s to 2–5s.

## Job flow

```mermaid
sequenceDiagram
    participant N as N8N
    participant R as RunPod API
    participant W as Worker (handler.py)

    N->>R: POST /run { input: { text, voice, ... } }
    R-->>N: { id: "abc", status: "IN_QUEUE" }
    R->>W: dispatch job
    W->>W: pipeline = PIPELINES["p"]
    W->>W: chunks = [audio for _, _, audio in pipeline(text, voice, speed)]
    W->>W: audio = np.concatenate(chunks)
    W->>W: bytes = encode_audio(audio, "opus")
    W-->>R: { audio_base64, format, ... }

    loop polling
        N->>R: GET /status/abc
        R-->>N: { status: "IN_PROGRESS" }
    end

    N->>R: GET /status/abc
    R-->>N: { status: "COMPLETED", output: { audio_base64, ... } }
    N->>N: decode base64 → binary file
```

## Per-worker concurrency

Each GPU worker can process up to 4 simultaneous jobs:

- The SDK's internal loop calls `concurrency_modifier(current_count)` periodically.
- As long as the return value (`4`) is greater than `current_count`, the worker pulls another job.
- `KPipeline` is thread-safe for inference; the `PIPELINES` cache is guarded by `_PIPELINE_LOCK` only during initial creation.

## Limits and cost

| Resource             | Value                                       |
| -------------------- | ------------------------------------------- |
| VRAM per worker      | 16 GB (4× ~300 MB for Kokoro)               |
| Concurrency / worker | 4 jobs                                      |
| Estimated throughput | ~100 jobs/min per worker (depends on text length) |
| Active workers       | 5 (set in the console)                      |
| Max workers          | 30 (auto-scale)                             |
| Idle timeout         | 5s (workers shut down quickly to save cost) |
