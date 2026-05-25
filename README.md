# MDDataNet

MDDataNet converts molecular dynamics simulations into standardized, labeled,
machine-learning-ready dataset packages.

It reads MDAnalysis-compatible topology and trajectory files, stores standardized
trajectory/topology data in chunked Zarr, applies reproducible event rules or
presets, creates future-event labels and train/validation/test splits, validates
the result, and writes a shareable `.mddatanet.zip` package.

The CLI is useful locally today. The future MDDataNet Hub will be a separate
metadata registry for discovering validated packages.

## Install

```bash
python -m pip install -e ".[dev]"
```

If your environment does not have `pip`, install it first with:

```bash
python -m ensurepip --upgrade
```

## Five-Minute Demo

```bash
mddatanet demo
mddatanet inspect outputs/ligand_unbinding_demo.mddatanet.zip --labels
mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip
```

The demo generates a tiny synthetic protein-ligand trajectory at runtime. It
does not commit example datasets or config templates to the repo.

Python loader smoke test:

```python
from mddatanet import MDDataNetDataset

ds = MDDataNetDataset(
    "outputs/ligand_unbinding_demo.mddatanet.zip",
    window_length=2,
    target="ligand_unbinding_future_2",
)

item = ds[0]
print(item["coordinates"].shape)
print(item["label"], item["valid"])
```

## Common Workflow

```bash
mddatanet convert \
  --topology system.psf \
  --coordinates system.pdb \
  --trajectory run.dcd \
  --name kinase_ligand_run1 \
  --system-type protein_ligand \
  --out kinase_raw.mddatanet

mddatanet analyze \
  --input kinase_raw.mddatanet \
  --preset ligand_unbinding \
  --ligand "resname LIG" \
  --pocket "protein" \
  --param distance_threshold=15.0 \
  --param horizon_frames=500 \
  --out kinase_labeled.mddatanet

mddatanet split \
  --input kinase_labeled.mddatanet \
  --strategy temporal \
  --gap 100 \
  --out kinase_ready.mddatanet.zip

mddatanet validate kinase_ready.mddatanet.zip
mddatanet inspect kinase_ready.mddatanet.zip --features --labels --splits
```

For huge active work, prefer unpacked `.mddatanet/` directories. Use
`.mddatanet.zip` for sharing, archiving, and Hub manifest export.

By default, `convert` writes `hybrid + compressed` packages: coordinates are
stored under `dataset.zarr/trajectory/positions` as chunked, compressed
`float32` arrays. Use `--storage-profile linked` with coordinate URLs and
checksums for huge Hub-scale packages where coordinates live outside the
`.mddatanet.zip`.

## Hub Registry Export

`mddatanet export-manifest` now writes a Hub-ready registry folder that can be
copied into `mddn-hub/datasets/<dataset_name>/`:

```bash
mddatanet export-manifest kinase_ready.mddatanet.zip \
  --out kinase_ligand_unbinding_v1
```

The folder contains Hub-schema `metadata.json`, `manifest.json`,
`download.yaml`, `checksums.json`, `dataset_card.md`, and label/metric files
when available. If `--download-url` is omitted, the exporter writes a
schema-valid placeholder URL so the folder can pass Hub validation before the
real external storage URL is known.

## Documentation

- [Quickstart](docs/quickstart.md)
- [Current CLI status](docs/current_cli_status.md)
- [Command reference](docs/command_reference.md)
- [Feature YAML reference](docs/feature_yaml_reference.md)
- [Event YAML reference](docs/event_yaml_reference.md)
- [Preset guide](docs/preset_guide.md)
- [Package format](docs/package_format.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Example workflows](docs/workflows.md)
- [Versioning and releases](docs/versioning.md)
- [Full build specification](docs/MDDataNet_CLI_Full_Build_Specification.md)

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests
python -m build
```

MDDataNet is not an MD simulation engine and does not run NAMD, GROMACS, AMBER,
OpenMM, or WESTPA. It standardizes reproducible operational labels for ML tasks;
those labels should not be treated as universal biological truth.
