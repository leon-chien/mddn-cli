"""Split strategies."""

from mddatanet.splits.random_window import random_window_split
from mddatanet.splits.service import make_splits, split_package
from mddatanet.splits.temporal import temporal_split
from mddatanet.splits.trajectory import trajectory_split

__all__ = ["make_splits", "random_window_split", "split_package", "temporal_split", "trajectory_split"]
