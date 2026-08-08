# Météo

L'étape Météo choisit le forçage météorologique — précipitations et température journalières moyennées sur chaque bassin versant sélectionné — qui alimente les modèles.
Comparer les méthodes est en soi un exercice de modélisation : les stations observées et les réanalyses divergent, et cette divergence se propage dans le débit simulé.

## Les trois méthodes

![Choix de la méthode météo](../assets/images/screenshots/weather-methods-fr-dark.png#only-dark)
![Choix de la méthode météo](../assets/images/screenshots/weather-methods-fr-light.png#only-light)

Sélectionner une méthode charge ses données; en choisir une autre pendant qu'un chargement est en cours annule le premier.
Comme sur la carte des Stations, survoler une station dessine son bassin versant — les captures d'écran ci-dessous le montrent sous les sources de chaque méthode.

### "Stations les plus proches"

Les enregistrements journaliers observés des stations météo du ministère du Québec (MELCC).
Les stations les plus proches du centroïde du bassin versant sont combinées par pondération inverse à la distance (les stations plus proches pèsent plus, en 1/d²).
Le curseur **"Stations"** (1–5, 3 par défaut) fixe le nombre de stations alimentant la moyenne.
La carte dessine chaque station météo, les centroïdes des bassins versants et une ligne de chaque centroïde vers les stations qu'il utilise réellement; survoler un centroïde met ses liens en évidence.

![Méthode des stations les plus proches](../assets/images/screenshots/weather-nearest-stations-fr-dark.png#only-dark)
![Méthode des stations les plus proches](../assets/images/screenshots/weather-nearest-stations-fr-light.png#only-light)

### "ERA5"

La réanalyse globale ERA5 de l'ECMWF : une reconstruction de la météo passée fondée sur un modèle, sur une grille de 0.25°, extraite aux cellules de la grille couvrant chaque bassin versant et moyennée avec des poids de superficie.
La carte trace le contour des cellules contributives.

![Méthode ERA5](../assets/images/screenshots/weather-era5-fr-dark.png#only-dark)
![Méthode ERA5](../assets/images/screenshots/weather-era5-fr-light.png#only-light)

### "Grille du ministère"

Les grilles journalières des *Grilles climatiques du Québec* : des observations de stations interpolées spatialement sur une grille fine, réduites à une moyenne de bassin versant pondérée par la superficie.

![Méthode de la grille du ministère](../assets/images/screenshots/weather-ministry-grid-fr-dark.png#only-dark)
![Méthode de la grille du ministère](../assets/images/screenshots/weather-ministry-grid-fr-light.png#only-light)

## Graphiques

Le canevas montre quatre graphiques : les **précipitations** (mm, barres journalières, en haut) et la **température** (°C, courbe, en bas), pour le bassin versant de calage (violet, à gauche) et le bassin versant de simulation (vert, à droite), chacun sur sa propre période.

## Exportation

**"Exporter"** télécharge un CSV par rôle (`weather_<method>_<role>_<id>.csv`, colonnes `datetime,precipitation,temperature`), activé une fois les données de la méthode courante chargées.
