# Versioning And Releases

MDDataNet uses semantic versioning for the CLI and Python package.

## Version Policy

- Patch releases fix bugs, improve docs, or improve error messages.
- Minor releases add commands, features, presets, metadata fields, or compatible
  schema additions.
- Major releases are reserved for incompatible package format or schema changes.

The package format version is tracked separately in `metadata.json`.

## Release Checklist

Before a release:

```bash
python -m pytest
python -m ruff check src tests
python -m build
mddatanet demo
mddatanet validate outputs/ligand_unbinding_demo.mddatanet.zip
```

Then:

1. Update `CHANGELOG.md`.
2. Confirm `pyproject.toml` version and metadata.
3. Tag the release.
4. Run the manual TestPyPI workflow.
5. Install from TestPyPI in a clean environment.
6. Publish to PyPI only after the TestPyPI package works.

PyPI publication should stay manual until the schema and API are stable.
