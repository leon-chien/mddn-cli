from pydantic import ValidationError

from mddatanet.format.schema import FeatureConfig


def test_feature_config_requires_unique_names():
    try:
        FeatureConfig.model_validate(
            {
                "features": [
                    {
                        "name": "d",
                        "type": "min_distance",
                        "selection_a": "resname LIG",
                        "selection_b": "protein",
                    },
                    {
                        "name": "d",
                        "type": "min_distance",
                        "selection_a": "resname LIG",
                        "selection_b": "protein",
                    },
                ]
            }
        )
    except ValidationError:
        return
    raise AssertionError("duplicate feature names should be rejected")

