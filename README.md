# MDDataNet

MDDataNet converts molecular dynamics simulations into standardized, labeled,
machine-learning-ready dataset packages.

It reads MDAnalysis-compatible topology and trajectory files, computes trajectory
features, applies reproducible event rules or presets, creates future-event
labels and train/validation/test splits, validates the result, and writes a
shareable `.mddatanet.zip` package.

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

## Common Workflow

```bash
mddatanet convert \
  --topology system.psf \
  --coordinates system.pdb \
  --trajectory run.dcd \
  --name kinase_ligand_run1 \
  --system-type protein_ligand \
  --out kinase_raw.mddatanet

mddatanet label \
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

## Documentation

- [Quickstart](docs/quickstart.md)
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
