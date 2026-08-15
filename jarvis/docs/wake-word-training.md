# Wake-word training and promotion (gate 5.6)

Jarvis wakes on **hey jarvis** using a pre-trained openWakeWord model that ships
with the package (`hey_jarvis_v0.1.onnx`). Gate 5.6 promotes a **custom
`jarvis.onnx`** so the wake word can be retrained for the operator's own voice
and phrase.

## How the detector picks a model

`jarvis.audio.wake.build_model_paths` resolves in this order:

1. An explicit `model_paths` list, if provided.
2. `config.WAKE_CUSTOM_MODEL`, if set **and** the file exists.
3. The packaged `hey_jarvis_v0.1.onnx` from `openwakeword.resources`.

So a trained model takes precedence with **zero code changes**: drop it at a
known path and point `WAKE_CUSTOM_MODEL` at it in `config.py`.

## Training a custom model

openWakeWord models are trained with the upstream toolkit; the steps below are
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

- With the model in place, `config.WAKE_CUSTOM_MODEL.is_file()` is true and
  `build_model_paths(None, custom=WAKE_CUSTOM_MODEL)` returns `[jarvis.onnx]`.
- Run the loop (`jarvis start`) and verify the wake word triggers only on the
  intended phrase; tune `WAKE_THRESHOLD` (0.5 default) if it over- or
  under-triggers.

## Status

Training the custom model is environment/operator work and is **not** part of
this slice. The config hook and precedence are implemented and unit-tested; the
packaged `hey_jarvis_v0.1.onnx` remains the active detector until a trained
model is provided.
