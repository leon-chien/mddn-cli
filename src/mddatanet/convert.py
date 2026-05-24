"""MDAnalysis-backed package conversion."""

from __future__ import annotations

import platform
import shutil
import sys
import time
import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from mddatanet import __version__
from mddatanet.format.dataset_card import write_dataset_card
from mddatanet.format.metadata import write_metadata
from mddatanet.format.provenance import write_provenance
from mddatanet.format.schema import (
    Metadata,
    Provenance,
    RunRecord,
    SimulationMetadata,
    SourceMetadata,
    SystemMetadata,
)
from mddatanet.io.checksums import write_checksums
from mddatanet.io.loaders import load_universe
from mddatanet.io.package import pack_package
from mddatanet.io.source import source_file_record
from mddatanet.io.zarr_store import (
    DEFAULT_POSITION_FRAME_CHUNK,
    create_array,
    create_string_array,
    create_zarr_store,
    write_index_names,
)
from mddatanet.utils.errors import PackageError
from mddatanet.utils.paths import ensure_can_write, is_package_zip, package_stem


@dataclass(frozen=True)
class _RunSpec:
    run_id: str
    trajectory: Path | None
    frame_range: range
    package_start: int
    package_stop: int
    atom_count: int
    reader: str | None
    format: str | None
    timestep_ps: float | None
    has_periodic_box: bool | None


def convert_package(
    *,
    topology: Path,
    trajectory: Path | Sequence[Path] | None,
    coordinates: Path | None,
    name: str,
    out: Path,
    description: str | None = None,
    license: str = "unknown",
    source_url: str | None = None,
    citation: str | None = None,
    run_id: Sequence[str] | None = None,
    simulation_engine: str | None = None,
    force_field: str | None = None,
    solvent: str | None = None,
    ensemble: str | None = None,
    organism: str | None = None,
    protein: str | None = None,
    system_type: str | None = None,
    stride: int = 1,
    start: int | None = None,
    stop: int | None = None,
    store_positions: bool = False,
    overwrite: bool = False,
    command: str | None = None,
) -> Path:
    """Convert raw MD files into an initial MDDataNet package."""

    started = time.perf_counter()
    if stride < 1:
        raise PackageError("stride must be >= 1")
    topology = Path(topology)
    trajectories = _normalize_trajectories(trajectory)
    run_ids = _resolve_run_ids(trajectories, run_id)
    coordinates = Path(coordinates) if coordinates is not None else None
    _validate_source_paths(topology=topology, coordinates=coordinates, trajectories=trajectories)

    run_specs = _build_run_specs(
        topology=topology,
        coordinates=coordinates,
        trajectories=trajectories,
        run_ids=run_ids,
        start=start,
        stop=stop,
        stride=stride,
    )
    total_frames = sum(len(spec.frame_range) for spec in run_specs)
    if total_frames == 0:
        raise PackageError("Frame slice selected zero frames.")

    first_universe = load_universe(topology, coordinates=coordinates, trajectory=run_specs[0].trajectory)
    first_ts = first_universe.trajectory[run_specs[0].frame_range.start]
    inferred_system_type = system_type or _infer_system_type(first_universe)
    ligand_present = _has_ligand_like_residue(first_universe)

    target_dir: Path
    tempdir: TemporaryDirectory[str] | None = None
    if is_package_zip(out):
        ensure_can_write(out, overwrite=overwrite)
        tempdir = TemporaryDirectory(prefix="mddatanet-convert-")
        target_dir = Path(tempdir.name) / f"{package_stem(out)}.mddatanet"
    else:
        target_dir = ensure_can_write(out, overwrite=overwrite)
    try:
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)
        zarr_root = create_zarr_store(target_dir / "dataset.zarr", overwrite=True)

        metadata = Metadata(
            mddatanet_version=__version__,
            dataset_name=name,
            description=description,
            system=SystemMetadata(
                system_type=inferred_system_type,
                num_atoms=int(first_universe.atoms.n_atoms),
                num_residues=int(first_universe.residues.n_residues),
                num_frames=total_frames,
                num_runs=len(run_specs),
                timestep_ps=_trajectory_dt(first_universe.trajectory),
                has_periodic_box=_has_periodic_box(first_ts),
                organism=organism,
                protein=protein,
                ligand_present=ligand_present,
            ),
            source=SourceMetadata(
                topology_file=str(topology),
                coordinates_file=str(coordinates) if coordinates is not None else None,
                trajectory_file=str(run_specs[0].trajectory) if run_specs[0].trajectory is not None else None,
                trajectory_files=[str(spec.trajectory) for spec in run_specs if spec.trajectory is not None],
                topology_format=topology.suffix.lower().lstrip(".") or None,
                coordinates_format=coordinates.suffix.lower().lstrip(".") if coordinates is not None else None,
                trajectory_format=run_specs[0].format,
                source_url=source_url,
                citation=citation,
            ),
            simulation=SimulationMetadata(
                engine=simulation_engine,
                force_field=force_field,
                solvent=solvent,
                ensemble=ensemble,
            ),
            license=license,
            tags=_metadata_tags(
                system_type=inferred_system_type,
                organism=organism,
                protein=protein,
                ligand_present=ligand_present,
                simulation_engine=simulation_engine,
                force_field=force_field,
                solvent=solvent,
                ensemble=ensemble,
                license=license,
            ),
        )
        source_files = [source_file_record(topology, role="topology")]
        if coordinates is not None:
            source_files.append(source_file_record(coordinates, role="coordinates"))
        for spec in run_specs:
            if spec.trajectory is not None:
                source_files.append(source_file_record(spec.trajectory, role="trajectory", run_id=spec.run_id))
        provenance = Provenance(
            mddatanet_version=__version__,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            platform=platform.platform(),
            commands=[command] if command else [],
            source_files=source_files,
            runs=[
                RunRecord(
                    run_id=spec.run_id,
                    trajectory_file=str(spec.trajectory) if spec.trajectory is not None else None,
                    trajectory_format=spec.format,
                    reader=spec.reader,
                    atom_count=spec.atom_count,
                    num_frames=len(spec.frame_range),
                    package_start=spec.package_start,
                    package_stop=spec.package_stop,
                    source_start=spec.frame_range.start,
                    source_stop=spec.frame_range.stop,
                    source_stride=spec.frame_range.step,
                    timestep_ps=spec.timestep_ps,
                    has_periodic_box=spec.has_periodic_box,
                )
                for spec in run_specs
            ],
            frame_start=start,
            frame_stop=stop,
            frame_stride=stride,
            stored_positions=store_positions,
        )

        _write_topology_arrays(zarr_root, first_universe)
        _write_frame_arrays(
            zarr_root,
            topology=topology,
            coordinates=coordinates,
            run_specs=run_specs,
            store_positions=store_positions,
        )
        write_index_names(zarr_root, feature_names=[], event_names=[])
        provenance.conversion_time_seconds = time.perf_counter() - started
        write_metadata(target_dir, metadata)
        write_provenance(target_dir, provenance)
        write_dataset_card(target_dir, metadata, provenance)
        (target_dir / "README.md").write_text(
            f"# {metadata.dataset_name}\n\nGenerated by MDDataNet.\n",
            encoding="utf-8",
        )
        (target_dir / "LICENSE").write_text(f"{metadata.license}\n", encoding="utf-8")
        write_checksums(target_dir)
        if is_package_zip(out):
            packed = pack_package(target_dir, out, overwrite=overwrite)
            return packed
        return target_dir
    finally:
        if tempdir is not None:
            tempdir.cleanup()


def _normalize_trajectories(trajectory: Path | Sequence[Path] | None) -> list[Path]:
    if trajectory is None:
        return []
    if isinstance(trajectory, (str, Path)):
        return [Path(trajectory)]
    return [Path(path) for path in trajectory]


def _resolve_run_ids(trajectories: list[Path], run_id: Sequence[str] | None) -> list[str]:
    if run_id is not None and len(run_id) != len(trajectories):
        raise PackageError(
            "--run-id count must match --trajectory count.",
            suggestion="Pass one --run-id for each --trajectory, or omit --run-id to derive IDs.",
        )
    if run_id is not None:
        if len(set(run_id)) != len(run_id):
            raise PackageError("run IDs must be unique.")
        return list(run_id)
    if not trajectories:
        return ["run_0"]
    derived = [path.stem or f"run_{index}" for index, path in enumerate(trajectories)]
    if len(set(derived)) != len(derived):
        derived = [f"{path.stem or 'run'}_{index}" for index, path in enumerate(trajectories)]
    return derived


def _validate_source_paths(*, topology: Path, coordinates: Path | None, trajectories: list[Path]) -> None:
    paths: list[tuple[str, Path | None]] = [("topology", topology), ("coordinates", coordinates)]
    paths.extend((f"trajectory[{index}]", path) for index, path in enumerate(trajectories))
    for label, path in paths:
        if path is not None and not path.exists():
            raise PackageError(f"{label} file does not exist: {path}")


def _build_run_specs(
    *,
    topology: Path,
    coordinates: Path | None,
    trajectories: list[Path],
    run_ids: list[str],
    start: int | None,
    stop: int | None,
    stride: int,
) -> list[_RunSpec]:
    run_inputs = trajectories or [None]
    package_start = 0
    expected_atoms: int | None = None
    specs: list[_RunSpec] = []
    for index, trajectory in enumerate(run_inputs):
        try:
            universe = load_universe(topology, coordinates=coordinates, trajectory=trajectory)
        except Exception as exc:
            raise PackageError(
                f"Could not open trajectory run '{run_ids[index]}' with the provided topology.",
                suggestion="Check that the topology, coordinates, and trajectory have compatible atom counts and formats.",
            ) from exc
        atom_count = int(universe.atoms.n_atoms)
        if expected_atoms is None:
            expected_atoms = atom_count
        elif atom_count != expected_atoms:
            raise PackageError(
                f"Trajectory run '{run_ids[index]}' has {atom_count} atoms, expected {expected_atoms}.",
                suggestion="Multi-run packages require one shared topology and atom ordering.",
            )
        frame_range = _frame_range(len(universe.trajectory), start=start, stop=stop, stride=stride)
        if len(frame_range) == 0:
            raise PackageError(f"Frame slice selected zero frames for run '{run_ids[index]}'.")
        first_ts = universe.trajectory[frame_range.start]
        package_stop = package_start + len(frame_range)
        specs.append(
            _RunSpec(
                run_id=run_ids[index],
                trajectory=trajectory,
                frame_range=frame_range,
                package_start=package_start,
                package_stop=package_stop,
                atom_count=atom_count,
                reader=universe.trajectory.__class__.__name__,
                format=trajectory.suffix.lower().lstrip(".") if trajectory is not None else topology.suffix.lower().lstrip("."),
                timestep_ps=_trajectory_dt(universe.trajectory),
                has_periodic_box=_has_periodic_box(first_ts),
            )
        )
        package_start = package_stop
    return specs


def _frame_range(total_frames: int, *, start: int | None, stop: int | None, stride: int) -> range:
    start_value = 0 if start is None else start
    stop_value = total_frames if stop is None else min(stop, total_frames)
    if start_value < 0:
        raise PackageError("start must be non-negative")
    if stop_value < start_value:
        raise PackageError("stop must be greater than or equal to start")
    return range(start_value, stop_value, stride)


def _write_topology_arrays(zarr_root, universe) -> None:
    arrays = zarr_root["arrays"]
    create_string_array(arrays, "atom_names", list(universe.atoms.names), overwrite=True)
    create_array(
        arrays,
        "residue_ids",
        shape=(int(universe.atoms.n_atoms),),
        dtype="int64",
        overwrite=True,
    )[:] = list(universe.atoms.resids)
    create_string_array(arrays, "residue_names", list(universe.atoms.resnames), overwrite=True)


def _write_frame_arrays(
    zarr_root,
    *,
    topology: Path,
    coordinates: Path | None,
    run_specs: list[_RunSpec],
    store_positions: bool,
) -> None:
    import numpy as np

    arrays = zarr_root["arrays"]
    n_frames = sum(len(spec.frame_range) for spec in run_specs)
    atom_count = run_specs[0].atom_count
    frame_indices = create_array(
        arrays,
        "frame_indices",
        shape=(n_frames,),
        dtype="int64",
        chunks=(min(max(n_frames, 1), 65_536),),
        overwrite=True,
    )
    source_frame_indices = create_array(
        arrays,
        "source_frame_indices",
        shape=(n_frames,),
        dtype="int64",
        chunks=(min(max(n_frames, 1), 65_536),),
        overwrite=True,
    )
    trajectory_ids = create_array(
        arrays,
        "trajectory_ids",
        shape=(n_frames,),
        dtype="int64",
        chunks=(min(max(n_frames, 1), 65_536),),
        overwrite=True,
    )
    frame_times = create_array(
        arrays,
        "frame_times",
        shape=(n_frames,),
        dtype="float64",
        chunks=(min(max(n_frames, 1), 65_536),),
        overwrite=True,
    )
    create_string_array(
        arrays,
        "run_ids",
        [spec.run_id for spec in run_specs for _ in spec.frame_range],
        overwrite=True,
    )
    positions = None
    if store_positions:
        positions = create_array(
            arrays,
            "positions",
            shape=(n_frames, atom_count, 3),
            dtype="float32",
            chunks=(min(DEFAULT_POSITION_FRAME_CHUNK, max(n_frames, 1)), atom_count, 3),
            overwrite=True,
        )

    for trajectory_id, spec in enumerate(run_specs):
        universe = load_universe(topology, coordinates=coordinates, trajectory=spec.trajectory)
        for out_start in range(spec.package_start, spec.package_stop, DEFAULT_POSITION_FRAME_CHUNK):
            out_stop = min(out_start + DEFAULT_POSITION_FRAME_CHUNK, spec.package_stop)
            local_start = out_start - spec.package_start
            local_stop = out_stop - spec.package_start
            chunk_frames = list(spec.frame_range[local_start:local_stop])
            chunk_indices = np.asarray(chunk_frames, dtype="int64")
            chunk_times = np.empty((len(chunk_frames),), dtype="float64")
            chunk_positions = (
                np.empty((len(chunk_frames), atom_count, 3), dtype="float32")
                if positions is not None
                else None
            )
            for offset, frame_index in enumerate(chunk_frames):
                ts = universe.trajectory[int(frame_index)]
                chunk_times[offset] = _frame_time(ts, frame_index)
                if chunk_positions is not None:
                    chunk_positions[offset] = universe.atoms.positions.astype("float32", copy=False)
            frame_indices[out_start:out_stop] = chunk_indices
            source_frame_indices[out_start:out_stop] = chunk_indices
            trajectory_ids[out_start:out_stop] = np.full((len(chunk_frames),), trajectory_id, dtype="int64")
            frame_times[out_start:out_stop] = chunk_times
            if positions is not None and chunk_positions is not None:
                positions[out_start:out_stop, :, :] = chunk_positions


def _infer_system_type(universe) -> str:
    try:
        if len(universe.select_atoms("protein")) > 0:
            return "protein"
    except Exception:
        pass
    return "unknown"


def _has_periodic_box(ts) -> bool:
    dimensions = getattr(ts, "dimensions", None)
    if dimensions is None:
        return False
    try:
        return bool(any(float(value) > 0 for value in dimensions[:3]))
    except Exception:
        return False


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _trajectory_dt(trajectory) -> float | None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return _safe_float(getattr(trajectory, "dt", None))


def _frame_time(ts, frame_index: int) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        value = _safe_float(getattr(ts, "time", None))
    return value if value is not None else float(frame_index)


def _has_ligand_like_residue(universe) -> bool:
    standard = {
        "ALA",
        "ARG",
        "ASN",
        "ASP",
        "CYS",
        "GLN",
        "GLU",
        "GLY",
        "HIS",
        "ILE",
        "LEU",
        "LYS",
        "MET",
        "PHE",
        "PRO",
        "SER",
        "THR",
        "TRP",
        "TYR",
        "VAL",
        "HOH",
        "WAT",
        "TIP3",
    }
    try:
        return any(resname not in standard for resname in set(universe.atoms.resnames))
    except Exception:
        return False


def _metadata_tags(
    *,
    system_type: str,
    organism: str | None,
    protein: str | None,
    ligand_present: bool,
    simulation_engine: str | None,
    force_field: str | None,
    solvent: str | None,
    ensemble: str | None,
    license: str,
) -> dict:
    return {
        "system": {
            "type": system_type,
            "organism": organism,
            "protein": protein,
            "ligand_present": ligand_present,
        },
        "simulation": {
            "engine": simulation_engine,
            "force_field": force_field,
            "solvent": solvent,
            "ensemble": ensemble,
        },
        "license": {"data_license": license},
    }
