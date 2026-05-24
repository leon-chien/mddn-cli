from mddatanet.labels.future import time_to_event


def test_time_to_event():
    values = time_to_event([False, False, True, False, True])

    assert values == [2, 1, 0, 1, 0]

