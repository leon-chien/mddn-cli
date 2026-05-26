"""Hugging Face and Arrow schemas for MDDataNet."""

from __future__ import annotations

from typing import Any

from mddatanet.utils.errors import DependencyError


def _datasets_module():
    try:
        import datasets
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("datasets", purpose="Hugging Face dataset export") from exc
    return datasets


def pyarrow_module() -> Any:
    try:
        import pyarrow as pa
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("pyarrow", purpose="Parquet dataset writing") from exc
    return pa


def heavy_tensor_schema() -> Any:
    """Return the canonical per-frame Parquet schema."""

    pa = pyarrow_module()
    coord_type = pa.list_(pa.list_(pa.float32()))
    return pa.schema(
        [
            ("frame_id", pa.int64()),
            ("time_ps", pa.float64()),
            ("coordinates", coord_type),
            ("forces", coord_type),
            ("rmsd", pa.float32()),
            ("radius_of_gyration", pa.float32()),
            ("event_label", pa.string()),
            ("event_confidence", pa.float32()),
        ]
    )


def metadata_index_schema() -> Any:
    """Return the lightweight search-index Parquet schema."""

    pa = pyarrow_module()
    return pa.schema(
        [
            ("dataset_name", pa.string()),
            ("protein_name", pa.string()),
            ("forcefield", pa.string()),
            ("max_rmsd", pa.float32()),
            ("min_radius_of_gyration", pa.float32()),
            ("tagged_events", pa.list_(pa.string())),
            ("hf_repo_link", pa.string()),
        ]
    )


def mddatanet_features() -> Any:
    """Return the canonical per-frame Hugging Face feature schema."""

    datasets = _datasets_module()
    return datasets.Features(
        {
            "frame_id": datasets.Value("int64"),
            "time_ps": datasets.Value("float64"),
            "coordinates": datasets.Array2D(shape=(None, 3), dtype="float32"),
            "forces": datasets.Array2D(shape=(None, 3), dtype="float32"),
            "rmsd": datasets.Value("float32"),
            "radius_of_gyration": datasets.Value("float32"),
            "event_label": datasets.Value("string"),
            "event_confidence": datasets.Value("float32"),
        }
    )


def metadata_index_features() -> Any:
    """Return the lightweight semantic index schema."""

    datasets = _datasets_module()
    return datasets.Features(
        {
            "dataset_name": datasets.Value("string"),
            "protein_name": datasets.Value("string"),
            "forcefield": datasets.Value("string"),
            "max_rmsd": datasets.Value("float32"),
            "min_radius_of_gyration": datasets.Value("float32"),
            "tagged_events": datasets.Sequence(datasets.Value("string")),
            "hf_repo_link": datasets.Value("string"),
        }
    )
