from playwright.sync_api import Page

from tests.e2e.drivers import goto_app, select_station, wait_chart

#### tests ####


def test_reload_restores_hydrographs(page: Page, base_url: str) -> None:
    goto_app(page)
    select_station(page, "calibration", "061004")
    select_station(page, "simulation", "061020")
    wait_chart(page, "hydrographs__calibration")
    wait_chart(page, "hydrographs__simulation")
    # the persisted stations' series are requested at connect, before the
    # station list lands, so both hydrographs must draw again on their own
    page.reload()
    wait_chart(page, "hydrographs__calibration")
    wait_chart(page, "hydrographs__simulation")
