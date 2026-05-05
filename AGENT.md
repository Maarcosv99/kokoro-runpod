# AGENT.md

Guia para colaboração com agentes de IA (Claude Code, Cursor, etc.) neste repositório.

## O que é este projeto

Worker Serverless do RunPod (formato Queue) que serve **Kokoro TTS v1.0** para síntese de voz em **português brasileiro**. O consumo é feito via **N8N** (nó HTTP Request) chamando a API do RunPod (`/runsync` ou `/run` + polling). Não há cliente em código neste repositório — é só Python (worker). Detalhes em [`README.md`](README.md).

## Onde encontrar informações

| Pergunta                                  | Onde olhar                              |
| ----------------------------------------- | --------------------------------------- |
| Como rodar / fazer deploy?                | [`README.md`](README.md)                |
| Visão geral da arquitetura?               | [`docs/architecture.md`](docs/architecture.md) |
| Por que tal decisão foi tomada?           | [`docs/design.md`](docs/design.md)      |
| Sobre o modelo Kokoro / vozes / limites?  | [`docs/explanation.md`](docs/explanation.md) |
| Schema de input/output do handler?        | `README.md` + `handler.py:handler`      |
| Como rodar testes / CI?                   | Seção "Comandos úteis" abaixo           |

## Subagentes Claude Code

Os subagentes ficam em `.claude/agents/` e são invocados pelo Claude Code via tool `Task`. Use o agente certo pra cada fase:

| Agente       | Quando usar                                                    |
| ------------ | -------------------------------------------------------------- |
| `researcher` | Antes de qualquer mudança que dependa de info externa (mudanças na API do `kokoro`, nova versão do SDK do RunPod, vozes novas). |
| `planner`    | Para quebrar mudanças complexas em passos referenciando arquivos e padrões existentes. |
| `executor`   | Para implementar planos aprovados, seguindo `ruff format`, type hints e adicionando testes. |
| `tester`     | Para escrever / rodar testes pytest mockando `KPipeline`, e validar `ruff` + `mypy` + `pytest`. |

## Skills recomendadas (Claude Code)

Skills nativas do Claude Code (e plugin `superpowers`) que ajudam neste projeto:

- **`coding-guidelines`** — disciplina geral de implementação (sem código morto, sem over-engineering, sem comentários supérfluos).
- **`superpowers:test-driven-development`** — escreva o teste antes da feature; vital pra mudanças no `handler`.
- **`docs-writer`** — manutenção da pasta `docs/` consistente em estrutura e tom.
- **`superpowers:verification-before-completion`** — sempre rode `ruff && mypy && pytest` antes de declarar uma tarefa concluída.

## Comandos úteis

```bash
# Setup (uma vez)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Loop de desenvolvimento
ruff check .                 # lint
ruff format .                # auto-format
mypy handler.py              # type-check
pytest -v                    # testes (kokoro/torch são mockados)
pytest --cov=handler         # cobertura

# Build Docker (precisa Docker Desktop)
docker build --platform linux/amd64 -t kokoro-worker:dev .
```

## Convenções

- **Idioma único**: PT-BR. Não adicione defaults em outras línguas sem alinhar com o dono do repo.
- **Não** instale `kokoro` ou `torch` em `requirements-dev.txt` — testes mockam.
- **Não** use FastAPI/Uvicorn — é Queue Worker.
- **Não** crie arquivos `.runpod/hub.json` — deploy é via GitHub Integration, não Hub.
- Mensagens de erro do `handler` voltam pro consumidor (N8N) como `{"error": "..."}` — escreva-as em PT-BR.
- **Sem código TypeScript / JavaScript / Node** neste repo — o consumo é via N8N HTTP. Não readicione `client/`.
- Comentários só onde o **porquê** não é óbvio do código.
