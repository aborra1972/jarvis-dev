# Wake-word training and promotion (gate 5.6)

Jarvis supports two wake-word backends:

1. **openWakeWord** (default): pretrained `hey_jarvis_v0.1.onnx` from the package.
2. **XLSR classifier** (gate 5.6): custom wav2vec2-XLSR + LogisticRegression
   trained on the operator's own voice for "jarvis" (single word, Argentine Spanish).

## How the detector picks a backend

`config.WAKE_ENGINE` selects the backend:

- `"openwakeword"` (default): uses the pretrained hey_jarvis model.
- `"xslr"`: uses the custom trained classifier at `spike/models/jarvis_wake.onnx`.

`jarvis.audio.wake.build_wake_detector()` is the factory that selects the backend.

## XLSR classifier (recommended)

The XLSR classifier recognizes **"jarvis"** (single word) with the operator's
Argentine Spanish pronunciation. It uses:

- **wav2vec2-large-xlsr-53** for feature extraction (1024-dim embeddings, max-pool)
- **LogisticRegression + StandardScaler** for classification
- **ONNX runtime** for lightweight inference (21KB model)

### Training

Training scripts are in `/tmp/opencode/train/` (separate venv required):

```bash
# 1. Record positive samples (say "jarvis" ~30 times)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py pos -n 30

# 2. Record negative samples (other phrases, noise ~20 times)
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/grabar_wake.py neg -n 20

# 3. Extract XLSR embeddings
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/extraer_xlsr.py

# 4. Train and evaluate classifier
/tmp/opencode/train-venv/bin/python /tmp/opencode/train/entrenar_clasificador.py --export-onnx
```

### Performance (current model)

- CV Estratificada: accuracy=98.0%, recall=96.7%, precision=100%, FP=0%
- Leave-One-Session-Out: accuracy=98.3%, recall=96.7%, precision=100%, FP=0%
- Latency: ~350ms per 2s window on CPU

### Deployment

1. Copy `clasificador.onnx` to `spike/models/jarvis_wake.onnx`
2. Set `WAKE_ENGINE = "xslr"` in `config.py`
3. No code changes needed — the factory handles backend selection

## openWakeWord (legacy)

The original openWakeWord detector uses the pretrained `hey_jarvis_v0.1.onnx`.
To use it, set `WAKE_ENGINE = "openwakeword"` in config.py.

### Training a custom openWakeWord model

openWakeWord models are trained with the upstream toolkit; the steps below
the ones that map onto this project:

1. **Record utterances.** Capture 5–10s of the operator saying *"hey jarvis"*
   at 16 kHz mono (the same format the mic pipeline uses). A few dozen
   positive samples improve robustness; no negative samples are needed for the
   per-word binary training.
2. **Train the ONNX.** Use the openWakeWord training scripts
   (https://github.com/dscripka/openWakeWord) to produce a
   `hey_jarvis_v0.1.onnx`-compatible file, exported with the same input/output
   contract (input: 16 kHz audio, output: per-frame model score).
3. **Place and configure.** Save it under `spike/models/jarvis.onnx` and set:

   ```python
   WAKE_CUSTOM_MODEL = SPIKE / "models" / "jarvis.onnx"
   ```

   The detector re-resolves on every start, so no rebuild is required.

## Validation

- With `WAKE_ENGINE = "xslr"`, verify `config.WAKE_XLSR_MODEL.is_file()` is true.
- Run the loop (`jarvis start`) and verify the wake word triggers on "jarvis".
- Tune `WAKE_THRESHOLD` (0.5 default) if it over- or under-triggers.

## Status

- XLSR classifier: **ACTIVE** (`WAKE_ENGINE = "xslr"`)
- openWakeWord: available as fallback (`WAKE_ENGINE = "openwakeword"`)
