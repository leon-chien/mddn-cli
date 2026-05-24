from pydantic import ValidationError

from mddatanet.format.schema import EventConfig


def test_event_config_valid_threshold():
    config = EventConfig.model_validate(
        {
            "events": [
                {
                    "name": "unbound",
                    "type": "feature_threshold",
                    "feature": "distance",
                    "operator": "greater_than",
                    "threshold": 15.0,
                    "horizon_frames": 500,
                }
            ]
        }
    )

    assert config.events[0].name == "unbound"


def test_event_config_rejects_missing_feature():
    try:
        EventConfig.model_validate(
            {
                "events": [
                    {
                        "name": "bad",
                        "type": "feature_threshold",
                        "operator": "greater_than",
                        "threshold": 15.0,
                    }
                ]
            }
        )
    except ValidationError:
        return
    raise AssertionError("missing feature should be rejected")

