# Command Reference

## `mddatanet convert`

Create an initial package from raw MD files.

Required:

- `--topology`: topology file such as PDB, PSF, PRMTOP, or GRO.
- `--name`: dataset name.
- `--out`: output `.mddatanet/` directory or `.mddatanet.zip`.

Common options:

- `--coordinates`: coordinate file when topology has no coordinates.
- `--trajectory`: trajectory file; repeat for multiple runs.
- `--run-id`: run identifier; repeat once for each trajectory.
- `--trajectory-id`: trajectory identifier; repeat once for each trajectory.
- `--start`, `--stop`, `--stride`: frame slicing.
- `--chunk-size`: processing frame chunk size.
- `--data-mode`: `hybrid`, `trajectory`, or `features-only`; default `hybrid`.
- `--storage-profile`: `compressed`, `full`, or `linked`; default `compressed`.
- `--no-coordinates`: omit embedded coordinates.
- `--coordinate-dtype`: `float32` or `float64`.
- `--compression`: `zstd`, `blosc-zstd`, or `none`.
- `--chunk-frames`, `--chunk-atoms`: coordinate chunking controls.
- `--coordinate-precision`: optional coordinate rounding precision in Angstrom.
- `--coordinates-url`, `--coordinates-sha256`: required for linked coordinate packages.
- `--topology-url`, `--topology-sha256`: optional linked topology metadata.
- `--system-type`, `--simulation-engine`, `--force-field`, `--solvent`,
  `--ensemble`, `--organism`, `--protein`: metadata tags.

Default conversion writes `dataset.zarr/trajectory/positions` and
`dataset.zarr/topology/*`. Use `--storage-profile linked` for huge packages
whose coordinates live in external storage.

## `mddatanet featurize`

Add feature arrays from a feature YAML file.

```bash
mddatanet featurize --input raw.mddatanet --features features.yaml --out features.mddatanet
```

Features are written to `dataset.zarr/features/{feature_name}`.

## `mddatanet label`

Generate event labels from custom events or a preset.

Preset:

```bash
mddatanet label --input raw.mddatanet --preset ligand_unbinding --ligand "resname LIG" --pocket "protein" --out labeled.mddatanet
```

Custom YAML:

```bash
mddatanet label --input features.mddatanet --events events.yaml --out labeled.mddatanet
```

Labels are written under `dataset.zarr/labels/{event_name}`.

## `mddatanet analyze`

Run a preset-driven analysis in one step. This is the recommended high-level
workflow for built-in or user-defined presets.

```bash
mddatanet analyze --input raw.mddatanet --preset ligand_unbinding --ligand "resname LIG" --pocket protein --out labeled.mddatanet
mddatanet analyze --input raw.mddatanet --preset-yaml my_preset.yaml --param selection_a="segid A" --param selection_b="segid B" --out labeled.mddatanet
```

`analyze` resolves the preset, computes missing features, writes labels,
updates metadata/cards/checksums, and records resolved configs.

## `mddatanet split`

Create split arrays.

```bash
mddatanet split --input labeled.mddatanet --strategy temporal --gap 100 --out ready.mddatanet
```

Strategies:

- `temporal`: ordered train/validation/test split.
- `random_window`: random frame/window split with gap handling.
- `trajectory`: split by run ID for multi-run packages.

## `mddatanet validate`

Validate structure, schemas, checksums, array lengths, label semantics, runs,
and splits.

```bash
mddatanet validate ready.mddatanet.zip
```

Use `--no-checksums` while debugging intentionally modified packages.

## `mddatanet inspect`

Print a human-readable or JSON summary.

```bash
mddatanet inspect ready.mddatanet.zip --features --labels --splits
mddatanet inspect ready.mddatanet.zip --json
```

## Package Utilities

- `mddatanet pack source.mddatanet output.mddatanet.zip`
- `mddatanet unpack input.mddatanet.zip --out unpacked/`
- `mddatanet card --input ready.mddatanet --out ready_with_card.mddatanet`
- `mddatanet export-schema --out-dir schemas`
- `mddatanet split-package --input ready.mddatanet.zip --out-labels dataset.labels.mddatanet.zip --out-coordinates dataset.coordinates.zarr.zip`

## Demo And Presets

- `mddatanet demo`
- `mddatanet demo ligand_unbinding`
- `mddatanet presets list`
- `mddatanet presets show ligand_unbinding`
- `mddatanet presets explain ligand_unbinding`
- `mddatanet presets validate-yaml my_preset.yaml`

## Hub Manifest Export

Export small metadata files for the future Hub registry:

```bash
mddatanet export-manifest ready.mddatanet.zip --out hub_dataset_dir
```

The exported folder is shaped for `mddn-hub/datasets/<dataset_name>/` and
contains Hub-schema files: `metadata.json`, `manifest.json`, `download.yaml`,
`checksums.json`, `dataset_card.md`, `label_statistics.json`, and
`baseline_metrics.json` when metrics exist. `citation.bib` is included only
when citation metadata is present.

Add `--download-url` after uploading the large package to external storage.
Use `--verify-download` only when the URL is reachable and should be checked.
