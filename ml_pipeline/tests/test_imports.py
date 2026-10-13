from src.inference.offline_inference_report import infer_command_name
from src.preprocessing.feature_extraction import validate_features


def test_infer_command_name_detects_known_label():
    assert infer_command_name("outputs/demo_signals/front/sample.csv", ["front", "left"]) == "front"


def test_validate_features_accepts_finite_values():
    assert validate_features([[1.0, 2.0, 3.0]])
