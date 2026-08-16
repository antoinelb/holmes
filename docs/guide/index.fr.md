# Premiers pas

HOLMES s'exécute comme une application web locale.
Ce guide couvre chaque fonctionnalité de l'interface, étape par étape; la page des [flux de travail courants](workflows.md) les enchaîne en exercices de modélisation complets.

## Installation et lancement

Installez HOLMES (Python ≥ 3.12) et démarrez le serveur :

```bash
pip install holmes-hydro
holmes run
```

Ouvrez ensuite [http://127.0.0.1:8000](http://127.0.0.1:8000) dans votre navigateur.
Au premier lancement, le serveur télécharge le jeu de données préconstruit — une archive depuis la release `data` du dépôt — donc le démarrage peut prendre quelques minutes; le terminal affiche la progression du téléchargement et l'application démarre dès qu'il est terminé.
Ensuite, il ne retélécharge que lorsqu'une archive plus récente est publiée, et continue de servir les données courantes entre-temps.
Aucun identifiant n'est nécessaire pour utiliser l'application.
Les données se trouvent dans le répertoire de données de l'utilisateur (`~/.local/share/holmes` sous Linux, `~/Library/Application Support/holmes` sous macOS, `%LOCALAPPDATA%\holmes\holmes` sous Windows); définissez la variable d'environnement `HOLMES_DATA_DIR` pour utiliser un autre emplacement, et `HOLMES_SKIP_DATA_SYNC=True` pour sauter complètement la vérification au démarrage.

![L'application au premier chargement](../assets/images/screenshots/app-start-fr-dark.png#only-dark)
![L'application au premier chargement](../assets/images/screenshots/app-start-fr-light.png#only-light)

## L'interface

L'écran est divisé en quatre régions :

- **Barre latérale** (à gauche) : les six étapes du pipeline sous forme de boutons circulaires — Stations, Météo, Modèle, Calage, Simulation, Projection.
- **Contrôles** (en haut à droite) : la carte de réglages de l'étape courante.
- **Canevas** (au centre) : les graphiques — ou, pour l'étape Modèle, le catalogue de modèles.
- **Carte** (arrière-plan) : la carte interactive des stations, visible aux étapes Stations et Météo.

Le bouton de menu dans le coin supérieur droit ouvre le **panneau de réglages** :

![Panneau de réglages](../assets/images/screenshots/settings-panel-fr-dark.png#only-dark)
![Panneau de réglages](../assets/images/screenshots/settings-panel-fr-light.png#only-light)

- **"Changer de thème"** bascule entre le thème sombre (par défaut) et le thème clair; la touche ++t++ fait de même partout hors d'un champ de texte.
- **"Tout réinitialiser"** efface tout ce que l'application a enregistré dans votre navigateur et recharge la page — une remise à zéro complète du pipeline.
- **Version** affiche la version de HOLMES installée.

## Le pipeline

HOLMES est organisé en pipeline linéaire : chaque étape consomme les choix faits dans les précédentes.
La barre latérale montre où vous êtes et dans quel état se trouve chaque étape :

![Barre latérale du pipeline](../assets/images/screenshots/sidebar-pipeline-fr-dark.png#only-dark)
![Barre latérale du pipeline](../assets/images/screenshots/sidebar-pipeline-fr-light.png#only-light)

- **Verrouillée** (estompée) : il manque à l'étape un choix en amont — par exemple, Météo reste verrouillée tant que les deux stations et les deux périodes ne sont pas définies.
- **Disponible** (anneau gris) : l'étape peut être ouverte mais n'est pas encore configurée.
- **Terminée** (anneau vert) : les choix de l'étape sont complets et ses résultats sont à jour.
- **Périmée** (anneau jaune) : quelque chose a changé en amont depuis la dernière complétion de l'étape; revisitez-la pour recalculer.
- L'étape courante est mise en évidence.

Changer quoi que ce soit qui affecte un calage — station, période, méthode météo, transformation, initialisation, modèles, modèle de neige — supprime les paramètres calés et **reverrouille Simulation et Projection** jusqu'à ce que vous recaliez.
C'est délibéré : les résultats en aval ne doivent jamais refléter silencieusement une configuration périmée.

Vos sélections persistent dans le navigateur (elles survivent à un rechargement), mais les résultats de calage qui méritent d'être conservés plus longtemps devraient être [exportés dans un fichier](calibration.md#exporter-et-importer).

## Manipuler les graphiques

Tous les graphiques de HOLMES partagent les mêmes interactions :

- **Zoom** : cliquez et glissez horizontalement pour sélectionner une plage temporelle; le graphique zoome dessus.

![Un hydrogramme zoomé](../assets/images/screenshots/calibration-brush-zoom-fr-dark.png#only-dark)
![Un hydrogramme zoomé](../assets/images/screenshots/calibration-brush-zoom-fr-light.png#only-light)

- **Réinitialisation** : double-cliquez le graphique pour restaurer la plage complète.
- **Mise en évidence** : aux étapes à plusieurs modèles, survoler la ligne d'un modèle dans la carte des contrôles met sa courbe en évidence dans les graphiques et estompe les autres.
- **Les données manquantes** apparaissent comme de fines bandes verticales rouges; les trous interrompent la courbe plutôt que d'être comblés.

Pendant qu'un chargement de données est en cours, l'icône de l'onglet du navigateur devient une roulette et les graphiques concernés affichent leur propre indicateur de chargement.
