# Quickstart

## Install

From a checked-out repo:

```bash
python -m pip install -e ".[dev]"
```

If `python -m pip` fails with `No module named pip`, run:

```bash
python -m ensurepip --upgrade
python -m pip install -e ".[dev]"
```

## Run The Demo

```bash
mddatanet demo
```

The demo creates a tiny synthetic protein-ligand trajectory at runtime, converts
it into an MDDataNet package, applies the `ligand_unbinding` preset, creates
splits, validates the result, and writes:

```text
outputs/ligand_unbinding_demo.mddatanet.zip
```

Inspect and validate it:

```bash
mddatanet inspect outputs/ligand_unbinding_demo.mddatanet.zip --labels --splits
mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip
```

## Convert Your Own Data

```bash
mddatanet convert \
  --topology system.pdb \
  --trajectory traj.xtc \
  --name my_run \
  --out my_run.mddatanet
```

For PSF-style workflows:

```bash
mddatanet convert \
  --topology system.psf \
  --coordinates system.pdb \
  --trajectory traj.dcd \
  --name my_run \
  --out my_run.mddatanet
```

Use unpacked `.mddatanet/` directories while processing large trajectories.
Create `.mddatanet.zip` archives when sharing or exporting manifests.
