# MDDataNet

MDDataNet CLI converts molecular dynamics simulations into standardized,
labeled, machine-learning-ready dataset packages.

The CLI reads raw topology and trajectory files, extracts trajectory-derived
features, applies reproducible event definitions, generates current-event and
future-event labels, creates train/validation/test splits, tracks provenance,
and packages everything into a `.mddatanet.zip` file.

This repository is in an early local-CLI build phase. The current implementation
can convert small/medium MDAnalysis-readable trajectories into MDDataNet
packages, compute YAML-defined trajectory features, generate event labels,
create splits, validate packages, inspect packages, and pack/unpack archives.

Example datasets, user config templates, and bundled demo assets are
intentionally deferred. The demo generates tiny synthetic data at runtime.

## Quickstart

```bash
python -m pip install -e ".[dev]"
mddatanet demo
mddatanet inspect outputs/ligand_unbinding_demo.mddatanet.zip
```

The demo creates a small synthetic protein-ligand trajectory, applies the
`ligand_unbinding` preset, generates future-event labels, creates splits,
validates the package, and writes:

```text
outputs/ligand_unbinding_demo.mddatanet.zip
```

## What MDDataNet Is Not

MDDataNet is not an MD simulation engine. It does not run NAMD, GROMACS, AMBER,
OpenMM, or WESTPA. It does not host public datasets yet, train universal ML
models, manually annotate events, or replace MDAnalysis, MDTraj, MDDB, MDRepo,
ATLAS, or mdCATH.

It sits above trajectory readers and below the future MDDataNet Hub.

## Intended CLI

```bash
mddatanet convert --topology system.psf --coordinates system.pdb --trajectory run.dcd --name kinase_ligand_run1 --out kinase_ligand_run1.mddatanet.zip
mddatanet featurize --input kinase_ligand_run1.mddatanet.zip --features features.yaml --out kinase_ligand_features.mddatanet.zip
mddatanet label --input kinase_ligand_run1.mddatanet.zip --preset ligand_unbinding --ligand "resname LIG" --pocket "protein" --param distance_threshold=15.0 --param horizon_frames=500 --out kinase_ligand_labeled.mddatanet.zip
mddatanet split --input kinase_ligand_labeled.mddatanet.zip --strategy temporal --gap 100 --out kinase_ligand_ready.mddatanet.zip
mddatanet validate kinase_ligand_ready.mddatanet.zip
mddatanet inspect kinase_ligand_ready.mddatanet.zip
mddatanet export-manifest kinase_ligand_ready.mddatanet.zip --out hub/kinase_ligand_ready
```

Multiple replicate trajectories can be packaged together with repeated
`--trajectory` and `--run-id` options:

```bash
mddatanet convert --topology system.psf --trajectory run1.dcd --trajectory run2.dcd --run-id run1 --run-id run2 --name kinase_replicates --out kinase_replicates.mddatanet.zip
```

## Package Format

An unpacked package is a `.mddatanet/` directory containing:

```text
dataset.zarr/
metadata.json
provenance.json
checksums.json
dataset_card.md
README.md
LICENSE
```

The Zarr store uses these root groups:

```text
arrays/
features/
labels/
splits/
index/
```

Large arrays should always be written incrementally with explicit chunking and
compression. Raw positions are optional and should not be stored unless the user
requests them.

For very large trajectories, prefer working with unpacked `.mddatanet/`
directories during active processing and create `.mddatanet.zip` archives when
you are ready to share or export.

## Hub Registry Workflow

The future MDDataNet Hub should be a curated metadata registry, not a raw file
dump. Use:

```bash
mddatanet export-manifest my_dataset.mddatanet.zip --out hub_dataset_dir
```

This writes Hub-ready `metadata.json`, `dataset_card.md`, `checksums.json`,
`manifest.json`, and `download.yaml`. The large `.mddatanet.zip` should live on
Hugging Face Datasets, Zenodo, S3/R2, GCS, or institutional storage.

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

The source of truth for the full build is
`docs/MDDataNet_CLI_Full_Build_Specification.md`.
