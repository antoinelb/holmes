import polars as pl

from holmes.preprocessing import write_missing_fig


class TestWriteMissingFig:
    def test_saves_svg_with_missing_runs(self, tmp_path, joined_df):
        data = (
            joined_df.filter(pl.col("id") == "061004")
            .head(60)
            .with_columns(pl.col("datetime").cast(pl.Datetime("us")))
        )
        data = data.with_columns(
            pl.when(pl.arange(0, data.height).is_in([5, 20, 21, 22]))
            .then(None)
            .otherwise(pl.col("streamflow"))
            .alias("streamflow")
        )
        path = tmp_path / "figures" / "missing.svg"
        write_missing_fig(data, path)
        assert path.exists()
        assert path.read_bytes().startswith(b"<svg")
