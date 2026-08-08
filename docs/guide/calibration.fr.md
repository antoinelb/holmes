# Calage

L'étape Calage ajuste les paramètres des modèles sélectionnés au débit observé de la station de calage sur la période de calage — à la main, ou avec l'algorithme d'optimisation SCE-UA.

![Vue d'ensemble de l'étape Calage](../assets/images/screenshots/calibration-overview-fr-dark.png#only-dark)
![Vue d'ensemble de l'étape Calage](../assets/images/screenshots/calibration-overview-fr-light.png#only-light)

## Réglages

- **"Objectif"** — le score optimisé : RMSE, NSE ou KGE (voir [Métriques](../concepts/metrics.md)).
  Le RMSE est minimisé vers 0; le NSE et le KGE sont maximisés vers 1.
- **"Transformation"** — Aucune, Log ou Sqrt, appliquée aux débits observés et simulés avant le calcul de l'objectif.
  Une transformation logarithmique met l'accent sur les étiages; aucune transformation met l'accent sur les crues.
- **"Algorithme"** — **Manuel** (vous déplacez les curseurs) ou **SCE** (optimisation automatique; voir [Algorithmes de calage](../concepts/calibration-algorithms.md)).
- **"Années d'initialisation"** (0–5, 3 par défaut) — des années *ajoutées avant* la période de calage pour laisser les réservoirs internes du modèle se remplir depuis leur état initial arbitraire.
  Toute la période sélectionnée est évaluée; seules les années ajoutées sont exclues de l'objectif.
  L'initialisation apparaît comme une bande ombrée à gauche du graphique de débit.

Changer la transformation ou l'initialisation supprime l'historique des tentatives, puisque des scores calculés sous des réglages différents ne sont pas comparables.

## Calage manuel

Avec **"Algorithme" : Manuel**, ouvrez la section d'un modèle pour révéler un curseur par paramètre, borné par la plage plausible de ce paramètre (en échelle logarithmique quand la plage couvre plusieurs ordres de grandeur).

![Curseurs de paramètres](../assets/images/screenshots/calibration-sliders-fr-dark.png#only-dark)
![Curseurs de paramètres](../assets/images/screenshots/calibration-sliders-fr-light.png#only-light)

Chaque relâchement de curseur (ou valeur saisie) re-simule immédiatement le modèle : la pastille d'objectif à côté du nom du modèle se met à jour, la courbe simulée se redessine et un nouveau point s'ajoute au graphique d'objectif — votre trajectoire de calage.
Surveillez le graphique de débit en itérant : deux jeux de paramètres peuvent obtenir des scores similaires tout en échouant sur des parties différentes de l'hydrogramme ([zoomez](index.md#manipuler-les-graphiques) pour inspecter les crues ou les récessions).

## Calage automatique (SCE)

Avec **"Algorithme" : SCE**, la section repliable **"Réglages de l'algorithme"** expose les hyperparamètres de l'optimiseur — notamment `max_evaluations` (le budget de l'exécution en évaluations de modèle) et `seed` (fixée par défaut, pour qu'une exécution soit reproductible).

![Réglages SCE](../assets/images/screenshots/calibration-sce-settings-fr-dark.png#only-dark)
![Réglages SCE](../assets/images/screenshots/calibration-sce-settings-fr-light.png#only-light)

**"Caler"** lance une exécution sur chaque modèle sélectionné.
Pendant l'exécution, les réglages et les curseurs se verrouillent, les curseurs s'animent vers les valeurs de paramètres explorées et le bouton devient **"Arrêter"** (chaque modèle a aussi son propre bouton d'arrêt).
Arrêter conserve les meilleurs paramètres trouvés jusque-là.

![Résultat SCE](../assets/images/screenshots/calibration-sce-result-fr-dark.png#only-dark)
![Résultat SCE](../assets/images/screenshots/calibration-sce-result-fr-light.png#only-light)

## Graphiques

- Le **graphique d'objectif** (en haut) trace le score de chaque tentative — mouvements manuels comme exécutions SCE — par modèle, avec la médiane par-dessus pour les ensembles et une ligne de référence **"Optimal"** en tireté (0 pour le RMSE, 1 pour le NSE/KGE).

![Convergence de l'objectif](../assets/images/screenshots/calibration-objective-fr-dark.png#only-dark)
![Convergence de l'objectif](../assets/images/screenshots/calibration-objective-fr-light.png#only-light)

- Le **graphique de débit** (en bas) superpose les observations et la simulation courante de chaque modèle, avec la bande d'initialisation à gauche.
  Survoler la section d'un modèle met sa courbe en évidence dans les deux graphiques.

![Débits observé et simulés](../assets/images/screenshots/calibration-streamflow-fr-dark.png#only-dark)
![Débits observé et simulés](../assets/images/screenshots/calibration-streamflow-fr-light.png#only-light)

## L'étape se complète d'elle-même

Dès que chaque modèle sélectionné a au moins une tentative, les paramètres calés sont enregistrés et les étapes Simulation et Projection se déverrouillent.
Changer quoi que ce soit en amont — station, période, méthode météo, modèles, modèle de neige — ou la transformation ou l'initialisation supprime ces paramètres et les reverrouille.

**"Effacer"** (en haut à droite de la carte) réinitialise les curseurs aux valeurs par défaut et efface l'historique des tentatives, en conservant les réglages.

## Exporter et importer

**"Exporter"** télécharge deux fichiers nommés d'après la station et la période :

- `calibration_<station>_<start>_<end>.json` — la configuration complète, les paramètres ajustés de chaque modèle et l'historique complet des tentatives;
- `calibration_<station>_<start>_<end>.csv` — les séries simulées (`datetime,observations,<model…>` plus `median` pour les ensembles).

**"Importer"** restaure un `.json` exporté.
Le fichier est d'abord validé; si sa configuration diffère de la configuration courante, un dialogue liste chaque différence (station, période, méthode météo, modèle de neige, modèles…) et demande confirmation avant de remplacer :

![Dialogue de configuration à l'importation](../assets/images/screenshots/calibration-import-dialog-fr-dark.png#only-dark)
![Dialogue de configuration à l'importation](../assets/images/screenshots/calibration-import-dialog-fr-light.png#only-light)

**"Remplacer"** restaure le contexte exporté — stations, périodes, météo, modèles, paramètres ajustés et historique — exactement tel qu'exporté; **"Annuler"** garde tout en l'état.
Puisque le stockage du navigateur ne conserve que le dernier état, l'exportation est le moyen de garder plusieurs calages (un fichier par configuration, comme dans un exercice en échantillons distincts ou par bassin substitut) et d'y revenir plus tard.
