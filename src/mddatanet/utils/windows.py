"""Utilities for extracting sliding windows for ML training."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import numpy as np

from mddatanet.io.zarr_store import open_zarr_group


def iter_windows(
    package_path: Path,
    *,
    window_size: int,
    feature_names: list[str] | None = None,
    label_name: str | None = None,
    stride: int = 1,
    include_labels: bool = True,
) -> Generator[dict[str, np.ndarray], None, None]:
    """Iterate over sliding windows of features and labels.

    Yields:
        A dictionary with "features" (shape [window_size, num_features])
        and optional "label" (scalar or shape [num_labels]).
    """
    zarr_root = open_zarr_group(package_path / "dataset.zarr", mode="r")
    feature_group = zarr_root["features"]
    
    if feature_names is None:
        feature_names = sorted(feature_group.keys())
    
    features = [feature_group[name] for name in feature_names]
    num_frames = features[0].shape[0]
    
    labels = []
    label_mask = None
    if include_labels and label_name:
        # label_name could be "my_event/event_future_500"
        label_arr = zarr_root[f"labels/{label_name}"]
        labels.append(label_arr)
        mask_path = f"labels/{label_name}_valid_mask"
        try:
            label_mask = zarr_root[mask_path]
        except KeyError:
            label_mask = None

    # We also need to respect run boundaries.
    # We should not create windows that cross runs.
    run_ids = zarr_root["arrays/run_ids"][:]
    
    for i in range(0, num_frames - window_size + 1, stride):
        # Check if run_id is the same across the window
        if run_ids[i] != run_ids[i + window_size - 1]:
            continue
            
        window_feat = np.stack([feat[i : i + window_size] for feat in features], axis=1)
        result = {"features": window_feat}
        
        if labels:
            # We usually want the label at the end of the window, 
            # or the future label relative to the end of the window.
            # event_future_H at frame i means "event occurs in [i, i+H]".
            # If our window is [i, i+window_size-1], we might want the label at i+window_size-1.
            label_index = i + window_size - 1
            if label_mask is not None and not bool(label_mask[label_index]):
                continue
            result["label"] = labels[0][label_index]
            
        yield result
