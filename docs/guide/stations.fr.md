# Stations

L'étape Stations choisit les stations hydrométriques — et donc les bassins versants — sur lesquels travaille tout le pipeline, ainsi que leurs périodes.

![Vue d'ensemble de l'étape Stations](../assets/images/screenshots/stations-overview-fr-dark.png#only-dark)
![Vue d'ensemble de l'étape Stations](../assets/images/screenshots/stations-overview-fr-light.png#only-light)

## Rôles : calage et simulation

HOLMES suit toujours deux stations, une par rôle :

- La **station de calage** (violet) fournit le débit observé auquel les modèles sont ajustés.
- La **station de simulation** (vert) est celle où les paramètres calés sont évalués.

Utiliser la *même* station avec des périodes *différentes* donne un test en échantillons distincts (split-sample); utiliser une station *différente* donne un test par bassin substitut (proxy-basin).
Les deux stations et les deux périodes doivent être définies pour que l'étape Météo se déverrouille.

## Contrôles

![Contrôles de l'étape Stations](../assets/images/screenshots/stations-controls-fr-dark.png#only-dark)
![Contrôles de l'étape Stations](../assets/images/screenshots/stations-controls-fr-light.png#only-light)

Pour chaque rôle :

- **Sélecteur de station** — chaque station disponible sous la forme « Nom (ID) ».
  En choisir une remplit automatiquement la période avec l'enregistrement observé complet de la station.
- **Champs de dates "Début" / "Fin"** — la fenêtre d'analyse.
  Chacun a un petit bouton de réinitialisation qui ramène à la borne de l'enregistrement.
  La période de calage est bornée à l'enregistrement observé de la station (il faut des observations auxquelles ajuster les modèles).
  La période de simulation peut s'étendre *au-delà* de l'enregistrement — jusqu'en 1940 ou jusqu'à aujourd'hui — parce que le débit peut être reconstitué à partir de la météo seule (voir [Simulation](simulation.md#simuler-hors-de-lenregistrement-observe)).
  Une plage inversée (début après la fin) efface la période.

**"Exporter"** télécharge le débit observé chargé, un CSV par rôle sélectionné (`streamflow_<role>_<id>.csv`, colonnes `datetime,streamflow` en mm/jour, enregistrement complet).

## La carte

- Chaque cercle est une station hydrométrique; **survolez**-le pour voir son nom et le contour de son bassin versant.
- **Cliquez** une station pour ouvrir sa fiche : identifiant, superficie du bassin versant, début de l'enregistrement (et fin pour les stations fermées), plus les boutons **"Utiliser pour le calage"** et **"Utiliser pour la simulation"** — une alternative aux menus déroulants.
  Cliquez n'importe où ailleurs sur la carte pour la fermer.

![Fiche de station sur la carte](../assets/images/screenshots/stations-map-dialog-fr-dark.png#only-dark)
![Fiche de station sur la carte](../assets/images/screenshots/stations-map-dialog-fr-light.png#only-light)

- Les éléments de légende **"Station ouverte"** et **"Station fermée"** basculent la visibilité de chaque groupe.
  Les stations fermées (qui ne mesurent plus) sont masquées par défaut; les stations sélectionnées restent toujours visibles.

## Hydrogrammes

Le panneau du bas trace le débit observé de chaque rôle configuré sur sa période sélectionnée, dans la couleur du rôle.

![Hydrogrammes observés](../assets/images/screenshots/stations-hydrographs-fr-dark.png#only-dark)
![Hydrogrammes observés](../assets/images/screenshots/stations-hydrographs-fr-light.png#only-light)

Le débit est exprimé en **mm/jour** (le volume normalisé par la superficie du bassin versant), ce qui rend les valeurs comparables entre bassins versants de tailles différentes.
