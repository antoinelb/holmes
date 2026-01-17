"""Unit tests for holmes.api.projection module."""

from datetime import date

import polars as pl
from starlette.testclient import TestClient

from holmes.api.projection import _aggregate_projections, _evaluate_projection
from holmes.app import create_app


class TestProjectionWebSocket:
    """Tests for projection WebSocket handler."""

    def test_get_routes(self):
        """get_routes returns WebSocket routes."""
        from starlette.routing import WebSocketRoute

        from holmes.api.projection import get_routes

        routes = get_routes()
        assert len(routes) == 1
        route = routes[0]
        assert isinstance(route, WebSocketRoute)
        assert route.path == "/"

    def test_websocket_config_message(self):
        """Config message returns available projections."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            response = ws.receive_json()
            assert response["type"] == "config"
            assert isinstance(response["data"], list)

    def test_websocket_config_missing_data(self):
        """Config message without data sends error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment must be provided" in response["data"]

    def test_websocket_projection_message(self):
        """Projection message returns climate projection results."""
        # First get available config
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()

            if len(config_response["data"]) > 0:
                # Use first available config
                first_config = config_response["data"][0]
                ws.send_json(
                    {
                        "type": "projection",
                        "data": {
                            "config": {
                                "model": first_config["model"],
                                "horizon": first_config["horizon"],
                                "scenario": first_config["scenario"],
                            },
                            "calibration": {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": "cemaneige",
                                "hydroParams": {
                                    "x1": 100.0,
                                    "x2": 0.0,
                                    "x3": 50.0,
                                    "x4": 2.0,
                                },
                            },
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "projection"
                # Response contains projection (aggregated) and results (metrics)
                assert isinstance(response["data"], dict)
                assert "projection" in response["data"]
                assert "results" in response["data"]
                assert isinstance(response["data"]["projection"], list)
                assert isinstance(response["data"]["results"], list)

    def test_websocket_projection_without_snow(self):
        """Projection works without snow model."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()

            if len(config_response["data"]) > 0:
                first_config = config_response["data"][0]
                ws.send_json(
                    {
                        "type": "projection",
                        "data": {
                            "config": {
                                "model": first_config["model"],
                                "horizon": first_config["horizon"],
                                "scenario": first_config["scenario"],
                            },
                            "calibration": {
                                "catchment": "Au Saumon",
                                "hydroModel": "bucket",
                                "snowModel": None,
                                "hydroParams": {
                                    "c_soil": 100.0,
                                    "alpha": 0.5,
                                    "k_r": 100.0,
                                    "delta": 6.0,
                                    "beta": 0.5,
                                    "k_t": 200.0,
                                },
                            },
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "projection"
                # Response contains projection (aggregated) and results (metrics)
                assert isinstance(response["data"], dict)
                assert "projection" in response["data"]
                assert "results" in response["data"]

    def test_websocket_projection_missing_params(self):
        """Projection without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "projection", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_unknown_message_type(self):
        """Unknown message type returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["data"]


class TestProjectionDataErrors:
    """Tests for HolmesDataError handling in projection API."""

    def test_config_catchment_without_projection_data(self):
        """Config for catchment without projection file returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            # Leaf catchment has no projection data
            ws.send_json({"type": "config", "data": "Leaf"})
            response = ws.receive_json()
            assert response["type"] == "error"
            # Error should mention projection file not found
            assert "projection" in response["data"].lower()

    def test_projection_invalid_catchment(self):
        """Projection with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json(
                {
                    "type": "projection",
                    "data": {
                        "config": {
                            "model": "some_model",
                            "horizon": "2050",
                            "scenario": "rcp45",
                        },
                        "calibration": {
                            "catchment": "NonExistentCatchment",
                            "hydroModel": "gr4j",
                            "snowModel": None,
                            "hydroParams": {
                                "x1": 100.0,
                                "x2": 0.0,
                                "x3": 50.0,
                                "x4": 2.0,
                            },
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            # Error should mention CemaNeige or catchment issue
            assert (
                "cemaneige" in response["data"].lower()
                or "catchment" in response["data"].lower()
            )


class TestProjectionHelpers:
    """Tests for projection helper functions."""

    def test_aggregate_projections(self):
        """_aggregate_projections aggregates by day of year with median."""
        # Create test DataFrame with multiple members and dates spanning 2 years
        data = pl.DataFrame(
            {
                "date": [
                    date(2020, 1, 1),
                    date(2020, 1, 2),
                    date(2021, 1, 1),
                    date(2021, 1, 2),
                    date(2020, 1, 1),
                    date(2020, 1, 2),
                    date(2021, 1, 1),
                    date(2021, 1, 2),
                ],
                "streamflow": [10.0, 20.0, 12.0, 22.0, 14.0, 24.0, 16.0, 26.0],
                "member": ["m1", "m1", "m1", "m1", "m2", "m2", "m2", "m2"],
            }
        )

        result = _aggregate_projections(data)

        # Should have one row per unique day_of_year
        assert len(result) == 2
        # Should have columns for each member plus median and date
        assert "m1" in result.columns
        assert "m2" in result.columns
        assert "median" in result.columns
        assert "date" in result.columns
        # Date column should start from 2021-01-01 (synthetic year)
        assert result["date"].to_list()[0] == date(2021, 1, 1)
        # Values should be averaged across years for each member
        # m1 day 1: (10 + 12) / 2 = 11
        # m2 day 1: (14 + 16) / 2 = 15
        m1_day1 = result.filter(pl.col("date") == date(2021, 1, 1))["m1"][0]
        m2_day1 = result.filter(pl.col("date") == date(2021, 1, 1))["m2"][0]
        assert m1_day1 == 11.0
        assert m2_day1 == 15.0
        # Median should be median of member values
        median_day1 = result.filter(pl.col("date") == date(2021, 1, 1))["median"][0]
        assert median_day1 == 13.0  # median of [11, 15]

    def test_aggregate_projections_handles_leap_years(self):
        """Day 366 is mapped to day 1 for leap years via (ordinal-1) mod 365 + 1."""
        # The formula (ordinal_day - 1) mod 365 + 1 maps:
        # - Day 366 (Dec 31 in leap year) → (366-1) mod 365 + 1 = 0 + 1 = 1
        # - Day 365 (Dec 31 in non-leap year) → (365-1) mod 365 + 1 = 364 + 1 = 365
        data = pl.DataFrame(
            {
                "date": [
                    date(2020, 12, 31),  # Day 366 → maps to day 1
                    date(2020, 1, 1),  # Day 1 → maps to day 1
                ],
                "streamflow": [100.0, 80.0],
                "member": ["m1", "m1"],
            }
        )

        result = _aggregate_projections(data)

        # Both should be grouped to day 1
        assert len(result) == 1
        # Average of 100 and 80
        assert result["m1"][0] == 90.0

    def test_evaluate_projection(self):
        """_evaluate_projection computes seasonal metrics."""
        # Create test DataFrame spanning multiple years with varied seasonal values
        dates = []
        streamflows = []
        members = []

        # Generate data for 2 years, 2 members
        for year in [2020, 2021]:
            for month in range(1, 13):
                for member in ["m1", "m2"]:
                    d = date(year, month, 15)
                    dates.append(d)
                    members.append(member)
                    # Base streamflow varies by season
                    if month in [1, 2, 3]:  # Winter
                        base = 5.0
                    elif month in [3, 4, 5, 6]:  # Spring (overlaps with winter end)
                        base = 50.0 if month != 3 else 20.0
                    elif month in [5, 6, 7, 8, 9, 10]:  # Summer (overlaps with spring)
                        base = 2.0 if month not in [5, 6] else 15.0
                    else:  # Autumn (9, 10, 11, 12)
                        base = 30.0
                    # Add member variation
                    if member == "m2":
                        base *= 1.1
                    streamflows.append(base)

        data = pl.DataFrame(
            {"date": dates, "streamflow": streamflows, "member": members}
        )

        result = _evaluate_projection(data)

        # Should have one row per member
        assert len(result) == 2
        # Should have all metric columns
        assert "winter_min" in result.columns
        assert "summer_min" in result.columns
        assert "spring_max" in result.columns
        assert "autumn_max" in result.columns
        assert "mean" in result.columns
        assert "member" in result.columns

    def test_evaluate_projection_seasonal_boundaries(self):
        """Verify correct month boundaries for each season."""
        # Create minimal data to verify each season is correctly filtered
        # Winter: months 1-3, Summer: months 5-10, Spring: months 3-6, Autumn: months 9-12
        dates = []
        streamflows = []
        members = []

        # Create specific values for each month to verify filtering
        month_values = {
            1: 10,  # Winter only
            2: 11,  # Winter only
            3: 12,  # Winter + Spring
            4: 100,  # Spring only
            5: 1,  # Spring + Summer
            6: 2,  # Spring + Summer
            7: 3,  # Summer only
            8: 4,  # Summer only
            9: 50,  # Summer + Autumn
            10: 5,  # Summer + Autumn
            11: 60,  # Autumn only
            12: 70,  # Autumn only
        }

        for month, value in month_values.items():
            dates.append(date(2020, month, 15))
            streamflows.append(float(value))
            members.append("test")

        data = pl.DataFrame(
            {"date": dates, "streamflow": streamflows, "member": members}
        )

        result = _evaluate_projection(data)

        # Winter min (months 1-3): min of 10, 11, 12 = 10
        assert result["winter_min"][0] == 10.0
        # Summer min (months 5-10): min of 1, 2, 3, 4, 50, 5 = 1
        assert result["summer_min"][0] == 1.0
        # Spring max (months 3-6): max of 12, 100, 1, 2 = 100
        assert result["spring_max"][0] == 100.0
        # Autumn max (months 9-12): max of 50, 5, 60, 70 = 70
        assert result["autumn_max"][0] == 70.0
