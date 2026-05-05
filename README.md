# kokoro-runpod

Worker Serverless do RunPod (formato Queue) que executa o modelo **Kokoro TTS v1.0** (`hexgrad/Kokoro-82M`) com foco em **português brasileiro**.

## Setup local

Pré-requisito: Python 3.11+ (no Mac, Python 3.13 do sistema funciona — os testes mockam `kokoro` e `torch`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
mypy handler.py
pytest -v
```

Para rodar o handler de verdade localmente (com kokoro instalado, requer `espeak-ng` no host):

```bash
brew install espeak-ng libsndfile         # macOS
pip install -r requirements.txt
python handler.py                         # SDK do runpod lê test_input.json automaticamente
```

## Build Docker local

```bash
docker build --platform linux/amd64 -t kokoro-worker:dev .
```

A build pré-baixa os pesos do Kokoro para PT-BR — o primeiro build leva alguns minutos por isso, mas o cold start em produção fica em segundos.

## Deploy no RunPod via GitHub Integration

1. Faça push deste repositório para o GitHub.
2. Console RunPod → **Serverless** → **New Endpoint**.
3. **Custom Source** → **GitHub Repository** → conecte sua conta e selecione o repo.
4. Branch: `main`. Dockerfile path: `Dockerfile` (raiz).
5. **Endpoint Type**: **Queue**.
6. **GPU**: 16 GB. Marque múltiplas opções para evitar indisponibilidade — recomendado: `A4000`, `RTX 4000 Ada`, `L4`.
7. Workers: `Active 5`, `Max 30`.
8. `Idle Timeout: 5s`, `FlashBoot: ON`, `Execution Timeout: 300s`.
9. (Opcional) Env vars no console: `DEFAULT_LANG=p`, `DEFAULT_VOICE=pf_dora`. Já são defaults no código, mas explícitos facilitam debug.
10. Após o deploy, copie o **Endpoint ID** e gere uma **API Key** em Settings → API Keys. No N8N, configure as credenciais HTTP / variáveis de ambiente do workflow:
    - `RUNPOD_ENDPOINT_ID=...`
    - `RUNPOD_API_KEY=...`

## Schema de input

```json
{
  "input": {
    "text": "string (obrigatório)",
    "voice": "string (default: pf_dora)",
    "lang_code": "string (default: p)",
    "speed": "float (default: 1.0)",
    "format": "wav | opus | flac (default: opus)"
  }
}
```

## Schema de output

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

Em caso de erro: `{ "error": "mensagem" }`.

## Exemplo curl

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

## Vozes PT-BR

| Voice ID    | Gênero    | Observação                |
| ----------- | --------- | ------------------------- |
| `pf_dora`   | Feminina  | Default — boa pra geral.  |
| `pm_alex`   | Masculina | Tom neutro / locução.     |
| `pm_santa`  | Masculina | Tom mais quente / festivo.|

> Outros idiomas (`a` inglês americano, `b` inglês britânico, `j` japonês, etc.) são tecnicamente suportados pela lib `kokoro`, mas **fora do escopo deste worker**: não são pré-aquecidos no Dockerfile e podem causar cold start ao serem solicitados em runtime.

## Variáveis de ambiente

| Var              | Default     | Descrição                                         |
| ---------------- | ----------- | ------------------------------------------------- |
| `DEFAULT_LANG`   | `p`         | `lang_code` usado quando o request não informar.  |
| `DEFAULT_VOICE`  | `pf_dora`   | Voz usada quando o request não informar.          |
| `HF_HOME`        | `/app/.cache/huggingface` | Cache do HuggingFace dentro da imagem. |

## Pontos críticos

- **`concurrency_modifier=4`**: cada worker GPU processa até 4 jobs em paralelo. Kokoro 82M consome ~300MB VRAM por inferência, então 4× cabe folgado em 16 GB. Sem isso, custo sobe ~4×.
- **Modelo embutido na imagem**: `RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='p')"` no Dockerfile cacheia os pesos. Combinado com FlashBoot do RunPod, cold start fica em 2–5s em vez de 30–60s.
- **`/run` (async + polling) vs `/runsync` (síncrono)**: use `/runsync` para textos curtos (<30s de áudio); use `/run` para textos longos ou quando quiser webhook.

## Como consumir do N8N

O worker é consumido via API HTTP do RunPod — qualquer cliente que fale HTTP funciona. No N8N, use um nó **HTTP Request**:

**Caminho síncrono (recomendado para frases curtas, até ~30s de áudio):**

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
- A resposta vem com `output.audio_base64` — use um nó **Code** ou **Move Binary Data** para converter base64 → binário e gravar o arquivo.

**Caminho assíncrono (textos longos):** chame `/run` para receber `{ id }`, depois `/status/{id}` em loop até `status === "COMPLETED"`. Suporta `webhook` no body para evitar polling.

## Documentação adicional

- [`docs/architecture.md`](docs/architecture.md) — diagrama e fluxo
- [`docs/design.md`](docs/design.md) — decisões e trade-offs
- [`docs/explanation.md`](docs/explanation.md) — sobre o modelo Kokoro
- [`AGENT.md`](AGENT.md) — guia para colaboração com agentes de IA
