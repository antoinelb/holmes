# Projection

L'étape Projection alimente les modèles calés avec des ensembles de modèles climatiques plutôt qu'avec la météo passée, projetant le régime d'écoulement de la station de simulation sur les décennies à venir (2020–2099).
Comme la Simulation, elle se déverrouille une fois que le calage a produit des paramètres et se calcule automatiquement à l'ouverture.

![Vue d'ensemble de l'étape Projection](../assets/images/screenshots/projection-overview-fr-dark.png#only-dark)
![Vue d'ensemble de l'étape Projection](../assets/images/screenshots/projection-overview-fr-light.png#only-light)

## Contrôles

![Contrôles de l'étape Projection](../assets/images/screenshots/projection-controls-fr-dark.png#only-dark)
![Contrôles de l'étape Projection](../assets/images/screenshots/projection-controls-fr-light.png#only-light)

- **"Modèle climatique"** — l'ensemble de forçage :
  **"ClimEx (CRCM5)"**, un ensemble de 50 membres à modèle unique dont la dispersion reflète la variabilité naturelle du climat; ou
  **"ESPO-G6-R2 (CMIP6)"**, un ensemble CMIP6 multi-modèles corrigé de biais dont la dispersion reflète aussi le désaccord entre modèles.
- **"Scénario"** — la trajectoire d'émissions; ClimEx offre RCP8.5, ESPO-G6-R2 offre SSP2-4.5 et SSP3-7.0.
  Chaque bouton affiche le nombre de membres.
- **"Horizon"** — la fenêtre de 30 ans : 2020–2049, 2040–2069 ou 2070–2099.
- Une ligne par modèle hydrologique; le survol le met en évidence dans les graphiques (pas de pastille de métrique — il n'y a pas d'observations dans le futur auxquelles se comparer).
- **"Exporter"** — trois fichiers nommés `projection_<station>_<climate model>_<scenario>_<horizon>` : un `.json` (la configuration, les paramètres, les indicateurs médians), un `_regime.csv` (le régime par jour de l'année par modèle) et un `_indicators.csv` (une ligne par modèle et membre).

Changer l'un des trois réglages recharge et redessine :

![Un autre ensemble, scénario et horizon](../assets/images/screenshots/projection-variant-fr-dark.png#only-dark)
![Un autre ensemble, scénario et horizon](../assets/images/screenshots/projection-variant-fr-light.png#only-light)

## Le graphique de régime

Le graphique du haut est le **régime annuel d'écoulement** : le débit moyen (mm/jour) par jour de l'année sur l'horizon.

- une ligne fine par membre climatique — la dispersion de l'ensemble;
- une médiane par modèle hydrologique (affichée pour les ensembles de modèles);
- la **médiane** globale par-dessus;
- une référence **historique** verte en tireté : les mêmes modèles exécutés sur la météo observée pendant la période de simulation, de sorte que le changement de régime — fonte plus précoce, chronologie des crues différente — se lit directement contre le passé.

## Le graphique des indicateurs

Le graphique du bas condense le régime de chaque membre en cinq indicateurs — **"Min hiver"**, **"Max printemps"**, **"Min été"**, **"Max automne"** et **"Moyenne"** — avec un point par modèle et membre, un trait plein pour la médiane et un trait historique en tireté par colonne (l'axe se coupe pour que les petits et les grands indicateurs restent lisibles).
Il répond directement aux questions opérationnelles : de combien la crue printanière se déplace, jusqu'où descendent les étiages d'hiver et d'été, et comment le bilan moyen change.
