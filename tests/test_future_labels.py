from mddatanet.labels.future import future_event_labels


def test_future_event_labels_are_inclusive():
    labels = future_event_labels([False, False, True, False], horizon_frames=2)

    assert labels == [True, True, True, False]

