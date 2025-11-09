import math

import numba
import numpy as np

##########
# public #
##########


@numba.jit(nopython=True, cache=True)
def run_oudin(
    temperature: np.ndarray,
    day_of_year: np.ndarray,
    latitude: float,
) -> np.ndarray:
    """
    Calculate potential evapotranspiration using Oudin formula.

    Parameters:
        temperature: Daily air temperature (°C)
        day_of_year: Day of year (1-366)
        latitude: Catchment latitude (degrees)

    Returns:
        Array of potential evapotranspiration (mm/day)
    """
    n_timesteps = temperature.shape[0]
    pet = np.zeros(n_timesteps)

    # Constants
    gsc = 0.082  # Solar constant (MJ m-2 min-1)
    rho = 1000  # Water density (kg/m3)

    # Convert latitude to radians
    lat_rad = (math.pi * latitude) / 180

    for t in range(n_timesteps):
        # Latent heat of vaporization (MJ/kg)
        lambda_val = 2.501 - 0.002361 * temperature[t]

        # Day of year
        doy = day_of_year[t]

        # Solar declination (radians)
        ds = 0.409 * math.sin(((2 * math.pi) / 365) * doy - 1.39)

        # Inverse relative distance Earth-Sun
        dr = 1 + 0.033 * math.cos((doy * 2 * math.pi) / 365)

        # Sunset hour angle (radians)
        tmp = (-math.tan(lat_rad)) * math.tan(ds)
        # Clip to valid range for arccos
        tmp = max(-1.0, min(1.0, tmp))
        omega = math.acos(tmp)

        # Extraterrestrial radiation (MJ m-2 day-1)
        re = (
            ((24 * 60) / math.pi)
            * gsc
            * dr
            * (
                omega * math.sin(lat_rad) * math.sin(ds)
                + math.cos(lat_rad) * math.cos(ds) * math.sin(omega)
            )
        )

        # Potential evapotranspiration (mm/day)
        pet[t] = (re / (lambda_val * rho)) * ((temperature[t] + 5) / 100)
        pet[t] *= 1000  # Convert to mm/day
        pet[t] = max(0, pet[t])  # Cannot be negative

    return pet


async def precompile_oudin() -> None:
    """Precompile Oudin model for faster first run."""
    run_oudin(
        np.array([10.0]),
        np.array([180]),
        45.0,
    )
