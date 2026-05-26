# Changelog

All notable changes to MDDataNet will be documented here.

MDDataNet follows semantic versioning for the Python package and CLI.

## 0.1.0 - Unreleased

### Added

- Hugging Face-native CLI surface with `init`, `inspect`, `prepare`, `analyze`,
  `tag`, `package`, `validate`, `publish`, `load`, `benchmark`, `demo`, and
  preset inspection commands.
- Local HF workspaces with `mddatanet.yaml`, `.mddn_cache/mddatanet.json`,
  per-frame Parquet data shards, validation reports, and dataset cards.
- Required Ray-backed prepare path for frame-range worker sharding.
- Solvent stripping by default with `--keep-solvent` and `--atom-selection`
  overrides.
- Nullable force tensor handling for trajectories without source force vectors.
- Frame-aligned preset metrics and custom Python metric scripts.
- Hugging Face split materialization with `train`, `validation`, `test`, and
  `metadata_index` Parquet files.
- Local upload preview through `publish --dry-run-out`.
- Dataset card generation with Hugging Face YAML front matter.
- Runtime-generated ligand unbinding demo.

### Changed

- MDDataNet is now Hugging Face-native. The custom metadata registry,
  `.mddatanet.zip` archive workflow, local manifest export, and standalone split
  command are retired from the public CLI.

### Notes

- SLURM/PBS script generation and async multipart upload optimization remain
  future work.
