from datetime import date
from typing import Any
from unittest.mock import MagicMock

import polars as pl
import pytest

import holmes.data.archive as archive

sentinel_name = "raw/hydro/station_data.ipc"

old_df = pl.DataFrame({"a": [1, 2]})
new_df = pl.DataFrame({"a": [3, 4]})
era5_df = pl.DataFrame({"b": [5.0]})


def make_api_response(payload: Any) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


class FakeStreamResponse:
    def __init__(
        self,
        content: bytes,
        *,
        chunks: list[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._chunks = [content] if chunks is None else chunks
        self.headers = {} if headers is None else headers

    def __enter__(self) -> "FakeStreamResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_bytes(self):
        yield from self._chunks


def patch_release(monkeypatch, payload: Any) -> None:
    monkeypatch.setattr(
        archive.httpx,
        "get",
        lambda url, **kwargs: make_api_response(payload),
    )


def patch_stream(
    monkeypatch, content: bytes, headers: dict[str, str] | None = None
) -> list[str]:
    calls: list[str] = []

    def fake_stream(method: str, url: str, **kwargs: Any):
        calls.append(url)
        return FakeStreamResponse(content, headers=headers)

    monkeypatch.setattr(archive.httpx, "stream", fake_stream)
    return calls


class TestSyncData:
    def test_newer_remote_downloads_and_swaps(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json, capsys
    ):
        # pre-existing data an update must replace, plus a stale marker
        local_sentinel = tmp_data_dir / sentinel_name
        local_sentinel.parent.mkdir(parents=True)
        old_df.write_ipc(local_sentinel)
        (tmp_data_dir / archive.marker_name).write_text("2026-01-01")
        # a leftover staging dir from an interrupted previous sync
        stale = tmp_data_dir / "tmp" / "extract" / "stale.txt"
        stale.parent.mkdir(parents=True)
        stale.write_text("stale")

        patch_release(monkeypatch, release_json("2026-08-15"))
        patch_stream(
            monkeypatch,
            zip_bytes(
                {sentinel_name: new_df, "raw/weather/era5.ipc": era5_df}
            ),
        )

        archive.sync_data()

        assert archive.local_archive_date() == date(2026, 8, 15)
        assert pl.read_ipc(local_sentinel, memory_map=False).equals(new_df)
        assert pl.read_ipc(
            tmp_data_dir / "raw" / "weather" / "era5.ipc", memory_map=False
        ).equals(era5_df)
        assert not (tmp_data_dir / "tmp").exists()
        assert not list(tmp_data_dir.rglob("*.part"))
        out = capsys.readouterr().out
        assert "Downloaded data archive (2026-08-15)." in out
        # an existing archive is an update, not a first run
        assert "Updating the data" in out
        assert "first run" not in out
        assert "Extracted the archive." in out

    def test_equal_local_skips_download(
        self, tmp_data_dir, monkeypatch, release_json
    ):
        (tmp_data_dir / archive.marker_name).write_text("2026-08-15")
        patch_release(monkeypatch, release_json("2026-08-15"))
        stream = MagicMock()
        monkeypatch.setattr(archive.httpx, "stream", stream)

        archive.sync_data()

        stream.assert_not_called()

    def test_newer_local_skips_download(
        self, tmp_data_dir, monkeypatch, release_json
    ):
        (tmp_data_dir / archive.marker_name).write_text("2026-12-31")
        patch_release(monkeypatch, release_json("2026-08-15"))
        stream = MagicMock()
        monkeypatch.setattr(archive.httpx, "stream", stream)

        archive.sync_data()

        stream.assert_not_called()

    def test_api_failure_with_local_data_warns(
        self, tmp_data_dir, monkeypatch, capsys
    ):
        local_sentinel = tmp_data_dir / sentinel_name
        local_sentinel.parent.mkdir(parents=True)
        old_df.write_ipc(local_sentinel)

        def boom(url, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(archive.httpx, "get", boom)

        archive.sync_data()

        out = capsys.readouterr().out
        assert "Could not check the data release (boom)" in out
        assert "using existing local data" in out
        assert pl.read_ipc(local_sentinel, memory_map=False).equals(old_df)

    def test_api_failure_without_data_raises(self, monkeypatch):
        def boom(url, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(archive.httpx, "get", boom)

        with pytest.raises(archive.MissingDataError, match="holmes download"):
            archive.sync_data()

    def test_no_matching_asset_raises(self, monkeypatch):
        patch_release(
            monkeypatch,
            {
                "assets": [
                    {
                        "name": "data-cache.tar.gz",
                        "browser_download_url": "u",
                    },
                    {"browser_download_url": "u"},
                ]
            },
        )

        with pytest.raises(archive.MissingDataError, match="holmes download"):
            archive.sync_data()

    def test_first_run_announces_the_one_time_wait(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json, capsys
    ):
        patch_release(monkeypatch, release_json("2026-08-15"))
        patch_stream(monkeypatch, zip_bytes({sentinel_name: new_df}))

        archive.sync_data()

        out = capsys.readouterr().out
        assert "first run only" in out
        assert "the app starts as soon as it is done" in out

    def test_garbled_marker_over_real_data_is_not_a_first_run(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json, capsys
    ):
        local_sentinel = tmp_data_dir / sentinel_name
        local_sentinel.parent.mkdir(parents=True)
        old_df.write_ipc(local_sentinel)
        (tmp_data_dir / archive.marker_name).write_text("not-a-date")

        patch_release(monkeypatch, release_json("2026-08-15"))
        patch_stream(monkeypatch, zip_bytes({sentinel_name: new_df}))

        archive.sync_data()

        assert "first run" not in capsys.readouterr().out

    def test_interrupt_clears_staging_and_propagates(
        self, tmp_data_dir, monkeypatch, release_json
    ):
        patch_release(monkeypatch, release_json("2026-08-15"))

        def interrupt(method: str, url: str, **kwargs: Any):
            (tmp_data_dir / "tmp").mkdir(parents=True, exist_ok=True)
            (tmp_data_dir / "tmp" / "partial.part").write_bytes(b"partial")
            raise KeyboardInterrupt

        monkeypatch.setattr(archive.httpx, "stream", interrupt)

        with pytest.raises(KeyboardInterrupt):
            archive.sync_data()

        assert not (tmp_data_dir / "tmp").exists()

    def test_max_dated_asset_chosen(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json
    ):
        patch_release(
            monkeypatch,
            release_json(
                "2026-08-15",
                extra_assets=[
                    "data-2026-01-01.zip",
                    "era5.ipc",
                    "data-cache.tar.gz",
                ],
            ),
        )
        calls = patch_stream(monkeypatch, zip_bytes({sentinel_name: new_df}))

        archive.sync_data()

        assert calls == ["https://example.com/data-2026-08-15.zip"]
        assert archive.local_archive_date() == date(2026, 8, 15)

    def test_garbage_zip_keeps_old_data(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json, capsys
    ):
        local_sentinel = tmp_data_dir / sentinel_name
        local_sentinel.parent.mkdir(parents=True)
        old_df.write_ipc(local_sentinel)
        (tmp_data_dir / archive.marker_name).write_text("2026-01-01")

        patch_release(monkeypatch, release_json("2026-08-15"))
        # the zip extracts but holds no sentinel, so it is not a data archive
        patch_stream(monkeypatch, zip_bytes({"raw/other.ipc": new_df}))

        archive.sync_data()

        out = capsys.readouterr().out
        assert "Could not download the data archive" in out
        assert pl.read_ipc(local_sentinel, memory_map=False).equals(old_df)
        assert archive.local_archive_date() == date(2026, 1, 1)
        assert not (tmp_data_dir / "raw" / "other.ipc").exists()

    def test_garbage_zip_without_data_raises(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json
    ):
        patch_release(monkeypatch, release_json("2026-08-15"))
        patch_stream(monkeypatch, zip_bytes({"raw/other.ipc": new_df}))

        with pytest.raises(archive.MissingDataError, match="holmes download"):
            archive.sync_data()

    def test_zip_slip_member_rejected(
        self, tmp_data_dir, monkeypatch, zip_bytes, release_json
    ):
        patch_release(monkeypatch, release_json("2026-08-15"))
        patch_stream(
            monkeypatch,
            zip_bytes({"../evil.txt": b"evil", sentinel_name: new_df}),
        )

        with pytest.raises(archive.MissingDataError, match="holmes download"):
            archive.sync_data()

        assert not list(tmp_data_dir.parent.rglob("evil.txt"))


class TestDownloadArchive:
    def test_counts_one_tick_per_megabyte(self, tmp_data_dir, monkeypatch):
        tracker = MagicMock()
        tracker.__enter__.return_value = tracker
        made = MagicMock(return_value=tracker)
        monkeypatch.setattr(archive, "progress_task", made)
        # 3 MB streamed in half-megabyte chunks
        monkeypatch.setattr(
            archive.httpx,
            "stream",
            lambda method, url, **kwargs: FakeStreamResponse(
                b"",
                chunks=[b"x" * (archive.mb // 2)] * 6,
                headers={"content-length": str(3 * archive.mb)},
            ),
        )

        path = archive._download_archive(
            "url", date(2026, 8, 15), tmp_data_dir / "tmp"
        )

        made.assert_called_once_with(
            "MB downloaded", "Downloaded the archive.", 3
        )
        assert tracker.increment.call_count == 3
        assert path.stat().st_size == 3 * archive.mb

    def test_undeclared_size_falls_back_to_a_plain_task(
        self, tmp_data_dir, monkeypatch
    ):
        made = MagicMock()
        monkeypatch.setattr(archive, "progress_task", made)
        patch_stream(monkeypatch, b"body")

        path = archive._download_archive(
            "url", date(2026, 8, 15), tmp_data_dir / "tmp"
        )

        made.assert_not_called()
        assert path.read_bytes() == b"body"

    # the counter is display only: a junk header must not cost the download
    def test_unparsable_size_still_downloads(self, tmp_data_dir, monkeypatch):
        patch_stream(
            monkeypatch, b"body", headers={"content-length": "garbage"}
        )

        path = archive._download_archive(
            "url", date(2026, 8, 15), tmp_data_dir / "tmp"
        )

        assert path.read_bytes() == b"body"


class TestReadProduct:
    def test_hit(self, tmp_data_dir):
        path = tmp_data_dir / sentinel_name
        path.parent.mkdir(parents=True)
        old_df.write_ipc(path, compression="zstd")

        assert archive.read_product(path).equals(old_df)

    def test_miss(self, tmp_data_dir):
        path = tmp_data_dir / sentinel_name

        with pytest.raises(archive.MissingDataError, match="holmes download"):
            archive.read_product(path)


class TestLocalArchiveDate:
    def test_absent(self, tmp_data_dir):
        assert archive.local_archive_date() is None

    def test_valid(self, tmp_data_dir):
        (tmp_data_dir / archive.marker_name).write_text("2026-08-15\n")

        assert archive.local_archive_date() == date(2026, 8, 15)

    def test_garbled(self, tmp_data_dir):
        (tmp_data_dir / archive.marker_name).write_text("not-a-date")

        assert archive.local_archive_date() is None
