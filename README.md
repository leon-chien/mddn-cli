# MDDataNet

MDDataNet converts molecular dynamics simulations into standardized, labeled,
machine-learning-ready dataset packages.

It reads MDAnalysis-compatible topology and trajectory files, stores standardized
trajectory/topology data in chunked Zarr, applies reproducible event rules or
presets, creates future-event labels and train/validation/test splits, validates
the result, and writes a shareable `.mddatanet.zip` package.

The CLI is the package-building side of the MDDataNet ecosystem. The
[MDDataNet Hub](https://github.com/leon-chien/mddn-hub) is the metadata
registry for discovering validated packages: the CLI creates `.mddatanet.zip`
archives, users upload those archives to external storage, the Hub stores
metadata and download links, and downstream users download packages to train
with `MDDataNetDataset`.

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

`mddatanet export-manifest` writes a Hub-ready registry folder that can be
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

The intended handoff is:

1. Use this CLI to create and validate a `.mddatanet.zip` package.
2. Upload the package to external storage such as Hugging Face Datasets, Zenodo,
   S3/R2, GCS, or institutional storage.
3. Run `mddatanet export-manifest` with the package URL or replace the
   placeholder URL in `download.yaml`.
4. Submit the metadata folder to the
   [MDDataNet Hub](https://github.com/leon-chien/mddn-hub).
5. Users read the Hub metadata, download and verify the package, then train with
   `MDDataNetDataset`.

The Hub stores metadata, download links, checksums, dataset cards, and benchmark
semantics. It does not host large trajectories or `.mddatanet.zip` archives.

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
