from typing import get_args

import holmes_rs
import pytest

from holmes.model import Algorithm, HydroModel
from holmes.model_info import get_calibration_info, get_model_info


class TestGetModelInfo:
    def test_covers_every_model(self):
        info = get_model_info()
        assert set(info["hydro"]) == set(get_args(HydroModel))
        assert set(info["snow"]) == {"cemaneige"}

    @pytest.mark.parametrize("model", get_args(HydroModel))
    def test_hydro_info_matches_holmes_rs(self, model):
        info = get_model_info()["hydro"][model]
        mod = getattr(holmes_rs.hydro, model)
        assert info["description"]["en"]
        assert info["description"]["fr"]
        assert info["parameters"]["en"] == list(mod.param_descriptions)
        assert info["parameters"]["fr"] == list(mod.param_descriptions_fr)

    def test_cemaneige_parameters_are_hand_written(self):
        info = get_model_info()["snow"]["cemaneige"]
        assert info["description"]["en"]
        assert info["description"]["fr"]
        assert len(info["parameters"]["en"]) == 3
        assert len(info["parameters"]["fr"]) == 3


class TestGetCalibrationInfo:
    def test_covers_models_and_algorithms(self):
        info = get_calibration_info()
        assert set(info["hydro"]) == set(get_args(HydroModel))
        assert set(info["algorithms"]) == set(get_args(Algorithm))

    @pytest.mark.parametrize("model", get_args(HydroModel))
    def test_param_info_matches_holmes_rs(self, model):
        params = get_calibration_info()["hydro"][model]
        mod = getattr(holmes_rs.hydro, model)
        defaults, bounds = mod.init()
        assert [param["name"] for param in params] == list(mod.param_names)
        for param, default, (low, high) in zip(
            params, defaults, bounds, strict=True
        ):
            assert param["description"]["en"]
            assert param["description"]["fr"]
            assert param["default"] == pytest.approx(float(default))
            assert param["min"] == pytest.approx(float(low))
            assert param["max"] == pytest.approx(float(high))
