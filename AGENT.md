# AGENT.md

Guide for collaborating with AI agents (Claude Code, Cursor, etc.) on this repository.

## What this project is

A RunPod Serverless worker (Queue format) that serves **Kokoro TTS v1.0** for voice synthesis in **Brazilian Portuguese**. Consumption happens through **N8N** (an HTTP Request node) calling the RunPod API (`/runsync` or `/run` + polling). There's no client code in this repository — it's Python only (worker). Details in [`README.md`](README.md).

## Where to find information

| Question                                  | Where to look                                  |
| ----------------------------------------- | ---------------------------------------------- |
| How to run / deploy?                      | [`README.md`](README.md)                       |
| Architecture overview?                    | [`docs/architecture.md`](docs/architecture.md) |
| Why was decision X made?                  | [`docs/design.md`](docs/design.md)             |
| About the Kokoro model / voices / limits? | [`docs/explanation.md`](docs/explanation.md)   |
| Handler input/output schema?              | `README.md` + `handler.py:handler`             |
| How to run tests / CI?                    | "Useful commands" section below                |

## Claude Code subagents

The subagents live in `.claude/agents/` and are invoked by Claude Code through the `Task` tool. Pick the right agent per phase:

| Agent        | When to use                                                                                                                  |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| `researcher` | Before any change that depends on external info (changes to the `kokoro` API, a new RunPod SDK version, new voices).         |
| `planner`    | To break complex changes into steps that reference existing files and patterns.                                              |
| `executor`   | To implement approved plans, following `ruff format`, type hints, and adding tests.                                          |
| `tester`     | To write / run pytest tests mocking `KPipeline`, and to enforce `ruff` + `mypy` + `pytest`.                                  |

## Recommended skills (Claude Code)

Native Claude Code skills (and the `superpowers` plugin) that help in this project:

- **`coding-guidelines`** — general implementation discipline (no dead code, no over-engineering, no superfluous comments).
- **`superpowers:test-driven-development`** — write the test before the feature; vital for handler changes.
- **`docs-writer`** — keep the `docs/` folder consistent in structure and tone.
- **`superpowers:verification-before-completion`** — always run `ruff && mypy && pytest` before declaring a task done.

## Useful commands

```bash
# Setup (one-off)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Development loop
ruff check .                 # lint
ruff format .                # auto-format
mypy handler.py              # type-check
pytest -v                    # tests (kokoro/torch are mocked)
pytest --cov=handler         # coverage

# Docker build (requires Docker Desktop)
docker build --platform linux/amd64 -t kokoro-worker:dev .
```

## Conventions

- **Single language**: PT-BR. Don't add defaults in other languages without checking with the repo owner.
- **Do not** install `kokoro` or `torch` in `requirements-dev.txt` — tests mock them.
- **Do not** use FastAPI/Uvicorn — this is a Queue Worker.
- **Do not** create `.runpod/hub.json` — deploy is via GitHub Integration, not Hub.
- Handler error messages flow back to the consumer (N8N) as `{"error": "..."}` — write them in PT-BR (the consumer audience is PT-BR).
- **No TypeScript / JavaScript / Node code** in this repo — consumption is via N8N HTTP. Don't re-add `client/`.
- Comment only where the **why** isn't obvious from the code.
