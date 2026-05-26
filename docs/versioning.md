# Versioning And Releases

MDDataNet uses semantic versioning for the CLI and Python package.

- Patch releases: bug fixes and docs.
- Minor releases: new commands, metrics, presets, or HF export options.
- Major releases: incompatible CLI or Hugging Face schema changes.

The 0.1.0 line is pre-release and may still change quickly while the HF-native
schema stabilizes.

## Release Checklist

```bash
python -m pytest
python -m ruff check src tests
python -m build
mddatanet demo
mddatanet publish outputs/ligand_unbinding_demo_hf \
  --repo-id USER/ligand-unbinding-demo \
  --dry-run-out /tmp/mddatanet_demo_parquet
```

Then update `CHANGELOG.md`, tag the release, publish to TestPyPI, and only move
to PyPI once the HF schema is stable.
