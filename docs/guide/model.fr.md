# Modèle

L'étape Modèle choisit le ou les modèles hydrologiques — et le modèle de neige — que le reste du pipeline cale et exécute.
La théorie derrière chaque modèle est documentée dans la [section concepts](../concepts/index.md).

## Unique ou ensemble

![Sélection d'un modèle unique](../assets/images/screenshots/model-single-fr-dark.png#only-dark)
![Sélection d'un modèle unique](../assets/images/screenshots/model-single-fr-light.png#only-light)

La bascule **"Unique" / "Ensemble"** commute entre deux modes :

- **Unique** : exactement un modèle; cliquer un modèle remplace la sélection.
- **Ensemble** : un nombre quelconque de modèles s'exécutent côte à côte — le calage, la simulation et la projection montrent alors une série par modèle plus leur **médiane**.
  **"Tout sélectionner"** et **"Effacer"** agissent sur toute la grille.

![Sélection d'un ensemble](../assets/images/screenshots/model-ensemble-fr-dark.png#only-dark)
![Sélection d'un ensemble](../assets/images/screenshots/model-ensemble-fr-light.png#only-light)

Les ensembles sont le moyen d'explorer l'incertitude structurelle : vingt modèles ajustés aux mêmes données s'accorderont par endroits et divergeront ailleurs, et cette dispersion est instructive.
Repasser du mode ensemble au mode unique ne conserve que le premier modèle sélectionné.

## Le catalogue de modèles

Chacun des vingt boutons affiche le nom du modèle et son nombre de paramètres calés — un premier indice de sa complexité, des quatre paramètres de [GR4J](../concepts/hydro/gr4j.md) aux dix de [NAM](../concepts/hydro/nam.md).
**Survoler** un modèle remplit le panneau de détail du bas avec sa description et la signification de chaque paramètre; le panneau conserve le dernier modèle survolé.

## Modèle de neige

Les précipitations hivernales au Québec s'accumulent en manteau neigeux et sont libérées des mois plus tard — l'ignorer rend les crues printanières impossibles à reproduire.
La section **"Modèle de neige"** propose :

- **"Aucun"** — la précipitation atteint directement le modèle, sans comptabilité d'accumulation ni de fonte de la neige.
- **"CemaNeige"** — un modèle de neige degré-jour qui partage la précipitation entre pluie et neige par bande d'altitude et fait fondre le manteau neigeux au gré de la température (voir [Modèles de neige](../concepts/snow-models.md)).
  Ses deux paramètres sont calés en même temps que ceux du modèle hydrologique.
