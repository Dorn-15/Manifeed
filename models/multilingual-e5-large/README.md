Required ONNX artifacts for `worker-source-embedding`:

- `model.onnx`
- `tokenizer.json`
- `config.json`

Optional companion files often shipped with the tokenizer/model export:

- `tokenizer_config.json`
- `special_tokens_map.json`

The Rust worker reads this directory from the `MODEL_DIR` constant inside [workers-rust/worker-source-embedding/src/config.rs](/home/dorn/Projects/Manifeed/workers-rust/worker-source-embedding/src/config.rs).

Populate it with:

```bash
make download-embedding-model
```
