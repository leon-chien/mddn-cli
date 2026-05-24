# Troubleshooting

## `No module named pip`

Your Python environment does not have `pip`.

```bash
python -m ensurepip --upgrade
python -m pip install -e ".[dev]"
```

In Conda environments, `conda install pip` is also fine.

## Invalid Selection

Example:

```text
selection 'resid 42 and name CA' matched 0 atoms
```

Check that the topology contains the residue/atom names you expect. MDDataNet
uses MDAnalysis selection syntax.

## Topology And Trajectory Mismatch

If conversion fails because atom counts do not match, confirm that all
trajectories share the same topology and atom ordering. Multi-run packages
currently require one compatible system.

## Missing Raw Files During Featurization

If `convert` did not use `--store-positions`, featurization reopens the original
raw files recorded in provenance. Restore those files or rerun:

```bash
mddatanet convert ... --store-positions
```

Storing positions can make packages large, so it is disabled by default.

## Units And PBC

MDDataNet records distances as Angstrom and times as picoseconds when available
through MDAnalysis. Periodic boundary behavior depends on unit-cell information
being present in the trajectory.

## Huge Files

Use unpacked `.mddatanet/` directories during active processing. Packing to zip
is best for sharing or archiving.

## Validation Fails After Manual Edits

Run:

```bash
mddatanet validate package.mddatanet --no-checksums
```

If validation then passes, regenerate checksums by rerunning the relevant
MDDataNet command or repacking the package.
