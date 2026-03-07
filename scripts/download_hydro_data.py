import sys

########
# main #
########


def main() -> None:
    # 061028 to test
    station_id = parse_args()
    if station_id is None:
        sys.exit(2)


def parse_args() -> str | None:
    if len(sys.argv) == 2 and sys.argv[1] not in ("--help", "-h"):
        station_id = sys.argv[1]
        return station_id
    else:
        print("Usage: python download_hydro_data <station_id>")
        print()
        print(
            "Downloads the hydrological data for the given station id. "
            + "You can find this id in the Atlas hydroclimatique du Québec "
            + "(https://www.cehq.gouv.qc.ca/atlas-hydroclimatique/stations-hydrometriques/index.htm)."
        )
        print()
        print("Positional arguments:")
        print("  station_id  The hydrological station id")
        return None


if __name__ == "__main__":
    main()
