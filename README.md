# kokoro-runpod

RunPod Serverless worker (Queue format) that runs the **Kokoro TTS v1.0** model (`hexgrad/Kokoro-82M`) with a focus on **Brazilian Portuguese**.

## Local setup

Prerequisite: Python 3.11+ (on macOS the system's Python 3.13 works fine — the tests mock `kokoro` and `torch`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
mypy handler.py
pytest -v
```

To run the handler for real locally (with `kokoro` installed; requires `espeak-ng` on the host):

```bash
brew install espeak-ng libsndfile         # macOS
pip install -r requirements.txt
python handler.py                         # the runpod SDK reads test_input.json automatically
```

## Local Docker build

```bash
docker build --platform linux/amd64 -t kokoro-worker:dev .
```

The build pre-downloads the Kokoro PT-BR weights — the first build takes a few minutes because of that, but the production cold start drops to seconds.

## Deploy to RunPod via GitHub Integration

1. Push this repository to GitHub.
2. RunPod console → **Serverless** → **New Endpoint**.
3. **Custom Source** → **GitHub Repository** → connect your account and pick the repo.
4. Branch: `main`. Dockerfile path: `Dockerfile` (root).
5. **Endpoint Type**: **Queue**.
6. **GPU**: 16 GB. Tick multiple options to avoid availability issues — recommended: `A4000`, `RTX 4000 Ada`, `L4`.
7. Workers: `Active 5`, `Max 30`.
8. `Idle Timeout: 5s`, `FlashBoot: ON`, `Execution Timeout: 300s`.
9. (Optional) Env vars in the console: `DEFAULT_LANG=p`, `DEFAULT_VOICE=pf_dora`. These are already the code defaults, but setting them explicitly makes debugging easier.
10. After deploy, copy the **Endpoint ID** and generate an **API Key** in Settings → API Keys. In N8N, configure the HTTP credentials / workflow environment variables:
    - `RUNPOD_ENDPOINT_ID=...`
    - `RUNPOD_API_KEY=...`

## Input schema

```json
{
  "input": {
    "text": "string (required)",
    "voice": "string (default: pf_dora)",
    "lang_code": "string (default: p)",
    "speed": "float (default: 1.0)",
    "format": "wav | opus | flac (default: opus)"
  }
}
```

## Output schema

```json
{
  "audio_base64": "...",
  "format": "opus",
  "sample_rate": 24000,
  "duration_seconds": 3.421,
  "voice": "pf_dora",
  "lang_code": "p"
}
```

On error: `{ "error": "message" }`.

## curl example

```bash
curl -X POST "https://api.runpod.ai/v2/$RUNPOD_ENDPOINT_ID/runsync" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Olá, mundo! Bem-vindo ao Kokoro.",
      "voice": "pf_dora",
      "lang_code": "p",
      "format": "opus"
    }
  }'
```

## PT-BR voices

| Voice ID    | Gender | Notes                              |
| ----------- | ------ | ---------------------------------- |
| `pf_dora`   | Female | Default — solid general-purpose.   |
| `pm_alex`   | Male   | Neutral tone, good for narration.  |
| `pm_santa`  | Male   | Warmer, festive tone.              |

> Other languages (`a` American English, `b` British English, `j` Japanese, etc.) are technically supported by the `kokoro` library but **out of scope for this worker**: they are not pre-warmed in the Dockerfile and may incur a cold start when first requested at runtime.

## Environment variables

| Var              | Default     | Description                                    |
| ---------------- | ----------- | ---------------------------------------------- |
| `DEFAULT_LANG`   | `p`         | `lang_code` used when the request omits it.    |
| `DEFAULT_VOICE`  | `pf_dora`   | Voice used when the request omits it.          |
| `HF_HOME`        | `/app/.cache/huggingface` | HuggingFace cache inside the image. |

## Critical notes

- **`concurrency_modifier=4`**: each GPU worker handles up to 4 jobs in parallel. Kokoro 82M consumes ~300 MB of VRAM per inference, so 4× fits comfortably in 16 GB. Without this, cost goes up roughly 4×.
- **Model baked into the image**: `RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='p')"` in the Dockerfile caches the weights. Combined with RunPod FlashBoot, cold start drops to 2–5s instead of 30–60s.
- **`/run` (async + polling) vs `/runsync` (sync)**: use `/runsync` for short texts (<30s of audio); use `/run` for long texts or when you want a webhook.

## Consuming from N8N

The worker is consumed via the RunPod HTTP API — any HTTP-capable client works. In N8N, use an **HTTP Request** node:

**Synchronous path (recommended for short phrases, up to ~30s of audio):**

- Method: `POST`
- URL: `https://api.runpod.ai/v2/{{$env.RUNPOD_ENDPOINT_ID}}/runsync`
- Headers: `Authorization: Bearer {{$env.RUNPOD_API_KEY}}`, `Content-Type: application/json`
- Body (JSON):
  ```json
  {
    "input": {
      "text": "{{$json.text}}",
      "voice": "pf_dora",
      "lang_code": "p",
      "format": "opus"
    }
  }
  ```
- The response carries `output.audio_base64` — use a **Code** or **Move Binary Data** node to convert base64 → binary and write the file.

**Asynchronous path (long texts):** call `/run` to receive `{ id }`, then `/status/{id}` in a loop until `status === "COMPLETED"`. Supports a `webhook` field in the body to skip polling.

## Additional documentation

- [`docs/architecture.md`](docs/architecture.md) — diagram and flow
- [`docs/design.md`](docs/design.md) — decisions and trade-offs
- [`docs/explanation.md`](docs/explanation.md) — about the Kokoro model
- [`AGENT.md`](AGENT.md) — guide for collaborating with AI agents
