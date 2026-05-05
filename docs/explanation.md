# Sobre o Kokoro TTS

## O que é Kokoro

[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) é um modelo open-source de Text-to-Speech (síntese de voz) com **82 milhões de parâmetros** lançado em 2024 pelo grupo `hexgrad`. Apesar do tamanho enxuto, alcança qualidade comparável a modelos 10x maiores em benchmarks subjetivos (TTS Arena).

Características:

- **Tamanho**: ~330 MB de pesos (FP32). Cabe em qualquer GPU com >1 GB de VRAM.
- **Sample rate**: 24 kHz (suficiente pra voz humana).
- **Multilíngue**: ~30 idiomas suportados via `misaki` (phonemizer com regras por idioma).
- **Vozes**: pacote de "voicepacks" embutidos — não precisa de áudio de referência (não é zero-shot voice cloning, é seleção de voz pré-treinada).
- **Licença**: Apache 2.0.

## Pipeline interno

Quando você chama `pipeline(text, voice="pf_dora", speed=1.0)`:

1. **Tokenização**: o texto é dividido em sentenças.
2. **Phonemization**: cada sentença vai para o `misaki` (no PT-BR, usa um conjunto de regras + dicionário). Saída: sequência de fonemas IPA.
3. **Modelo**: o transformer 82M consome (fonemas + voicepack) e gera espectrogramas mel.
4. **Vocoder**: HiFi-GAN-style decoder converte mel → waveform 24 kHz.
5. O `pipeline` é um **generator**: yielda `(graphemes, phonemes, audio)` por chunk (~uma sentença por iteração).

Por isso o handler concatena os chunks com `np.concatenate` antes de codificar.

## Vozes PT-BR

| Voice ID    | Gênero    | Características                              |
| ----------- | --------- | -------------------------------------------- |
| `pf_dora`   | Feminina  | Tom geral, timbre claro. Default do worker.  |
| `pm_alex`   | Masculina | Tom neutro / locução técnica.                |
| `pm_santa`  | Masculina | Tom mais quente, festivo (originalmente persona "Papai Noel"). |

A convenção de nomes: `<lang_prefix><gender>_<name>`. `p` = português, `f`/`m` = female/male.

## Outros idiomas (referência)

Tecnicamente suportados pela lib (mas não pré-aquecidos neste worker):

- `a` — American English (ex.: `af_heart`, `am_michael`)
- `b` — British English (ex.: `bf_emma`, `bm_george`)
- `j` — Japanese (ex.: `jf_alpha`)
- `z` — Mandarin Chinese
- `e` — Spanish
- `f` — French
- `h` — Hindi
- `i` — Italian

Veja a lista completa no [HuggingFace card](https://huggingface.co/hexgrad/Kokoro-82M).

## Limites conhecidos

- **Texto longo**: o `pipeline` processa frase por frase, mas textos muito longos (>1000 palavras) consomem memória progressivamente. Para textos longos, considere chunking no cliente.
- **Pronúncia de nomes próprios**: depende do dicionário do `misaki`. Nomes raros podem ser pronunciados com sotaque estranho. Workaround: usar fonemas IPA explícitos no texto.
- **Velocidade (`speed`)**: aceita `0.5–2.0`. Fora dessa faixa o áudio degrada.
- **Não é voice cloning**: você não pode fornecer um áudio de referência pra clonar uma voz. Use uma voz pré-existente.

## Referências

- Modelo: https://huggingface.co/hexgrad/Kokoro-82M
- Lib Python: https://pypi.org/project/kokoro/
- Phonemizer: https://github.com/hexgrad/misaki
- TTS Arena (avaliação subjetiva): https://huggingface.co/spaces/Pendrokar/TTS-Spaces-Arena
