# Current CLI Status

MDDataNet is currently a Hugging Face-native workspace CLI.

Working commands:

- `init`
- `inspect`
- `prepare`
- `analyze`
- `tag`
- `package`
- `validate`
- `publish`
- `load`
- `benchmark`
- `demo`
- `presets list/show/explain/validate-yaml`

The current implementation can:

- initialize `mddatanet.yaml`;
- inspect MDAnalysis-readable source files;
- prepare per-frame Parquet shards through Ray-backed worker logic;
- strip solvent by default;
- preserve coordinates and null force tensors when forces are unavailable;
- compute basic frame-aligned metrics and ligand-binding/unbinding style event
  labels;
- manually tag allowed event intervals;
- generate train/validation/test Parquet files and a lightweight
  `metadata_index`;
- validate schema and frame coverage;
- publish to Hugging Face or run a local dry-run upload preview.

Removed from the public product:

- `.mddatanet.zip` final archives;
- custom `mddn-hub` manifest export;
- public `convert`, `push-to-hub`, `split`, `pack`, `unpack`, and
  `export-manifest` commands.
