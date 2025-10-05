import math

import numba
import numpy as np

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

# 366-day temperature gradient array (from v2)
TEMPERATURE_GRADIENT = np.array(
    [
        -0.376,
        -0.374,
        -0.371,
        -0.368,
        -0.366,
        -0.363,
        -0.361,
        -0.358,
        -0.355,
        -0.353,
        -0.350,
        -0.348,
        -0.345,
        -0.343,
        -0.340,
        -0.337,
        -0.335,
        -0.332,
        -0.329,
        -0.327,
        -0.324,
        -0.321,
        -0.319,
        -0.316,
        -0.313,
        -0.311,
        -0.308,
        -0.305,
        -0.303,
        -0.300,
        -0.297,
        -0.295,
        -0.292,
        -0.289,
        -0.287,
        -0.284,
        -0.281,
        -0.279,
        -0.276,
        -0.273,
        -0.271,
        -0.268,
        -0.265,
        -0.263,
        -0.260,
        -0.262,
        -0.264,
        -0.266,
        -0.268,
        -0.270,
        -0.272,
        -0.274,
        -0.277,
        -0.279,
        -0.281,
        -0.283,
        -0.285,
        -0.287,
        -0.289,
        -0.291,
        -0.293,
        -0.295,
        -0.297,
        -0.299,
        -0.301,
        -0.303,
        -0.306,
        -0.308,
        -0.310,
        -0.312,
        -0.314,
        -0.316,
        -0.318,
        -0.320,
        -0.323,
        -0.326,
        -0.330,
        -0.333,
        -0.336,
        -0.339,
        -0.343,
        -0.346,
        -0.349,
        -0.352,
        -0.355,
        -0.359,
        -0.362,
        -0.365,
        -0.368,
        -0.372,
        -0.375,
        -0.378,
        -0.381,
        -0.385,
        -0.388,
        -0.391,
        -0.394,
        -0.397,
        -0.401,
        -0.404,
        -0.407,
        -0.410,
        -0.414,
        -0.417,
        -0.420,
        -0.420,
        -0.421,
        -0.421,
        -0.421,
        -0.422,
        -0.422,
        -0.422,
        -0.423,
        -0.423,
        -0.423,
        -0.424,
        -0.424,
        -0.424,
        -0.425,
        -0.425,
        -0.425,
        -0.426,
        -0.426,
        -0.426,
        -0.427,
        -0.427,
        -0.427,
        -0.428,
        -0.428,
        -0.428,
        -0.429,
        -0.429,
        -0.429,
        -0.430,
        -0.430,
        -0.428,
        -0.425,
        -0.423,
        -0.421,
        -0.419,
        -0.416,
        -0.414,
        -0.412,
        -0.410,
        -0.407,
        -0.405,
        -0.403,
        -0.401,
        -0.398,
        -0.396,
        -0.394,
        -0.392,
        -0.389,
        -0.387,
        -0.385,
        -0.383,
        -0.380,
        -0.378,
        -0.376,
        -0.374,
        -0.371,
        -0.369,
        -0.367,
        -0.365,
        -0.362,
        -0.360,
        -0.362,
        -0.365,
        -0.367,
        -0.369,
        -0.372,
        -0.374,
        -0.376,
        -0.379,
        -0.381,
        -0.383,
        -0.386,
        -0.388,
        -0.390,
        -0.393,
        -0.395,
        -0.397,
        -0.400,
        -0.402,
        -0.404,
        -0.407,
        -0.409,
        -0.411,
        -0.414,
        -0.416,
        -0.418,
        -0.421,
        -0.423,
        -0.425,
        -0.428,
        -0.430,
        -0.431,
        -0.431,
        -0.432,
        -0.433,
        -0.433,
        -0.434,
        -0.435,
        -0.435,
        -0.436,
        -0.436,
        -0.437,
        -0.438,
        -0.438,
        -0.439,
        -0.440,
        -0.440,
        -0.441,
        -0.442,
        -0.442,
        -0.443,
        -0.444,
        -0.444,
        -0.445,
        -0.445,
        -0.446,
        -0.447,
        -0.447,
        -0.448,
        -0.449,
        -0.449,
        -0.450,
        -0.448,
        -0.447,
        -0.445,
        -0.444,
        -0.442,
        -0.440,
        -0.439,
        -0.437,
        -0.435,
        -0.434,
        -0.432,
        -0.431,
        -0.429,
        -0.427,
        -0.426,
        -0.424,
        -0.423,
        -0.421,
        -0.419,
        -0.418,
        -0.416,
        -0.415,
        -0.413,
        -0.411,
        -0.410,
        -0.408,
        -0.406,
        -0.405,
        -0.403,
        -0.402,
        -0.400,
        -0.403,
        -0.405,
        -0.408,
        -0.411,
        -0.413,
        -0.416,
        -0.419,
        -0.421,
        -0.424,
        -0.427,
        -0.429,
        -0.432,
        -0.435,
        -0.437,
        -0.440,
        -0.443,
        -0.445,
        -0.448,
        -0.451,
        -0.453,
        -0.456,
        -0.459,
        -0.461,
        -0.464,
        -0.467,
        -0.469,
        -0.472,
        -0.475,
        -0.477,
        -0.480,
        -0.482,
        -0.483,
        -0.485,
        -0.486,
        -0.488,
        -0.490,
        -0.491,
        -0.493,
        -0.495,
        -0.496,
        -0.498,
        -0.499,
        -0.501,
        -0.503,
        -0.504,
        -0.506,
        -0.507,
        -0.509,
        -0.511,
        -0.512,
        -0.514,
        -0.515,
        -0.517,
        -0.519,
        -0.520,
        -0.522,
        -0.524,
        -0.525,
        -0.527,
        -0.528,
        -0.530,
        -0.526,
        -0.523,
        -0.519,
        -0.515,
        -0.512,
        -0.508,
        -0.504,
        -0.501,
        -0.497,
        -0.493,
        -0.490,
        -0.486,
        -0.482,
        -0.479,
        -0.475,
        -0.471,
        -0.468,
        -0.464,
        -0.460,
        -0.457,
        -0.453,
        -0.449,
        -0.446,
        -0.442,
        -0.438,
        -0.435,
        -0.431,
        -0.427,
        -0.424,
        -0.420,
        -0.417,
        -0.415,
        -0.412,
        -0.410,
        -0.407,
        -0.405,
        -0.402,
        -0.399,
        -0.397,
        -0.394,
        -0.392,
        -0.389,
        -0.386,
        -0.384,
        -0.381,
        -0.379,
    ]
)

##########
# public #
##########


@numba.jit(nopython=True)
def run_cemaneige(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    day_of_year: np.ndarray,
    altitude_layers: np.ndarray,
    median_altitude: float,
    n_altitude_layers: int,
    ctg: float,
    kf: float,
    beta: float,
    vmin: float,
    tf: float,
    qnbv: float,
    gthreshold: float,
) -> np.ndarray:
    """
    Run CemaNeige snow accounting model.

    Parameters:
        precipitation: Daily precipitation (mm)
        temperature: Daily air temperature (°C)
        day_of_year: Day of year (1-366)
        altitude_layers: Altitude of each layer (m)
        median_altitude: Median catchment altitude (m)
        n_altitude_layers: Number of altitude layers
        ctg: Thermal inertia parameter (0-1)
        kf: Snowmelt factor (0-20)
        beta: Precipitation gradient (default 0)
        vmin: Minimum melt threshold (default 0.1)
        tf: Freezing temperature threshold (default 0)
        qnbv: Snow quantity parameter
        gthreshold: Snow threshold for melting

    Returns:
        Array of water output (liquid precip + snowmelt) in mm/day
    """
    n_timesteps = precipitation.shape[0]
    output = np.zeros(n_timesteps)

    # Initialize snow states
    snowpack = np.zeros(n_altitude_layers)  # G: snowpack content
    thermal_state = np.zeros(n_altitude_layers)  # eTg: thermal state

    # Compute normalization constant
    c = (
        np.sum(np.exp(beta * (altitude_layers - median_altitude)))
        / n_altitude_layers
    )

    for t in range(n_timesteps):
        # Forcing regionalization
        doy = day_of_year[t] - 1  # Convert to 0-based index
        theta = TEMPERATURE_GRADIENT[doy]

        # Temperature at each altitude layer
        tz = temperature[t] + theta * (altitude_layers - median_altitude) / 100

        # Precipitation at each altitude layer
        pz = (
            (1 / c)
            * (precipitation[t] / n_altitude_layers)
            * np.exp(beta * (altitude_layers - median_altitude))
        )

        # Fraction of solid precipitation
        fsol = np.zeros(n_altitude_layers)
        for z in range(n_altitude_layers):
            if tz[z] > 3:
                fsol[z] = 0
            elif tz[z] < -1:
                fsol[z] = 1
            else:
                fsol[z] = 1 - ((tz[z] - (-1)) / (3 - (-1)))

        # Split into liquid and solid precipitation
        pl = (1 - fsol) * pz
        ps = fsol * pz

        # Snow accumulation
        snowpack += ps

        # Thermal state update
        tmp = ctg * thermal_state + (1 - ctg) * tz
        thermal_state = np.minimum(0, tmp)

        # Snow melt calculation
        ftg = thermal_state >= tf  # Melting factor
        fpot = (tz > 0) * np.minimum(snowpack, kf * (tz - tf) * ftg)
        fnts = np.minimum(snowpack / gthreshold, 1)

        snow_melt = fpot * ((1 - vmin) * fnts + vmin)
        snowpack -= snow_melt

        # Total water output
        output[t] = np.sum(pl) + np.sum(snow_melt)

    return output


async def precompile_cemaneige() -> None:
    """Precompile CemaNeige model for faster first run."""
    run_cemaneige(
        np.array([1.0]),  # precipitation
        np.array([0.0]),  # temperature
        np.array([1]),  # day_of_year
        np.array([100.0, 200.0, 300.0]),  # altitude_layers
        200.0,  # median_altitude
        3,  # n_altitude_layers
        0.25,  # ctg
        3.74,  # kf
        0.0,  # beta
        0.1,  # vmin
        0.0,  # tf
        1.0,  # qnbv
        0.9,  # gthreshold
    )
