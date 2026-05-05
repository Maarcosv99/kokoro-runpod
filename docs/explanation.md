# About Kokoro TTS

## What Kokoro is

[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) is an open-source Text-to-Speech model with **82 million parameters** released in 2024 by the `hexgrad` group. Despite the small footprint, it reaches quality on par with models 10× larger on subjective benchmarks (TTS Arena).

Highlights:

- **Size**: ~330 MB of weights (FP32). Fits on any GPU with >1 GB of VRAM.
- **Sample rate**: 24 kHz (plenty for human voice).
- **Multilingual**: ~30 languages supported via `misaki` (a per-language phonemizer).
- **Voices**: bundled "voicepacks" — no reference audio required (this is not zero-shot voice cloning, it's pre-trained voice selection).
- **License**: Apache 2.0.

## Internal pipeline

When you call `pipeline(text, voice="pf_dora", speed=1.0)`:

1. **Tokenization**: the text is split into sentences.
2. **Phonemization**: each sentence goes through `misaki` (for PT-BR, a rule set + dictionary). Output: an IPA phoneme sequence.
3. **Model**: the 82M transformer consumes (phonemes + voicepack) and produces mel spectrograms.
4. **Vocoder**: a HiFi-GAN-style decoder turns mel into a 24 kHz waveform.
5. The `pipeline` is a **generator**: it yields `(graphemes, phonemes, audio)` per chunk (~one sentence per iteration).

That's why the handler concatenates chunks with `np.concatenate` before encoding.

## PT-BR voices

| Voice ID    | Gender | Characteristics                                   |
| ----------- | ------ | ------------------------------------------------- |
| `pf_dora`   | Female | General-purpose tone, clear timbre. Worker default. |
| `pm_alex`   | Male   | Neutral tone, suited for technical narration.     |
| `pm_santa`  | Male   | Warmer, festive tone (originally a Santa persona).|

Naming convention: `<lang_prefix><gender>_<name>`. `p` = Portuguese, `f`/`m` = female/male.

## Other languages (reference)

Technically supported by the library (but not pre-warmed in this worker):

- `a` — American English (e.g. `af_heart`, `am_michael`)
- `b` — British English (e.g. `bf_emma`, `bm_george`)
- `j` — Japanese (e.g. `jf_alpha`)
- `z` — Mandarin Chinese
- `e` — Spanish
- `f` — French
- `h` — Hindi
- `i` — Italian

See the full list on the [HuggingFace card](https://huggingface.co/hexgrad/Kokoro-82M).

## Known limits

- **Long text**: the `pipeline` processes sentence by sentence, but very long inputs (>1000 words) accumulate memory. For long texts, consider chunking on the consumer side.
- **Proper-noun pronunciation**: depends on the `misaki` dictionary. Rare names may come out with an odd accent. Workaround: use explicit IPA phonemes in the text.
- **Speed (`speed`)**: accepts `0.5–2.0`. Outside that range the audio degrades.
- **Not voice cloning**: you can't supply a reference audio to clone a voice. Use one of the pre-trained voices.

## References

- Model: https://huggingface.co/hexgrad/Kokoro-82M
- Python lib: https://pypi.org/project/kokoro/
- Phonemizer: https://github.com/hexgrad/misaki
- TTS Arena (subjective evaluation): https://huggingface.co/spaces/Pendrokar/TTS-Spaces-Arena
