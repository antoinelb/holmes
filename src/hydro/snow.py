#########
# types #
#########

snow_models = {
    "CemaNeige": {
        "parameters": {
            "Ctg": {
                "min": 0,
                "max": 1,
                "is_integer": False,
            },
            "Kf": {
                "min": 0,
                "max": 20,
                "is_integer": True,
            },
        }
    }
}
