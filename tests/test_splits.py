from mddatanet.splits.temporal import temporal_split, validate_split_indices


def test_temporal_split_with_gap():
    splits = temporal_split(100, train=0.7, val=0.15, test=0.15, gap=5)

    assert splits["train"][0] == 0
    assert splits["train"][-1] == 69
    assert splits["val"][0] == 75
    assert splits["test"][0] == 95
    validate_split_indices(splits, num_frames=100)

