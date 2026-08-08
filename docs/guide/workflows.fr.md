# Flux de travail courants

Des recettes enchaînant les étapes du pipeline en exercices classiques de l'hydrologie opérationnelle.
Chacune renvoie aux pages d'étape pour les détails.

## Calage manuel d'un modèle

1. **[Stations](stations.md)** : choisissez la station et la période de calage; choisissez la même station comme station de simulation (période quelconque) pour que le pipeline puisse se déverrouiller.
2. **[Météo](weather.md)** : choisissez une méthode.
3. **[Modèle](model.md)** : mode "Unique", choisissez un modèle, activez CemaNeige.
4. **[Calage](calibration.md)** : choisissez l'objectif et la transformation, réglez "Algorithme" sur Manuel, ouvrez la section du modèle et itérez sur les curseurs.
   Chaque mouvement re-simule immédiatement; jugez l'ajustement sur la pastille d'objectif *et* sur l'hydrogramme (zoomez sur les crues et les récessions).
5. **"Exporter"** le résultat — le JSON conserve les paramètres et toute votre trajectoire, le CSV contient les séries simulées pour vos figures.

## Calage automatique avec test en échantillons distincts

Caler sur une période, valider sur une autre : la performance sur des données que le modèle n'a jamais vues est la seule mesure honnête.

1. **[Stations](stations.md)** : la même station pour les deux rôles; période de calage = la fenêtre d'ajustement, période de simulation = une fenêtre de validation *disjointe*.
2. **[Météo](weather.md)** et **[Modèle](model.md)** : comme ci-dessus.
3. **[Calage](calibration.md)** : "Algorithme" SCE, puis **"Caler"**; exportez les paramètres ajustés.
4. **[Simulation](simulation.md)** : la validation s'exécute automatiquement — lisez les pastilles KGE et le profil à six métriques; exportez les séries et les métriques.

Pour étudier l'effet de la période de calage elle-même, relancez l'étape 3 avec une période de calage différente (par exemple beaucoup plus courte) et comparez les métriques de validation : les paramètres ne sont généraux que dans la mesure du climat sur lequel ils ont été ajustés.

## Comparer les sources météo et les modèles

1. Montez un calage en échantillons distincts comme ci-dessus, avec l'étape [Modèle](model.md) en mode "Ensemble" sur les modèles à comparer — une seule exécution SCE les cale tous, et chaque graphique les superpose avec leur médiane.
2. Pour changer de source météo, revisitez **[Météo](weather.md)** et choisissez une autre méthode.
   Les étapes en aval deviennent périmées et les paramètres calés sont supprimés — recalez, puis comparez les métriques de validation entre les exécutions.
3. **Exportez le calage de chaque configuration dans son propre fichier**; réimporter un fichier restaure tout son contexte ([importation](calibration.md#exporter-et-importer)), pour basculer entre les configurations à volonté.

## Test par bassin substitut (transfert spatial)

Des paramètres calés sur un bassin versant peuvent-ils en reproduire un autre?

1. **[Stations](stations.md)** : station de calage = le bassin donneur, station de simulation = le bassin receveur, avec leurs périodes.
2. Calez (SCE) sur le donneur comme ci-dessus.
3. **[Simulation](simulation.md)** évalue les paramètres du donneur sur le receveur : le profil de métriques vous dit quels aspects du transfert tiennent (chronologie, volume) et lesquels se dégradent.

## Reconstituer un événement non observé

Un modèle calé plus la météo suffisent pour estimer le débit là où et quand aucune station ne mesurait — par exemple la crue du Saguenay de juillet 1996 à une station dont l'enregistrement commence plus tard.

1. Calez sur la station et la période convenables les plus proches ([manuel](#calage-manuel-dun-modele) ou [automatique](#calage-automatique-avec-test-en-echantillons-distincts)).
2. **[Stations](stations.md)** : réglez la station de simulation sur la cible et la période de simulation autour de l'événement — la période peut s'étendre hors de l'enregistrement observé.
3. **[Simulation](simulation.md)** : l'hydrogramme se dessine à partir de la météo seule (les métriques restent vides sans observations); zoomez sur l'événement et exportez les séries.

## Sauvegarder et présenter votre travail

- Chaque étape a un bouton **"Exporter"**; les CSV (débit, météo, séries simulées, régime, indicateurs) sont prêts à tracer dans les figures de votre rapport.
- Le navigateur ne conserve que le dernier état : **exportez chaque calage auquel vous tenez dans son propre JSON** et réimportez-le pour y revenir.
