# Simulation

L'étape Simulation évalue les paramètres calés sur la station et la période de simulation — des données auxquelles les modèles n'ont *pas* été ajustés.
C'est là qu'un calage prouve (ou échoue à prouver) qu'il généralise : test en échantillons distincts (split-sample) quand la station est la même et que la période diffère, test par bassin substitut (proxy-basin) quand la station diffère.

L'étape se déverrouille une fois que le calage a produit des paramètres, et le résultat est calculé automatiquement quand vous l'ouvrez.

![Vue d'ensemble de l'étape Simulation](../assets/images/screenshots/simulation-overview-fr-dark.png#only-dark)
![Vue d'ensemble de l'étape Simulation](../assets/images/screenshots/simulation-overview-fr-light.png#only-light)

## Contrôles

- **"Années d'initialisation"** (0–5, 1 par défaut) — même rôle qu'au [calage](calibration.md#reglages) : des années ajoutées en amont pour amorcer les réservoirs, exclues des métriques.
- Une ligne par modèle avec son **KGE** sur la fenêtre de simulation; survoler une ligne met ce modèle en évidence dans les deux graphiques.
- **"Exporter"** télécharge `simulation_<station>_<start>_<end>.json` (la configuration, les paramètres de chaque modèle et toutes ses métriques) et `.csv` (`datetime,observations,<model…>` plus `median` pour les ensembles).

## Le graphique des métriques

Plutôt qu'un score unique, le graphique du haut profile le comportement de chaque modèle sur six [métriques](../concepts/metrics.md), un point par modèle plus un point plein pour la médiane, contre un guide "Optimal" en tireté à 1 :

![Métriques de simulation](../assets/images/screenshots/simulation-metrics-fr-dark.png#only-dark)
![Métriques de simulation](../assets/images/screenshots/simulation-metrics-fr-light.png#only-light)

- **"Hauts débits (KGE)"** — le KGE sur les débits non transformés, dominé par les crues;
- **"Débits moyens (KGE-sqrt)"** — le KGE sur les débits transformés par racine carrée;
- **"Étiages (KGE-log)"** — le KGE sur les débits transformés par logarithme, dominé par les récessions et le débit de base;
- **"Bilan hydrique (biais moyen)"** — le ratio du débit moyen simulé au débit moyen observé;
- **"Variabilité des débits (biais d'écart-type)"** — le ratio de l'écart-type des débits simulés à celui des observés;
- **"Corrélation"** — la chronologie de la série simulée par rapport aux observations.

Un modèle peut bien noter sur les crues et dériver quand même sur le volume ou les étiages; le profil rend ces compromis visibles d'un coup d'œil.

## Le graphique de débit

Le graphique du bas superpose les observations (en vert — la couleur de la station de simulation) avec la simulation de chaque modèle et la médiane de l'ensemble, bande d'initialisation incluse.

## Simuler hors de l'enregistrement observé

La période de simulation peut s'étendre au-delà de l'enregistrement de la station : les modèles tournent alors sur la météo seule.
L'hydrogramme se dessine quand même, mais les pastilles de métriques affichent "kge —" pour les jours sans observations auxquelles se comparer.
C'est ainsi qu'un événement non observé se reconstitue — par exemple la crue du Saguenay de juillet 1996 à une station dont l'enregistrement ne commence que plus tard.
