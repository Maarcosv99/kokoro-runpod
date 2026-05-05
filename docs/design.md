# Decisões de design

Cada seção lista a decisão, alternativas consideradas e o motivo da escolha.

## Por que Queue Worker, não Load Balancer?

**Decisão**: usar o formato Queue (`runpod.serverless.start(...)`) em vez de Load Balancer (FastAPI atrás de um LB).

**Alternativa**: rodar FastAPI/Uvicorn dentro do container e expor uma rota `/tts`. RunPod oferece esse modo via Load Balancer.

**Motivo**:
- Queue é mais simples — sem infraestrutura HTTP, sem precisar lidar com graceful shutdown.
- Queue lida melhor com picos: jobs ficam na fila do RunPod sem precisar dimensionar workers reativamente.
- O cliente já consome via API HTTP do RunPod (`/run`, `/runsync`, `/status`), então não precisamos servir HTTP nós mesmos.
- Custo é o mesmo: cobrança é por GPU-time, não por requests.

## Por que `concurrency_modifier=4`?

**Decisão**: cada worker processa até 4 jobs em paralelo.

**Alternativa**: 1 job por worker (default do RunPod).

**Motivo**:
- Kokoro 82M é leve: ~300 MB VRAM por inferência. 4 simultâneos cabem em 16 GB com folga.
- Inferência TTS é I/O-bound em parte (espeak-ng phonemization é CPU). 4 threads aproveitam CPU enquanto a GPU processa um chunk.
- Reduz custo em ~75% para o mesmo throughput vs. 1:1.

**Risco mitigado**: se observarmos OOM, basta diminuir o número retornado.

## Por que pré-baixar o modelo no Dockerfile?

**Decisão**: `RUN python -c "from kokoro import KPipeline; KPipeline(lang_code='p')"` na build.

**Alternativa**: baixar no boot (handler.py) ou usar Network Volume com pesos.

**Motivo**:
- Build embute os pesos na imagem (~330 MB). Cold start fica em ~5s em vez de 30–60s.
- Network Volume tem latência de rede no boot e custo extra mensal.
- O modelo é estável (versionado pela tag da imagem), então embutir é OK.

## Por que idioma único (PT-BR)?

**Decisão**: defaults, warmup e docs todos em PT-BR. Outros idiomas funcionam mas não são pré-aquecidos.

**Motivo**:
- Caso de uso atual é 100% PT-BR.
- Pré-aquecer múltiplos idiomas duplica o tempo de build e o tamanho da imagem.
- Manter a porta aberta (a lib `kokoro` aceita `lang_code` em runtime) custa nada.

## Por que `soundfile` em vez de `pydub` ou `ffmpeg-python`?

**Decisão**: `soundfile` para encoding WAV/FLAC/OPUS.

**Motivo**:
- Zero dependências de subprocess (`pydub` chama `ffmpeg` via shell).
- Suporte nativo a `BytesIO` — sem arquivos temporários.
- Já é dependência indireta de `kokoro`.

**Trade-off**: MP3 não é suportado nativamente por `soundfile` (precisa LAME). Como OPUS é mais leve e melhor qualidade, MP3 ficou fora.

## `/run` (async + polling) vs `/runsync` (síncrono)

**Decisão**: o repo não inclui cliente. Quem consome (N8N) escolhe o endpoint conforme o caso.

**Motivo**:
- `/runsync` é o caminho natural pra textos curtos (até ~30s de áudio): uma única chamada HTTP no nó HTTP Request do N8N e o áudio volta na resposta.
- `/runsync` tem timeout de conexão (~30s no RunPod). Textos longos estouram.
- `/run` + polling em `/status/{id}` (ou webhook) cobre textos longos. No N8N, isso é um nó HTTP inicial + um sub-workflow / loop com Wait + HTTP até `status === "COMPLETED"`.

## Por que mockar `kokoro` e `torch` nos testes?

**Decisão**: `tests/conftest.py` injeta `MagicMock` em `sys.modules` antes de importar `handler`.

**Motivo**:
- `torch` em macOS arm64 são ~200 MB. `kokoro` puxa `transformers`, `huggingface_hub` etc. — install pesado.
- Os testes validam a lógica do handler (parsing de input, encoding, geração da resposta), não o modelo em si.
- Evita instalar `espeak-ng` no host pra rodar testes.
- CI roda em Python 3.11 e completa em segundos.

**Trade-off**: bug que só aparece com `kokoro` real (ex.: assinatura mudada de `KPipeline.__call__`) só é pego em integração. Mitigado pela própria build do Docker, que importa `kokoro` de verdade.

## Por que GitHub Integration em vez de RunPod Hub?

**Decisão**: deploy via Custom Source → GitHub Repository.

**Motivo**:
- Hub é mais voltado a publicar templates reutilizáveis pra outros usuários.
- GitHub Integration faz auto-build a cada push em `main`.
- Sem esforço extra pra publicar (e sem versão "pública" que não queremos).
