from typing import Any, TypedDict, assert_never, get_args

import holmes_rs

import holmes.model
from holmes.model import HydroModel, SnowModel

#########
# types #
#########


class ModelInfo(TypedDict):
    description: str
    parameters: list[str]


class ParamInfo(TypedDict):
    name: str
    description: str
    default: float
    min: float
    max: float


##########
# public #
##########


def get_model_info() -> dict[str, dict[str, ModelInfo]]:
    """Serve model and parameter descriptions for the UI."""
    return {
        "hydro": {m: _get_hydro_model_info(m) for m in get_args(HydroModel)},
        "snow": {m: _get_snow_model_info(m) for m in get_args(SnowModel)},
    }


def get_calibration_info() -> dict[str, Any]:
    """Serve per-model parameter bounds and algorithm settings for the UI."""
    return {
        "hydro": {m: _get_hydro_param_info(m) for m in get_args(HydroModel)},
        "algorithms": {
            a: holmes.model.get_config(a)
            for a in get_args(holmes.model.Algorithm)
        },
    }


###########
# private #
###########


def _get_hydro_model_info(model: HydroModel) -> ModelInfo:
    match model:
        case "gr4j":
            return {
                "description": (
                    "GR4J (Génie Rural à 4 paramètres Journalier) is a "
                    "parsimonious daily lumped rainfall-runoff model "
                    "developed at IRSTEA (formerly Cemagref) in France and "
                    "widely used in research and forecasting. It routes "
                    "water through a production store for soil moisture and "
                    "a routing store for baseflow, splitting flow between "
                    "fast and slow pathways with only four calibrated "
                    "parameters."
                ),
                "parameters": list(holmes_rs.hydro.gr4j.param_descriptions),
            }
        case "bucket":
            return {
                "description": (
                    "The bucket model is a conceptual rainfall-runoff model "
                    "built on the linear-reservoir framework, a tank-style "
                    "approach with deep roots in hydrology. It uses a soil "
                    "moisture store feeding two routing stores that produce "
                    "separate quickflow and baseflow components, with six "
                    "parameters offering more flexibility than simpler "
                    "models like GR4J."
                ),
                "parameters": list(holmes_rs.hydro.bucket.param_descriptions),
            }
        case "cequeau":
            return {
                "description": (
                    "CEQUEAU is a conceptual rainfall-runoff model "
                    "originally developed at INRS-Eau in Québec in the "
                    "1970s. This simplified nine-parameter variant drops the "
                    "original spatial distribution but keeps a two-store "
                    "framework -- a surface store for precipitation and "
                    "evapotranspiration and a groundwater store for delayed "
                    "baseflow -- connected by infiltration and followed by "
                    "pure time-delay routing."
                ),
                "parameters": list(holmes_rs.hydro.cequeau.param_descriptions),
            }
        case "crec":
            return {
                "description": (
                    "CREC is a six-parameter daily lumped rainfall-runoff "
                    "model developed at the Centre de Recherche en Eau de "
                    "Chatou in France for hydropower applications. Its "
                    "signature is a sigmoid function that smoothly partitions "
                    "rainfall between direct runoff and infiltration based on "
                    "soil moisture, combined with a nonlinear surface routing "
                    "store and a linear groundwater reservoir."
                ),
                "parameters": list(holmes_rs.hydro.crec.param_descriptions),
            }
        case "gardenia":
            return {
                "description": (
                    "GARDENIA is a six-parameter daily lumped "
                    "rainfall-runoff model developed at the Bureau de "
                    "Recherches Géologiques et Minières (BRGM), originally "
                    "for hydrogeological applications. It chains three "
                    "reservoirs -- a surface interception store, a soil store "
                    "with quadratic outflow, and a linearly draining "
                    "groundwater store -- with fractional-delay routing."
                ),
                "parameters": list(
                    holmes_rs.hydro.gardenia.param_descriptions
                ),
            }
        case "hbv":
            return {
                "description": (
                    "HBV is a nine-parameter daily lumped rainfall-runoff "
                    "model developed by Bergström and Forsman (1973) at the "
                    "Swedish Meteorological and Hydrological Institute "
                    "(SMHI). It combines a soil moisture store with nonlinear "
                    "runoff generation, an intermediate reservoir with fast "
                    "and slow outflows, a linear groundwater store for "
                    "baseflow, and triangular routing for channel travel "
                    "time."
                ),
                "parameters": list(holmes_rs.hydro.hbv.param_descriptions),
            }
        case "hymod":
            return {
                "description": (
                    "HYMOD is a six-parameter rainfall-runoff model "
                    "introduced by Boyle (2000) that uses a Pareto "
                    "distribution to represent spatially variable soil "
                    "storage capacity across the catchment. Runoff is routed "
                    "through a cascade of three linear reservoirs for fast "
                    "flow and a single slow groundwater store, staying "
                    "competitive with more complex models despite its "
                    "parsimony."
                ),
                "parameters": list(holmes_rs.hydro.hymod.param_descriptions),
            }
        case "ihacres":
            return {
                "description": (
                    "IHACRES (Identification of unit Hydrographs And "
                    "Component flows from Rainfall, Evaporation and "
                    "Streamflow data) is a seven-parameter daily lumped model "
                    "jointly developed at the UK Institute of Hydrology "
                    "(Wallingford) and the Australian National University in "
                    "the early 1990s. It separates a nonlinear moisture-loss "
                    "module from a linear routing module, using parallel fast "
                    "and slow stores in series with a pure delay."
                ),
                "parameters": list(holmes_rs.hydro.ihacres.param_descriptions),
            }
        case "martine":
            return {
                "description": (
                    "MARTINE is a seven-parameter daily rainfall-runoff "
                    "model developed by Mazenc, Sanchez, and Thiéry (1984) at "
                    "France's BRGM for regionalization studies. It combines "
                    "four reservoirs -- a surface store, a quadratic "
                    "direct-routing store, an intermediate store with linear "
                    "drainage and overflow, and a groundwater store -- with "
                    "fractional-delay routing at the outlet."
                ),
                "parameters": list(holmes_rs.hydro.martine.param_descriptions),
            }
        case "mohyse":
            return {
                "description": (
                    "MOHYSE is a deliberately minimalist daily lumped "
                    "rainfall-runoff model developed by Fortin and Turcotte "
                    "(2007) at Université Laval, Canada. It uses just two "
                    "reservoirs -- soil and groundwater -- linked by linear "
                    "drainage, with a gamma-shaped unit hydrograph "
                    "distributing flow in time, making it among the "
                    "structurally simplest models in its class."
                ),
                "parameters": list(holmes_rs.hydro.mohyse.param_descriptions),
            }
        case "mordor":
            return {
                "description": (
                    "MORDOR is a conceptual rainfall-runoff model developed "
                    "by Électricité de France for hydropower forecasting. It "
                    "cascades four reservoirs -- surface, intermediate, deep "
                    "soil, and groundwater -- that progressively filter "
                    "rainfall, with all flow components routed through a "
                    "shared double-sided unit hydrograph."
                ),
                "parameters": list(holmes_rs.hydro.mordor.param_descriptions),
            }
        case "nam":
            return {
                "description": (
                    "NAM (Nedbør-Afstrømnings-Model) is a daily "
                    "rainfall-runoff model developed by Nielsen and Hansen "
                    "(1973) at the Technical University of Denmark, using "
                    "several interconnected reservoirs. Its defining trait is "
                    "tracking groundwater as a deficit rather than a stored "
                    "volume, with explicit overland-flow and interflow "
                    "pathways each passed through parallel reservoir cascades "
                    "before fractional-delay routing."
                ),
                "parameters": list(holmes_rs.hydro.nam.param_descriptions),
            }
        case "pdm":
            return {
                "description": (
                    "PDM (Probability-Distributed Model) is an "
                    "eight-parameter daily lumped model developed by Moore "
                    "and Clarke (1981) and widely used in British operational "
                    "hydrology. Its core idea -- a Pareto distribution "
                    "representing spatially variable soil moisture capacity "
                    "-- influenced later models such as HYMOD and Xinanjiang; "
                    "runoff feeds a cubic groundwater store and two linear "
                    "fast reservoirs with fractional-delay routing."
                ),
                "parameters": list(holmes_rs.hydro.pdm.param_descriptions),
            }
        case "sacramento":
            return {
                "description": (
                    "SACRAMENTO is a simplified nine-parameter model "
                    "descended from the US National Weather Service's "
                    "operational SAC-SMA scheme, in use across US forecast "
                    "centres for decades. It organizes hydrology through "
                    "cascading reservoirs -- interception, upper-zone tension "
                    "and free water, lower-zone routing, and direct routing "
                    "-- linked by percolation, evaporation, and an upward "
                    "mass-balance correction."
                ),
                "parameters": list(
                    holmes_rs.hydro.sacramento.param_descriptions
                ),
            }
        case "simhyd":
            return {
                "description": (
                    "SIMHYD is an eight-parameter conceptual rainfall-runoff "
                    "model developed in Australia, using threshold-based, "
                    "exponentially decaying infiltration. It comprises an "
                    "interception store, a soil moisture store, and two "
                    "linear routing reservoirs (ground and main) connected by "
                    "a time-delay register, separating slow baseflow from "
                    "fast surface response."
                ),
                "parameters": list(holmes_rs.hydro.simhyd.param_descriptions),
            }
        case "smar":
            return {
                "description": (
                    "SMAR (Soil Moisture Accounting and Routing) is an "
                    "eight-parameter daily lumped model developed by "
                    "O'Connell, Nash, and Farrell at University College "
                    "Galway, Ireland, for operational forecasting. It "
                    "discretizes the soil into layers with exponentially "
                    "decaying evapotranspiration by depth, feeding two "
                    "parallel routing paths -- a linear groundwater reservoir "
                    "and a quadratic surface reservoir."
                ),
                "parameters": list(holmes_rs.hydro.smar.param_descriptions),
            }
        case "tank":
            return {
                "description": (
                    "TANK is a conceptual rainfall-runoff model developed by "
                    "Sugawara (1979) at Japan's National Research Center for "
                    "Disaster Prevention and widely used across East Asia. It "
                    "stacks four linear reservoirs -- surface, upper soil, "
                    "lower soil, and groundwater -- with threshold-based side "
                    "outlets on the surface store and fractional-delay "
                    "routing, naturally separating flow components across "
                    "timescales."
                ),
                "parameters": list(holmes_rs.hydro.tank.param_descriptions),
            }
        case "topmodel":
            return {
                "description": (
                    "TOPMODEL is a semi-distributed conceptual model "
                    "introduced by Beven and Kirkby (1979) that uses "
                    "topographic information to predict the distribution of "
                    "saturated areas. This simplified seven-parameter version "
                    "uses three reservoirs -- interception, an unbounded "
                    "groundwater deficit store, and a nonlinear surface "
                    "routing store -- connected by sigmoid partition "
                    "functions driven by catchment saturation."
                ),
                "parameters": list(
                    holmes_rs.hydro.topmodel.param_descriptions
                ),
            }
        case "wageningen":
            return {
                "description": (
                    "WAGENINGEN is an eight-parameter daily lumped "
                    "rainfall-runoff model developed by Warmerdam, Kole, and "
                    "Chormanski (1997) for humid-temperate catchments. It "
                    "uses three reservoirs -- a soil store governing "
                    "evapotranspiration and percolation, a slow store "
                    "allowing capillary rise, and a fast routing store -- in "
                    "a production-routing chain with a soil-moisture "
                    "threshold that switches between wet and dry regimes."
                ),
                "parameters": list(
                    holmes_rs.hydro.wageningen.param_descriptions
                ),
            }
        case "xinanjiang":
            return {
                "description": (
                    "The Xinanjiang model is a rainfall-runoff framework "
                    "developed in 1980 at Hohai University in China for humid "
                    "and semi-humid catchments. It places two "
                    "power-distributed storage reservoirs (soil and free "
                    "water) in series feeding parallel fast and slow linear "
                    "routing reservoirs, capturing spatial variability in "
                    "soil saturation through a saturation-excess runoff "
                    "mechanism."
                ),
                "parameters": list(
                    holmes_rs.hydro.xinanjiang.param_descriptions
                ),
            }
        case _:  # pragma: no cover
            assert_never(model)


def _get_snow_model_info(model: SnowModel) -> ModelInfo:
    match model:
        case "cemaneige":
            return {
                "description": (
                    "CemaNeige is a degree-day snow accounting model "
                    "developed alongside GR4J at IRSTEA (formerly Cemagref) "
                    "in France, tracking snow accumulation and melt across "
                    "elevation bands with just three parameters. It acts as a "
                    "preprocessor that converts precipitation and snowmelt "
                    "into effective precipitation for the hydrological model. "
                    "In this app its parameters are not calibrated but fixed "
                    "at defaults ([0.25, 3.74, qnbv], with qnbv derived from "
                    "the data)."
                ),
                # cemaneige has no `param_descriptions` in holmes_rs, so the
                # three parameters are documented here by hand
                "parameters": [
                    "Thermal state weighting coefficient controlling how "
                    "quickly the snowpack temperature responds to air "
                    "temperature (dimensionless)",
                    "Degree-day melt factor giving the melt rate per degree "
                    "above freezing (mm/°C/day)",
                    "Mean annual solid precipitation used as the snowpack "
                    "melt-efficiency threshold (mm)",
                ],
            }
        case _:  # pragma: no cover
            assert_never(model)


def _get_hydro_param_info(model: HydroModel) -> list[ParamInfo]:
    match model:
        case "gr4j":
            mod = holmes_rs.hydro.gr4j
        case "bucket":
            mod = holmes_rs.hydro.bucket
        case "cequeau":
            mod = holmes_rs.hydro.cequeau
        case "crec":
            mod = holmes_rs.hydro.crec
        case "gardenia":
            mod = holmes_rs.hydro.gardenia
        case "hbv":
            mod = holmes_rs.hydro.hbv
        case "hymod":
            mod = holmes_rs.hydro.hymod
        case "ihacres":
            mod = holmes_rs.hydro.ihacres
        case "martine":
            mod = holmes_rs.hydro.martine
        case "mohyse":
            mod = holmes_rs.hydro.mohyse
        case "mordor":
            mod = holmes_rs.hydro.mordor
        case "nam":
            mod = holmes_rs.hydro.nam
        case "pdm":
            mod = holmes_rs.hydro.pdm
        case "sacramento":
            mod = holmes_rs.hydro.sacramento
        case "simhyd":
            mod = holmes_rs.hydro.simhyd
        case "smar":
            mod = holmes_rs.hydro.smar
        case "tank":
            mod = holmes_rs.hydro.tank
        case "topmodel":
            mod = holmes_rs.hydro.topmodel
        case "wageningen":
            mod = holmes_rs.hydro.wageningen
        case "xinanjiang":
            mod = holmes_rs.hydro.xinanjiang
        case _:  # pragma: no cover
            assert_never(model)

    defaults, bounds = mod.init()
    return [
        {
            "name": name,
            "description": description,
            "default": float(default),
            "min": float(low),
            "max": float(high),
        }
        for name, description, default, (low, high) in zip(
            mod.param_names,
            mod.param_descriptions,
            defaults,
            bounds,
            strict=True,
        )
    ]
