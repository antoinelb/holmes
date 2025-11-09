"""Additional tests for projection data to cover missing lines."""

import pytest
from src import data


def test_read_projection_data_with_non_ref_horizon_rcp45():
    """Test RCP4.5 with non-REF horizon to cover line 95-96."""
    # Use Au Saumon catchment which we know has projection data
    df = data.read_projection_data("Au Saumon", "CSI", "RCP4.5", "H20")
    assert len(df) > 0
    # Verify we got precipitation and temperature columns
    assert any("precipitation" in col for col in df.columns)
    assert any("temperature" in col for col in df.columns)


def test_read_projection_data_with_non_ref_horizon_rcp85():
    """Test RCP8.5 with non-REF horizon to cover line 97-98."""
    # Use Au Saumon catchment which we know has projection data
    df = data.read_projection_data("Au Saumon", "CSI", "RCP8.5", "H50")
    assert len(df) > 0
    # Verify we got precipitation and temperature columns
    assert any("precipitation" in col for col in df.columns)
    assert any("temperature" in col for col in df.columns)


def test_read_projection_data_invalid_scenario_with_non_ref_horizon():
    """Test invalid scenario with non-REF horizon to cover line 99-100."""
    with pytest.raises(ValueError, match="must be RCP4.5 or RCP8.5"):
        data.read_projection_data("Au Saumon", "CSI", "INVALID_SCENARIO", "H80")
