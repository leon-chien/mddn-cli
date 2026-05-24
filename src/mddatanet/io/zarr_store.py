"""Zarr store creation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mddatanet.utils.errors import DependencyError

REQUIRED_ROOT_GROUPS = ("arrays", "features", "labels", "splits", "index")
DEFAULT_1D_CHUNK = 65_536
DEFAULT_POSITION_FRAME_CHUNK = 64


def _zarr_module():
    try:
        import zarr
    except Exception as exc:  # pragma: no cover - depends on local env
        raise DependencyError("zarr", purpose="package array storage") from exc
    return zarr


def _default_compressor() -> Any:
    try:
        from numcodecs import Blosc
    except Exception:  # pragma: no cover - zarr can still write uncompressed arrays
        return None
    return Blosc(cname="zstd", clevel=3, shuffle=Blosc.SHUFFLE)


def open_zarr_group(path: str | Path, *, mode: str = "a") -> Any:
    zarr = _zarr_module()
    try:
        return zarr.open_group(str(path), mode=mode, zarr_format=2)
    except TypeError:  # zarr<3 does not accept zarr_format
        return zarr.open_group(str(path), mode=mode)


def create_zarr_store(path: str | Path, *, overwrite: bool = False) -> Any:
    path = Path(path)
    mode = "w" if overwrite else "a"
    root = open_zarr_group(path, mode=mode)
    for group_name in REQUIRED_ROOT_GROUPS:
        root.require_group(group_name)
    return root


def require_root_groups(root: Any) -> list[str]:
    missing: list[str] = []
    for group_name in REQUIRED_ROOT_GROUPS:
        if group_name not in root:
            missing.append(group_name)
    return missing


def create_array(
    group: Any,
    name: str,
    *,
    shape: tuple[int, ...],
    dtype: str,
    chunks: tuple[int, ...] | None = None,
    overwrite: bool = True,
) -> Any:
    """Create a chunked Zarr array with default compression."""

    kwargs: dict[str, Any] = {
        "shape": shape,
        "dtype": dtype,
        "chunks": chunks or _default_chunks(shape),
        "overwrite": overwrite,
    }
    compressor = _default_compressor()
    if compressor is not None:
        kwargs["compressor"] = compressor
    if hasattr(group, "create_array"):
        return group.create_array(name, **kwargs)
    return group.create_dataset(name, **kwargs)


def create_string_array(
    group: Any,
    name: str,
    values: list[str] | tuple[str, ...],
    *,
    overwrite: bool = True,
) -> Any:
    """Create a chunked fixed-width unicode string array.

    Zarr v2 variable-length strings have API differences across recent Zarr
    releases, so package metadata arrays use fixed-width unicode sized to the
    values being written.
    """

    max_len = max((len(str(value)) for value in values), default=1)
    array = create_array(
        group,
        name,
        shape=(len(values),),
        dtype=f"<U{max_len}",
        chunks=(min(max(len(values), 1), DEFAULT_1D_CHUNK),),
        overwrite=overwrite,
    )
    if values:
        array[:] = [str(value) for value in values]
    return array


def create_numeric_vector(
    group: Any,
    name: str,
    values: Any,
    *,
    dtype: str,
    overwrite: bool = True,
) -> Any:
    length = len(values)
    array = create_array(
        group,
        name,
        shape=(length,),
        dtype=dtype,
        chunks=(min(max(length, 1), DEFAULT_1D_CHUNK),),
        overwrite=overwrite,
    )
    if length:
        array[:] = values
    return array


def write_index_names(root: Any, *, feature_names: list[str] | None = None, event_names: list[str] | None = None) -> None:
    index = root["index"]
    if feature_names is not None:
        create_string_array(index, "feature_names", feature_names, overwrite=True)
    if event_names is not None:
        create_string_array(index, "event_names", event_names, overwrite=True)


def _default_chunks(shape: tuple[int, ...]) -> tuple[int, ...]:
    if not shape:
        return shape
    if len(shape) == 1:
        return (min(max(shape[0], 1), DEFAULT_1D_CHUNK),)
    frame_chunk = min(max(shape[0], 1), DEFAULT_POSITION_FRAME_CHUNK)
    return (frame_chunk, *shape[1:])
