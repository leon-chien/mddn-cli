from mddatanet.labels.future import fixed_horizon_valid_mask, future_event_labels


def test_future_event_labels_are_inclusive():
    labels = future_event_labels([False, False, True, False], horizon_frames=2)

    assert labels == [True, True, True, False]


def test_fixed_horizon_valid_mask_respects_run_boundaries():
    mask = fixed_horizon_valid_mask(
        6,
        2,
        run_ids=["run_a", "run_a", "run_a", "run_b", "run_b", "run_b"],
    )

    assert mask == [True, False, False, True, False, False]
