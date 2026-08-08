from typing import Any, TypedDict, assert_never, get_args

import holmes_rs

import holmes.model
from holmes.model import HydroModel, SnowModel

#########
# types #
#########


class Text(TypedDict):
    en: str
    fr: str


class Texts(TypedDict):
    en: list[str]
    fr: list[str]


class ModelInfo(TypedDict):
    description: Text
    parameters: Texts


class ParamInfo(TypedDict):
    name: str
    description: Text
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
                "description": {
                    "en": (
                        "GR4J (Génie Rural à 4 paramètres Journalier) is a "
                        "parsimonious daily lumped rainfall-runoff model "
                        "developed at IRSTEA (formerly Cemagref) in France "
                        "and widely used in research and forecasting. It "
                        "routes water through a production store for soil "
                        "moisture and a routing store for baseflow, "
                        "splitting flow between fast and slow pathways with "
                        "only four calibrated parameters."
                    ),
                    "fr": (
                        "GR4J (Génie Rural à 4 paramètres Journalier) est "
                        "un modèle pluie-débit global journalier "
                        "parcimonieux développé à l'IRSTEA (anciennement "
                        "Cemagref) en France et largement utilisé en "
                        "recherche et en prévision. Il achemine l'eau à "
                        "travers un réservoir de production pour l'humidité "
                        "du sol et un réservoir de routage pour le débit de "
                        "base, en répartissant l'écoulement entre des voies "
                        "rapides et lentes avec seulement quatre paramètres "
                        "calés."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.gr4j),
            }
        case "bucket":
            return {
                "description": {
                    "en": (
                        "The bucket model is a conceptual rainfall-runoff "
                        "model built on the linear-reservoir framework, a "
                        "tank-style approach with deep roots in hydrology. "
                        "It uses a soil moisture store feeding two routing "
                        "stores that produce separate quickflow and "
                        "baseflow components, with six parameters offering "
                        "more flexibility than simpler models like GR4J."
                    ),
                    "fr": (
                        "Le modèle bucket est un modèle pluie-débit "
                        "conceptuel fondé sur le cadre des réservoirs "
                        "linéaires, une approche de type tank profondément "
                        "enracinée en hydrologie. Il utilise un réservoir "
                        "d'humidité du sol alimentant deux réservoirs de "
                        "routage qui produisent des composantes distinctes "
                        "d'écoulement rapide et de débit de base, avec six "
                        "paramètres offrant plus de souplesse que des "
                        "modèles plus simples comme GR4J."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.bucket),
            }
        case "cequeau":
            return {
                "description": {
                    "en": (
                        "CEQUEAU is a conceptual rainfall-runoff model "
                        "originally developed at INRS-Eau in Québec in the "
                        "1970s. This simplified nine-parameter variant "
                        "drops the original spatial distribution but keeps "
                        "a two-store framework -- a surface store for "
                        "precipitation and evapotranspiration and a "
                        "groundwater store for delayed baseflow -- "
                        "connected by infiltration and followed by pure "
                        "time-delay routing."
                    ),
                    "fr": (
                        "CEQUEAU est un modèle pluie-débit conceptuel "
                        "développé à l'origine à l'INRS-Eau au Québec dans "
                        "les années 1970. Cette variante simplifiée à neuf "
                        "paramètres abandonne la distribution spatiale "
                        "d'origine mais conserve un cadre à deux réservoirs "
                        "-- un réservoir de surface pour les précipitations "
                        "et l'évapotranspiration et un réservoir souterrain "
                        "pour le débit de base différé -- reliés par "
                        "l'infiltration et suivis d'un routage par délai "
                        "pur."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.cequeau),
            }
        case "crec":
            return {
                "description": {
                    "en": (
                        "CREC is a six-parameter daily lumped "
                        "rainfall-runoff model developed at the Centre de "
                        "Recherche en Eau de Chatou in France for "
                        "hydropower applications. Its signature is a "
                        "sigmoid function that smoothly partitions rainfall "
                        "between direct runoff and infiltration based on "
                        "soil moisture, combined with a nonlinear surface "
                        "routing store and a linear groundwater reservoir."
                    ),
                    "fr": (
                        "CREC est un modèle pluie-débit global journalier à "
                        "six paramètres développé au Centre de Recherche en "
                        "Eau de Chatou en France pour des applications "
                        "hydroélectriques. Sa signature est une fonction "
                        "sigmoïde qui répartit progressivement la pluie "
                        "entre ruissellement direct et infiltration selon "
                        "l'humidité du sol, combinée à un réservoir de "
                        "routage de surface non linéaire et à un réservoir "
                        "souterrain linéaire."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.crec),
            }
        case "gardenia":
            return {
                "description": {
                    "en": (
                        "GARDENIA is a six-parameter daily lumped "
                        "rainfall-runoff model developed at the Bureau de "
                        "Recherches Géologiques et Minières (BRGM), "
                        "originally for hydrogeological applications. It "
                        "chains three reservoirs -- a surface interception "
                        "store, a soil store with quadratic outflow, and a "
                        "linearly draining groundwater store -- with "
                        "fractional-delay routing."
                    ),
                    "fr": (
                        "GARDENIA est un modèle pluie-débit global "
                        "journalier à six paramètres développé au Bureau de "
                        "Recherches Géologiques et Minières (BRGM), à "
                        "l'origine pour des applications hydrogéologiques. "
                        "Il enchaîne trois réservoirs -- un réservoir "
                        "d'interception de surface, un réservoir de sol à "
                        "vidange quadratique et un réservoir souterrain à "
                        "vidange linéaire -- avec un routage à délai "
                        "fractionnaire."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.gardenia),
            }
        case "hbv":
            return {
                "description": {
                    "en": (
                        "HBV is a nine-parameter daily lumped "
                        "rainfall-runoff model developed by Bergström and "
                        "Forsman (1973) at the Swedish Meteorological and "
                        "Hydrological Institute (SMHI). It combines a soil "
                        "moisture store with nonlinear runoff generation, "
                        "an intermediate reservoir with fast and slow "
                        "outflows, a linear groundwater store for baseflow, "
                        "and triangular routing for channel travel time."
                    ),
                    "fr": (
                        "HBV est un modèle pluie-débit global journalier à "
                        "neuf paramètres développé par Bergström et Forsman "
                        "(1973) à l'Institut suédois de météorologie et "
                        "d'hydrologie (SMHI). Il combine un réservoir "
                        "d'humidité du sol à génération de ruissellement "
                        "non linéaire, un réservoir intermédiaire à "
                        "vidanges rapide et lente, un réservoir souterrain "
                        "linéaire pour le débit de base et un routage "
                        "triangulaire pour le temps de parcours en rivière."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.hbv),
            }
        case "hymod":
            return {
                "description": {
                    "en": (
                        "HYMOD is a six-parameter rainfall-runoff model "
                        "introduced by Boyle (2000) that uses a Pareto "
                        "distribution to represent spatially variable soil "
                        "storage capacity across the catchment. Runoff is "
                        "routed through a cascade of three linear "
                        "reservoirs for fast flow and a single slow "
                        "groundwater store, staying competitive with more "
                        "complex models despite its parsimony."
                    ),
                    "fr": (
                        "HYMOD est un modèle pluie-débit à six paramètres "
                        "introduit par Boyle (2000) qui utilise une "
                        "distribution de Pareto pour représenter la "
                        "variabilité spatiale de la capacité de stockage du "
                        "sol sur le bassin. Le ruissellement est acheminé à "
                        "travers une cascade de trois réservoirs linéaires "
                        "pour l'écoulement rapide et un unique réservoir "
                        "souterrain lent, restant compétitif avec des "
                        "modèles plus complexes malgré sa parcimonie."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.hymod),
            }
        case "ihacres":
            return {
                "description": {
                    "en": (
                        "IHACRES (Identification of unit Hydrographs And "
                        "Component flows from Rainfall, Evaporation and "
                        "Streamflow data) is a seven-parameter daily lumped "
                        "model jointly developed at the UK Institute of "
                        "Hydrology (Wallingford) and the Australian "
                        "National University in the early 1990s. It "
                        "separates a nonlinear moisture-loss module from a "
                        "linear routing module, using parallel fast and "
                        "slow stores in series with a pure delay."
                    ),
                    "fr": (
                        "IHACRES (Identification of unit Hydrographs And "
                        "Component flows from Rainfall, Evaporation and "
                        "Streamflow data) est un modèle global journalier à "
                        "sept paramètres développé conjointement par "
                        "l'Institute of Hydrology britannique (Wallingford) "
                        "et l'Australian National University au début des "
                        "années 1990. Il sépare un module non linéaire de "
                        "perte d'humidité d'un module de routage linéaire, "
                        "avec des réservoirs rapide et lent en parallèle "
                        "suivis d'un délai pur."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.ihacres),
            }
        case "martine":
            return {
                "description": {
                    "en": (
                        "MARTINE is a seven-parameter daily rainfall-runoff "
                        "model developed by Mazenc, Sanchez, and Thiéry "
                        "(1984) at France's BRGM for regionalization "
                        "studies. It combines four reservoirs -- a surface "
                        "store, a quadratic direct-routing store, an "
                        "intermediate store with linear drainage and "
                        "overflow, and a groundwater store -- with "
                        "fractional-delay routing at the outlet."
                    ),
                    "fr": (
                        "MARTINE est un modèle pluie-débit journalier à "
                        "sept paramètres développé par Mazenc, Sanchez et "
                        "Thiéry (1984) au BRGM en France pour des études de "
                        "régionalisation. Il combine quatre réservoirs -- "
                        "un réservoir de surface, un réservoir de routage "
                        "direct quadratique, un réservoir intermédiaire à "
                        "drainage linéaire et débordement, et un réservoir "
                        "souterrain -- avec un routage à délai "
                        "fractionnaire à l'exutoire."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.martine),
            }
        case "mohyse":
            return {
                "description": {
                    "en": (
                        "MOHYSE is a deliberately minimalist daily lumped "
                        "rainfall-runoff model developed by Fortin and "
                        "Turcotte (2007) at Université Laval, Canada. It "
                        "uses just two reservoirs -- soil and groundwater "
                        "-- linked by linear drainage, with a gamma-shaped "
                        "unit hydrograph distributing flow in time, making "
                        "it among the structurally simplest models in its "
                        "class."
                    ),
                    "fr": (
                        "MOHYSE est un modèle pluie-débit global journalier "
                        "délibérément minimaliste développé par Fortin et "
                        "Turcotte (2007) à l'Université Laval, au Canada. "
                        "Il n'utilise que deux réservoirs -- sol et "
                        "souterrain -- reliés par un drainage linéaire, "
                        "avec un hydrogramme unitaire en forme de loi gamma "
                        "répartissant l'écoulement dans le temps, ce qui en "
                        "fait l'un des modèles structurellement les plus "
                        "simples de sa catégorie."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.mohyse),
            }
        case "mordor":
            return {
                "description": {
                    "en": (
                        "MORDOR is a conceptual rainfall-runoff model "
                        "developed by Électricité de France for hydropower "
                        "forecasting. It cascades four reservoirs -- "
                        "surface, intermediate, deep soil, and groundwater "
                        "-- that progressively filter rainfall, with all "
                        "flow components routed through a shared "
                        "double-sided unit hydrograph."
                    ),
                    "fr": (
                        "MORDOR est un modèle pluie-débit conceptuel "
                        "développé par Électricité de France pour la "
                        "prévision hydroélectrique. Il met en cascade "
                        "quatre réservoirs -- surface, intermédiaire, sol "
                        "profond et souterrain -- qui filtrent "
                        "progressivement la pluie, toutes les composantes "
                        "d'écoulement étant acheminées par un hydrogramme "
                        "unitaire bilatéral partagé."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.mordor),
            }
        case "nam":
            return {
                "description": {
                    "en": (
                        "NAM (Nedbør-Afstrømnings-Model) is a daily "
                        "rainfall-runoff model developed by Nielsen and "
                        "Hansen (1973) at the Technical University of "
                        "Denmark, using several interconnected reservoirs. "
                        "Its defining trait is tracking groundwater as a "
                        "deficit rather than a stored volume, with explicit "
                        "overland-flow and interflow pathways each passed "
                        "through parallel reservoir cascades before "
                        "fractional-delay routing."
                    ),
                    "fr": (
                        "NAM (Nedbør-Afstrømnings-Model) est un modèle "
                        "pluie-débit journalier développé par Nielsen et "
                        "Hansen (1973) à l'Université technique du "
                        "Danemark, utilisant plusieurs réservoirs "
                        "interconnectés. Son trait distinctif est de suivre "
                        "la nappe comme un déficit plutôt que comme un "
                        "volume stocké, avec des voies explicites de "
                        "ruissellement de surface et d'écoulement "
                        "hypodermique passant chacune par des cascades de "
                        "réservoirs parallèles avant un routage à délai "
                        "fractionnaire."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.nam),
            }
        case "pdm":
            return {
                "description": {
                    "en": (
                        "PDM (Probability-Distributed Model) is an "
                        "eight-parameter daily lumped model developed by "
                        "Moore and Clarke (1981) and widely used in British "
                        "operational hydrology. Its core idea -- a Pareto "
                        "distribution representing spatially variable soil "
                        "moisture capacity -- influenced later models such "
                        "as HYMOD and Xinanjiang; runoff feeds a cubic "
                        "groundwater store and two linear fast reservoirs "
                        "with fractional-delay routing."
                    ),
                    "fr": (
                        "PDM (Probability-Distributed Model) est un modèle "
                        "global journalier à huit paramètres développé par "
                        "Moore et Clarke (1981) et largement utilisé en "
                        "hydrologie opérationnelle britannique. Son idée "
                        "centrale -- une distribution de Pareto "
                        "représentant la variabilité spatiale de la "
                        "capacité en eau du sol -- a influencé des modèles "
                        "ultérieurs comme HYMOD et Xinanjiang; le "
                        "ruissellement alimente un réservoir souterrain "
                        "cubique et deux réservoirs rapides linéaires avec "
                        "un routage à délai fractionnaire."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.pdm),
            }
        case "sacramento":
            return {
                "description": {
                    "en": (
                        "SACRAMENTO is a simplified nine-parameter model "
                        "descended from the US National Weather Service's "
                        "operational SAC-SMA scheme, in use across US "
                        "forecast centres for decades. It organizes "
                        "hydrology through cascading reservoirs -- "
                        "interception, upper-zone tension and free water, "
                        "lower-zone routing, and direct routing -- linked "
                        "by percolation, evaporation, and an upward "
                        "mass-balance correction."
                    ),
                    "fr": (
                        "SACRAMENTO est un modèle simplifié à neuf "
                        "paramètres issu du schéma opérationnel SAC-SMA du "
                        "National Weather Service américain, en service "
                        "dans les centres de prévision américains depuis "
                        "des décennies. Il organise l'hydrologie en "
                        "réservoirs en cascade -- interception, eau de "
                        "tension et eau libre de la zone supérieure, "
                        "routage de la zone inférieure et routage direct -- "
                        "reliés par la percolation, l'évaporation et une "
                        "correction ascendante du bilan de masse."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.sacramento),
            }
        case "simhyd":
            return {
                "description": {
                    "en": (
                        "SIMHYD is an eight-parameter conceptual "
                        "rainfall-runoff model developed in Australia, "
                        "using threshold-based, exponentially decaying "
                        "infiltration. It comprises an interception store, "
                        "a soil moisture store, and two linear routing "
                        "reservoirs (ground and main) connected by a "
                        "time-delay register, separating slow baseflow from "
                        "fast surface response."
                    ),
                    "fr": (
                        "SIMHYD est un modèle pluie-débit conceptuel à huit "
                        "paramètres développé en Australie, utilisant une "
                        "infiltration à seuil à décroissance exponentielle. "
                        "Il comprend un réservoir d'interception, un "
                        "réservoir d'humidité du sol et deux réservoirs de "
                        "routage linéaires (souterrain et principal) reliés "
                        "par un registre à délai, séparant le débit de base "
                        "lent de la réponse rapide de surface."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.simhyd),
            }
        case "smar":
            return {
                "description": {
                    "en": (
                        "SMAR (Soil Moisture Accounting and Routing) is an "
                        "eight-parameter daily lumped model developed by "
                        "O'Connell, Nash, and Farrell at University College "
                        "Galway, Ireland, for operational forecasting. It "
                        "discretizes the soil into layers with "
                        "exponentially decaying evapotranspiration by "
                        "depth, feeding two parallel routing paths -- a "
                        "linear groundwater reservoir and a quadratic "
                        "surface reservoir."
                    ),
                    "fr": (
                        "SMAR (Soil Moisture Accounting and Routing) est un "
                        "modèle global journalier à huit paramètres "
                        "développé par O'Connell, Nash et Farrell à "
                        "l'University College Galway, en Irlande, pour la "
                        "prévision opérationnelle. Il discrétise le sol en "
                        "couches avec une évapotranspiration décroissant "
                        "exponentiellement avec la profondeur, alimentant "
                        "deux chemins de routage parallèles -- un réservoir "
                        "souterrain linéaire et un réservoir de surface "
                        "quadratique."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.smar),
            }
        case "tank":
            return {
                "description": {
                    "en": (
                        "TANK is a conceptual rainfall-runoff model "
                        "developed by Sugawara (1979) at Japan's National "
                        "Research Center for Disaster Prevention and widely "
                        "used across East Asia. It stacks four linear "
                        "reservoirs -- surface, upper soil, lower soil, and "
                        "groundwater -- with threshold-based side outlets "
                        "on the surface store and fractional-delay routing, "
                        "naturally separating flow components across "
                        "timescales."
                    ),
                    "fr": (
                        "TANK est un modèle pluie-débit conceptuel "
                        "développé par Sugawara (1979) au National Research "
                        "Center for Disaster Prevention du Japon et "
                        "largement utilisé en Asie de l'Est. Il empile "
                        "quatre réservoirs linéaires -- surface, sol "
                        "supérieur, sol inférieur et souterrain -- avec des "
                        "sorties latérales à seuil sur le réservoir de "
                        "surface et un routage à délai fractionnaire, "
                        "séparant naturellement les composantes "
                        "d'écoulement selon leurs échelles de temps."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.tank),
            }
        case "topmodel":
            return {
                "description": {
                    "en": (
                        "TOPMODEL is a semi-distributed conceptual model "
                        "introduced by Beven and Kirkby (1979) that uses "
                        "topographic information to predict the "
                        "distribution of saturated areas. This simplified "
                        "seven-parameter version uses three reservoirs -- "
                        "interception, an unbounded groundwater deficit "
                        "store, and a nonlinear surface routing store -- "
                        "connected by sigmoid partition functions driven by "
                        "catchment saturation."
                    ),
                    "fr": (
                        "TOPMODEL est un modèle conceptuel semi-distribué "
                        "introduit par Beven et Kirkby (1979) qui utilise "
                        "l'information topographique pour prédire la "
                        "distribution des zones saturées. Cette version "
                        "simplifiée à sept paramètres utilise trois "
                        "réservoirs -- interception, un réservoir de "
                        "déficit souterrain non borné et un réservoir de "
                        "routage de surface non linéaire -- reliés par des "
                        "fonctions de partage sigmoïdes pilotées par la "
                        "saturation du bassin."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.topmodel),
            }
        case "wageningen":
            return {
                "description": {
                    "en": (
                        "WAGENINGEN is an eight-parameter daily lumped "
                        "rainfall-runoff model developed by Warmerdam, "
                        "Kole, and Chormanski (1997) for humid-temperate "
                        "catchments. It uses three reservoirs -- a soil "
                        "store governing evapotranspiration and "
                        "percolation, a slow store allowing capillary rise, "
                        "and a fast routing store -- in a "
                        "production-routing chain with a soil-moisture "
                        "threshold that switches between wet and dry "
                        "regimes."
                    ),
                    "fr": (
                        "WAGENINGEN est un modèle pluie-débit global "
                        "journalier à huit paramètres développé par "
                        "Warmerdam, Kole et Chormanski (1997) pour les "
                        "bassins humides tempérés. Il utilise trois "
                        "réservoirs -- un réservoir de sol régissant "
                        "l'évapotranspiration et la percolation, un "
                        "réservoir lent permettant la remontée capillaire "
                        "et un réservoir de routage rapide -- dans une "
                        "chaîne production-routage avec un seuil d'humidité "
                        "du sol qui bascule entre régimes humide et sec."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.wageningen),
            }
        case "xinanjiang":
            return {
                "description": {
                    "en": (
                        "The Xinanjiang model is a rainfall-runoff "
                        "framework developed in 1980 at Hohai University in "
                        "China for humid and semi-humid catchments. It "
                        "places two power-distributed storage reservoirs "
                        "(soil and free water) in series feeding parallel "
                        "fast and slow linear routing reservoirs, capturing "
                        "spatial variability in soil saturation through a "
                        "saturation-excess runoff mechanism."
                    ),
                    "fr": (
                        "Le modèle Xinanjiang est un cadre pluie-débit "
                        "développé en 1980 à l'Université Hohai en Chine "
                        "pour les bassins humides et semi-humides. Il place "
                        "deux réservoirs de stockage à distribution en "
                        "puissance (sol et eau libre) en série alimentant "
                        "des réservoirs de routage linéaires rapide et lent "
                        "en parallèle, capturant la variabilité spatiale de "
                        "la saturation du sol par un mécanisme de "
                        "ruissellement par excès de saturation."
                    ),
                },
                "parameters": _param_texts(holmes_rs.hydro.xinanjiang),
            }
        case _:  # pragma: no cover
            assert_never(model)


def _get_snow_model_info(model: SnowModel) -> ModelInfo:
    match model:
        case "cemaneige":
            return {
                "description": {
                    "en": (
                        "CemaNeige is a degree-day snow accounting model "
                        "developed alongside GR4J at IRSTEA (formerly "
                        "Cemagref) in France, tracking snow accumulation "
                        "and melt across elevation bands with just three "
                        "parameters. It acts as a preprocessor that "
                        "converts precipitation and snowmelt into effective "
                        "precipitation for the hydrological model. In this "
                        "app its parameters are not calibrated but fixed at "
                        "defaults ([0.25, 3.74, qnbv], with qnbv derived "
                        "from the data)."
                    ),
                    "fr": (
                        "CemaNeige est un modèle degré-jour de suivi du "
                        "manteau neigeux développé aux côtés de GR4J à "
                        "l'IRSTEA (anciennement Cemagref) en France, "
                        "suivant l'accumulation et la fonte de la neige par "
                        "bandes d'altitude avec seulement trois paramètres. "
                        "Il agit comme un prétraitement qui convertit les "
                        "précipitations et la fonte en précipitations "
                        "efficaces pour le modèle hydrologique. Dans cette "
                        "application, ses paramètres ne sont pas calés mais "
                        "fixés aux valeurs par défaut ([0.25, 3.74, qnbv], "
                        "qnbv étant dérivé des données)."
                    ),
                },
                # cemaneige has no `param_descriptions` in holmes_rs, so the
                # three parameters are documented here by hand
                "parameters": {
                    "en": [
                        "Thermal state weighting coefficient controlling "
                        "how quickly the snowpack temperature responds to "
                        "air temperature (dimensionless)",
                        "Degree-day melt factor giving the melt rate per "
                        "degree above freezing (mm/°C/day)",
                        "Mean annual solid precipitation used as the "
                        "snowpack melt-efficiency threshold (mm)",
                    ],
                    "fr": [
                        "Coefficient de pondération de l'état thermique "
                        "contrôlant la vitesse à laquelle la température du "
                        "manteau neigeux répond à la température de l'air "
                        "(dimensionless)",
                        "Facteur de fonte degré-jour donnant le taux de "
                        "fonte par degré au-dessus du point de congélation "
                        "(mm/°C/day)",
                        "Précipitation solide annuelle moyenne servant de "
                        "seuil d'efficacité de fonte du manteau neigeux "
                        "(mm)",
                    ],
                },
            }
        case _:  # pragma: no cover
            assert_never(model)


def _param_texts(mod: Any) -> Texts:
    return {
        "en": list(mod.param_descriptions),
        "fr": list(mod.param_descriptions_fr),
    }


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
            "description": {"en": description, "fr": description_fr},
            "default": float(default),
            "min": float(low),
            "max": float(high),
        }
        for name, description, description_fr, default, (low, high) in zip(
            mod.param_names,
            mod.param_descriptions,
            mod.param_descriptions_fr,
            defaults,
            bounds,
            strict=True,
        )
    ]
