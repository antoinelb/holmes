# Concepts

Cette section présente les concepts fondamentaux de la modélisation pluie-débit et explique les modèles hydrologiques, les algorithmes et les métriques implémentés dans HOLMES.

## Qu'est-ce que la modélisation pluie-débit?

La modélisation pluie-débit consiste à simuler comment les précipitations tombant sur un bassin versant se transforment en débit à l'exutoire.
Cette transformation fait intervenir des processus physiques complexes : l'eau s'infiltre dans le sol, s'évapore vers l'atmosphère, percole vers la nappe et finit par rejoindre le cours d'eau par diverses voies.
Un modèle pluie-débit tente de représenter mathématiquement ces processus, ce qui permet de prédire le débit à partir des entrées météorologiques.

Comprendre ces modèles est essentiel pour la gestion des ressources en eau, la prévision des crues, l'évaluation des sécheresses et le dimensionnement des infrastructures.
Plutôt que de résoudre la physique complète du mouvement de l'eau dans le sol et les aquifères (ce qui exigerait des données spatiales détaillées rarement disponibles), les modèles conceptuels utilisent des représentations simplifiées qui capturent le comportement essentiel de l'hydrologie du bassin versant.

## Le bilan hydrique

Au cœur de la modélisation hydrologique se trouve l'équation du bilan hydrique :

$$\frac{dS}{dt} = P - E - Q$$

où :

- $S$ est l'eau stockée dans le bassin versant (humidité du sol, eau souterraine, neige)
- $P$ est la précipitation (pluie et neige)
- $E$ est l'évapotranspiration (l'eau qui retourne à l'atmosphère)
- $Q$ est le débit à l'exutoire

Cette équation simple énonce que la variation du stockage égale les entrées moins les sorties.
Tous les modèles hydrologiques conceptuels sont des élaborations de ce principe, ajoutant réservoirs, voies d'écoulement et délais pour représenter le cheminement de l'eau dans le système.

## La chaîne de modélisation HOLMES

HOLMES implémente une chaîne de modélisation complète pour la simulation pluie-débit.
Chaque étape s'appuie sur la précédente :

### 1. Évapotranspiration potentielle (ETP)

Avant de faire tourner un modèle hydrologique, il faut estimer la demande atmosphérique en eau.
L'ETP représente la quantité maximale d'eau qui s'évaporerait et transpirerait si l'eau était illimitée.
HOLMES utilise la [méthode d'Oudin](pet-models.md), qui estime l'ETP à partir de la température et du rayonnement solaire seulement, ce qui la rend pratique quand des données météorologiques détaillées ne sont pas disponibles.

### 2. Accumulation et fonte de la neige

Dans les bassins versants à chutes de neige importantes, la précipitation ne contribue pas immédiatement au ruissellement.
La neige s'accumule pendant les périodes froides et libère de l'eau à la fonte, ce qui modifie fondamentalement la chronologie du débit.
Le [modèle CemaNeige](snow-models.md) suit l'évolution du manteau neigeux par une approche degré-jour, répartissant la précipitation entre pluie et neige et calculant la fonte selon la température.

### 3. Transformation hydrologique

Le cœur de la chaîne de modélisation est le modèle pluie-débit qui transforme la précipitation efficace (pluie plus fonte) en débit.
HOLMES implémente plusieurs modèles :

- **[Modèle Bucket](hydro/bucket.md)** : un modèle à six paramètres fondé sur la théorie des réservoirs linéaires, avec des voies d'écoulement rapide et lente explicites.
  Il offre plus de flexibilité dans la répartition de l'écoulement et capture souvent bien la récession.
- **[CEQUEAU](hydro/cequeau.md)** : un modèle à neuf paramètres et deux réservoirs (la simplification « CEQU » du CEQUEAU original) qui produit plusieurs voies d'écoulement à seuil et continues, lui donnant une flexibilité considérable dans la forme de l'hydrogramme.
- **[CREC](hydro/crec.md)** : un modèle à six paramètres doté d'une fonction sigmoïde de partage de la pluie qui répartit en douceur la précipitation entre ruissellement et infiltration selon l'humidité du sol.
  Il utilise un routage de surface non linéaire (quadratique).
- **[GARDENIA](hydro/gardenia.md)** : un modèle à six paramètres du BRGM développé à l'origine pour la prévision pluie → niveau piézométrique.
  Il utilise trois réservoirs en série avec une loi de vidange quadratique du sol et un coefficient de correction de l'ETP calable.
- **[GR4J](hydro/gr4j.md)** : un modèle parcimonieux à quatre paramètres largement utilisé en recherche comme en opérationnel.
  Il représente le bassin versant par deux réservoirs (production et routage) reliés par des hydrogrammes unitaires.
- **[HBV](hydro/hbv.md)** : un modèle à neuf paramètres suivant la formulation HBV0 de Bergström issue de la thèse de Perrin.
  Il utilise une production de sol non linéaire intégrée en cinq sous-pas, un réservoir intermédiaire à deux sorties, une percolation plafonnée et un hydrogramme unitaire triangulaire.
- **[IHACRES](hydro/ihacres.md)** : un modèle à sept paramètres de Jakeman et al. (1990) construit autour d'un indice d'humidité du bassin adimensionnel à assèchement modulé par l'ETP, d'une pluie efficace trapézoïdale au point milieu et de réservoirs de routage linéaires rapide/lent en parallèle partageant un couplage multiplicatif des constantes de temps.
- **[HYMOD](hydro/hymod.md)** : un modèle à six paramètres utilisant un réservoir d'humidité du sol à distribution de Pareto (genèse du ruissellement par aires contributives variables) combiné à trois réservoirs linéaires en cascade pour l'écoulement rapide et un réservoir souterrain linéaire pour le débit de base.
- **[MARTINE](hydro/martine.md)** : un modèle à sept paramètres du BRGM (Mazenc et al. 1984) avec une production de surface par débordement, un coefficient de distribution rapide/lente calable, un routage direct quadratique, un réservoir intermédiaire à double voie (drainage linéaire + débordement) et une récession linéaire de la nappe.
- **[MOHYSE](hydro/mohyse.md)** : un modèle minimaliste à sept paramètres (Fortin & Turcotte 2007) avec une infiltration limitée par la capacité, deux réservoirs linéaires sol/nappe, un drainage linéaire à trois voies et un hydrogramme unitaire en forme de loi gamma pour le routage.
- **[MORDOR](hydro/mordor.md)** : un modèle à six paramètres d'EDF (Garçon 1999) avec quatre réservoirs en cascade (surface → intermédiaire → sol profond → nappe), une répartition proportionnelle de la pluie, une vidange non linéaire cubique de la nappe et un routage UH2 bilatéral à trois composantes d'exposant 2.5.
- **[NAM](hydro/nam.md)** : un portage à dix paramètres de la version HM12 de HOOPLA du modèle opérationnel danois de Nielsen & Hansen (1973).
  Sept réservoirs (surface, sol, deux réservoirs en cascade d'écoulement hypodermique, deux réservoirs en cascade de ruissellement de surface et un réservoir de *déficit* de la nappe) avec une évapotranspiration à trois branches, une remontée capillaire depuis la zone saturée et un hydrogramme unitaire à délai fractionnaire.
- **[PDM](hydro/pdm.md)** : un modèle à huit paramètres (Probability-Distributed Model, Moore & Clarke 1981) avec une capacité d'humidité du sol à distribution de Pareto, un drainage à seuil vers un réservoir souterrain cubique, une cascade linéaire à deux étages pour le routage rapide et un hydrogramme unitaire à délai fractionnaire.
- **[SACRAMENTO](hydro/sacramento.md)** : une variante à neuf paramètres du modèle opérationnel NWSRFS de Burnash et al. (1973) suivant la simplification de Perrin.
  Il utilise cinq réservoirs (interception, eau de tension, eau libre, routage de zone basse, routage direct) avec un schéma de percolation à rétroaction de remplissage, des voies d'écoulement intermédiaire (interflow) et hypodermique, et une correction ascendante du bilan de masse entre le réservoir de zone basse et le réservoir d'eau libre.
- **[SIMHYD](hydro/simhyd.md)** : un modèle australien à huit paramètres (Chiew et al. 2002) avec une capacité d'infiltration exponentielle décroissant avec la saturation du sol, un écoulement hypodermique et une recharge de la nappe proportionnels à la saturation, et deux réservoirs de routage linéaires (souterrain lent + routage rapide) avec un routage à délai fractionnaire.
- **[SMAR](hydro/smar.md)** : un modèle à huit paramètres (O'Connell et al. 1970) avec une colonne de sol discrétisée en 16 couches (25 mm par couche, 400 mm au total), une évapotranspiration décroissant exponentiellement avec la profondeur, un ruissellement direct dépendant de l'humidité, deux réservoirs de routage linéaire/quadratique à répartition d'écoulement calable et un hydrogramme unitaire à délai fractionnaire.
- **[TANK](hydro/tank.md)** : une variante de Perrin à sept paramètres du modèle de Sugawara (1979) (HOOPLA HM17), organisant le bassin versant en une cascade verticale de quatre réservoirs linéaires avec des sorties latérales à double seuil sur le réservoir de surface, une progression géométrique des constantes de temps de vidange, une satisfaction de l'ETP en cascade de haut en bas, une correction de l'ETP calable et un hydrogramme unitaire à délai fractionnaire routant la somme de cinq débits sortants.
- **[TOPMODEL](hydro/topmodel.md)** : une variante à sept paramètres du modèle à indice topographique de Beven & Kirkby (1979) suivant la simplification de Perrin.
  Un réservoir d'interception, un réservoir de déficit de la nappe non borné avec deux fonctions de partage sigmoïdes (recharge et évapotranspiration), un réservoir de routage de surface quadratique et un hydrogramme unitaire à délai fractionnaire — pédagogiquement intéressant parce qu'il remplace les seuils de saturation durs par des partages probabilistes lisses.
- **[WAGENINGEN](hydro/wageningen.md)** : un modèle conceptuel à huit paramètres (Warmerdam et al. 1997, HOOPLA HM19) avec un seuil unique d'humidité du sol $X_1$ qui bascule entre percolation et remontée capillaire, une ETP amortie en cosinus sous le seuil, une dissociation de l'écoulement via le ratio $T/X_5$, des réservoirs linéaires rapide/lent en parallèle aux constantes de temps couplées multiplicativement et un routage à délai fractionnaire.
- **[XINANJIANG](hydro/xinanjiang.md)** : une variante à huit paramètres du modèle opérationnel chinois de Zhao et al. (1980).
  Il utilise deux réservoirs à excès de saturation à distribution en puissance en série (sol + eau libre) alimentant un partage de routage rapide/lent calable et un hydrogramme unitaire à délai fractionnaire à deux prises.

### 4. Calage du modèle

Les modèles hydrologiques ont des paramètres qui ne peuvent pas être mesurés directement et doivent être estimés en comparant les sorties du modèle au débit observé.
Ce processus, appelé calage, cherche les valeurs de paramètres qui minimisent l'écart entre débits simulés et observés.
HOLMES utilise l'[algorithme SCE-UA](calibration-algorithms.md), une méthode d'optimisation globale conçue spécifiquement pour le calage des modèles hydrologiques.

### 5. Évaluation de la performance

Après le calage, il faut évaluer la qualité du modèle.
HOLMES fournit plusieurs [métriques de performance](metrics.md) qui quantifient différents aspects de la précision du modèle :

- Le **RMSE** mesure l'ampleur moyenne des erreurs
- Le **NSE** mesure la compétence du modèle par rapport à l'utilisation de la moyenne comme prédicteur
- Le **KGE** décompose la performance en corrélation, biais de variabilité et biais de moyenne

## Choisir le bon modèle

Le choix du modèle dépend des caractéristiques de votre bassin versant et de vos objectifs.
Chaque ligne ci-dessous renvoie à la page de concepts complète du modèle :

| Modèle | Params | Réservoir de sol | Répartition de l'écoulement | Routage | Échanges souterrains | Équifinalité | Idéal pour |
|--------|:------:|------------------|-----------------------------|---------|:--------------------:|:------------:|------------|
| [Bucket](hydro/bucket.md) | 6 | Réservoir unique | Calable ($\alpha$, $\beta$) | Réservoirs linéaires | Non | Plus élevée | Bassins versants aux composantes de récession distinctes |
| [CEQUEAU](hydro/cequeau.md) | 9 | Deux réservoirs (surface + eau souterraine) | Voies à seuil + continues | Délai temporel pur | Non | Plus élevée | Formes d'hydrogramme flexibles, réponse pilotée par des seuils |
| [CREC](hydro/crec.md) | 6 | Réservoir unique + partage sigmoïde | Sigmoïde (dépendant de l'humidité) | Réservoirs quadratique + linéaire | Non | Modérée | Bassins versants où la genèse du ruissellement dépend de l'humidité |
| [GARDENIA](hydro/gardenia.md) | 6 | Surface + sol + eau souterraine en série | Débordement en surface + vidange quadratique du sol | Délai fractionnaire | Non | Modérée | Bassins versants à forte composante aquifère; cas d'usage pluie → niveau piézométrique |
| [GR4J](hydro/gr4j.md) | 4 | Réservoir unique | Fixe 90 % / 10 % | Hydrogrammes unitaires + réservoir non linéaire | Oui ($X_2$) | Plus faible | Bassins versants tempérés humides, benchmarking |
| [HBV](hydro/hbv.md) | 9 | Sol non linéaire (cinq sous-pas) | Réservoir intermédiaire à sortie haute à seuil + sortie basse linéaire | Hydrogramme unitaire triangulaire | Non | Plus élevée | Bassins versants nordiques / tempérés, prévision opérationnelle |
| [IHACRES](hydro/ihacres.md) | 7 | Indice d'humidité adimensionnel (non borné, décroissance modulée par l'ETP) | Fraction rapide/lente calable ($X_2$) | Réservoirs linéaires parallèles ($X_3$ / $X_3 \cdot X_4$) + délai fractionnaire | Non | Modérée | Bassins versants où l'analyse de récession guide le calage; contraste pédagogique avec les modèles à réservoir de sol |
| [HYMOD](hydro/hymod.md) | 6 | Distribution de Pareto (aires contributives variables) | Excès de saturation + $\alpha$ calable | Cascade de trois réservoirs linéaires + un réservoir lent | Non | Modérée | Bassins versants où domine le ruissellement des zones saturées |
| [MARTINE](hydro/martine.md) | 7 | Réservoir unique (débordement) | Fraction rapide/lente calable ($X_5$) | Réservoir direct quadratique + intermédiaire à double voie + eau souterraine linéaire + délai fractionnaire | Non | Modérée | Études de régionalisation; bassins versants aux composantes hypodermique et de débit de base distinctes |
| [MOHYSE](hydro/mohyse.md) | 7 | Réservoir unique à capacité limitée | Drainage vadose linéaire vers la rivière + la nappe | Hydrogramme unitaire gamma (mémoire de 80 pas) | Non | Modérée | Benchmarking; référence de complexité minimale; enseignement de la chaîne production-routage-convolution |
| [MORDOR](hydro/mordor.md) | 6 | Quatre réservoirs en cascade (U → L → Z → N) | Proportionnelle au remplissage de U + partage du drainage de L selon le ratio de Z | UH2 bilatéral à trois composantes (exposant 2.5) | Non | Modérée | Bassins versants à débit de base important; enseignement des chaînes de réservoirs en cascade |
| [NAM](hydro/nam.md) | 10 | Réservoir de surface + réservoir de sol avec remontée capillaire | ETP à trois branches + partage ruissellement/hypodermique/percolation selon le taux de remplissage du sol | Deux cascades parallèles de deux réservoirs + HU à délai fractionnaire | Oui (par déficit, seuil $X_1$) | Plus élevée | Bassins versants où ruissellement de surface et écoulement hypodermique doivent être modélisés séparément; cas d'usage opérationnels scandinaves |
| [PDM](hydro/pdm.md) | 8 | Distribution de Pareto (aires contributives variables) | Excès de saturation + excès d'infiltration + drainage à seuil | Cascade de deux réservoirs linéaires + réservoir souterrain cubique + délai fractionnaire | Non | Modérée | Bassins versants à ruissellement par aires contributives variables et récession non linéaire du débit de base; cas d'usage opérationnels britanniques |
| [SACRAMENTO](hydro/sacramento.md) | 9 | Interception + eau de tension + eau libre (cascade de trois réservoirs) | Percolation à rétroaction de remplissage + débordement à seuil | Réservoir de routage direct + registre à délai fractionnaire | Oui (via la percolation profonde $X_8$) | Plus élevée | Bassins versants à séparation nette du débit de base; cas d'usage opérationnels de type NWS |
| [SIMHYD](hydro/simhyd.md) | 8 | Interception + réservoir de sol (infiltration exponentielle) | Écoulement hypodermique et recharge de la nappe proportionnels à la saturation | Réservoirs linéaires souterrain (lent) + de routage (rapide) + délai fractionnaire | Non | Modérée | Bassins versants australiens; benchmarking des modèles d'infiltration à seuil |
| [SMAR](hydro/smar.md) | 8 | Colonne de sol discrétisée en 16 couches (400 mm) | Ruissellement direct dépendant de l'humidité + infiltration exponentielle | Réservoirs souterrain linéaire + de surface quadratique + délai fractionnaire | Non | Modérée | Enseignement de la discrétisation verticale du sol; bassins versants où le profil d'ETP en profondeur compte |
| [TANK](hydro/tank.md) | 7 | Quatre réservoirs linéaires en cascade verticale (S → R → T → L) | Sorties latérales à double seuil sur $S$ + sorties latérales simples sur $R$, $T$ | Constantes de vidange en progression géométrique ($x_3$, $x_3 x_4$, $x_3 x_4 x_7$, $x_3 x_4 x_7^2$) + délai fractionnaire | Non | Modérée | Bassins versants aux récessions multi-échelles émergentes; enseignement de la séparation des écoulements par le stockage |
| [TOPMODEL](hydro/topmodel.md) | 7 | Interception + déficit souterrain non borné | Recharge sigmoïde + ETP souterraine sigmoïde (logistique, sans seuils) | Réservoir de surface quadratique + débit de base exponentiel + délai fractionnaire | Non | Modérée | Bassins versants où la dynamique lisse des aires saturées compte; contraste pédagogique avec les modèles à seuils |
| [WAGENINGEN](hydro/wageningen.md) | 8 | Réservoir de sol unique avec seuil $X_1$ et remontée capillaire depuis $T$ | Dissociation de l'écoulement via $\mathrm{DIV} = \min(1, T/X_5)$ | Réservoirs linéaires parallèles rapide ($X_6$) + lent ($X_6 \cdot X_7$) + délai fractionnaire | Ascendants (remontée capillaire $T \to S$) | Modérée | Bassins versants tempérés humides à alternance nette de régimes secs/humides; enseignement du couplage de processus par seuil |
| [XINANJIANG](hydro/xinanjiang.md) | 8 | Deux réservoirs à distribution en puissance (sol + eau libre) | Excès de saturation ($B = 0.25$ fixe, $X_8$ calable) | Réservoirs linéaires rapide/lent + hydrogramme unitaire à deux prises | Non | Modérée | Bassins versants à forte variabilité spatiale de la capacité de stockage; cas d'usage opérationnels chinois / de mousson |

<!--
  Vous ajoutez un modèle hydrologique? Ajoutez une ligne à ce tableau. Le
  schéma des colonnes est : Modèle (lié) | Params | Réservoir de sol |
  Répartition de l'écoulement | Routage | Échanges souterrains |
  Équifinalité | Idéal pour. Gardez les lignes dans l'ordre alphabétique de
  docs/concepts/hydro/ (l'ordre qu'awesome-nav affichera dans la barre
  latérale).
-->

Pour les bassins versants où la neige est importante, activez CemaNeige quel que soit le modèle hydrologique choisi.

## Pour aller plus loin

Chaque page de concepts fournit des explications détaillées, les formulations mathématiques et des conseils pratiques :

- [Modèle Bucket](hydro/bucket.md) - Modèle à réservoirs linéaires avec répartition flexible de l'écoulement
- [Modèle CEQUEAU](hydro/cequeau.md) - Modèle à deux réservoirs avec voies d'écoulement à seuil et continues
- [Modèle CREC](hydro/crec.md) - Partage sigmoïde avec routage de surface non linéaire
- [Modèle GARDENIA](hydro/gardenia.md) - Modèle BRGM à trois réservoirs avec vidange quadratique du sol et correction de l'ETP
- [Modèle GR4J](hydro/gr4j.md) - Modèle parcimonieux à quatre paramètres
- [Modèle HBV](hydro/hbv.md) - Formulation de Bergström à neuf paramètres avec production de sol en cinq sous-pas et routage triangulaire
- [Modèle IHACRES](hydro/ihacres.md) - Modèle à indice d'humidité à sept paramètres avec assèchement modulé par l'ETP et routage linéaire rapide/lent en parallèle
- [Modèle HYMOD](hydro/hymod.md) - Réservoir de sol à distribution de Pareto avec cascade rapide de trois réservoirs
- [Modèle MARTINE](hydro/martine.md) - Modèle BRGM à sept paramètres avec routage quadratique et réservoir intermédiaire à double voie
- [Modèle MOHYSE](hydro/mohyse.md) - Modèle minimaliste à sept paramètres avec infiltration limitée par la capacité et hydrogramme unitaire gamma
- [Modèle MORDOR](hydro/mordor.md) - Modèle EDF à six paramètres avec quatre réservoirs en cascade et routage UH2 à trois composantes
- [Modèle NAM](hydro/nam.md) - Portage danois HM12 à dix paramètres avec sept réservoirs, réservoir de déficit de la nappe et remontée capillaire
- [Modèle PDM](hydro/pdm.md) - Réservoir de sol à distribution de Pareto avec nappe cubique et drainage à seuil
- [Modèle SACRAMENTO](hydro/sacramento.md) - Cascade Burnash/NWSRFS à cinq réservoirs avec percolation à rétroaction de remplissage et amortissement de la percolation profonde
- [Modèle SIMHYD](hydro/simhyd.md) - Modèle australien à huit paramètres avec infiltration exponentielle, deux réservoirs de routage linéaires et délai fractionnaire
- [Modèle SMAR](hydro/smar.md) - Modèle irlandais à huit paramètres avec colonne de sol en 16 couches, ETP décroissant avec la profondeur et routage linéaire/quadratique
- [Modèle TANK](hydro/tank.md) - Cascade de Sugawara à sept paramètres de quatre réservoirs linéaires avec sorties latérales à double seuil et progression géométrique des constantes de vidange
- [TOPMODEL](hydro/topmodel.md) - Modèle de Beven & Kirkby à sept paramètres avec partage sigmoïde recharge/ETP et débit de base exponentiel
- [Modèle WAGENINGEN](hydro/wageningen.md) - Modèle de Warmerdam et al. à huit paramètres avec bascule percolation/remontée capillaire par seuil et dissociation de l'écoulement
- [Modèle XINANJIANG](hydro/xinanjiang.md) - Deux réservoirs à excès de saturation à distribution en puissance avec partage de routage rapide/lent
- [Modèles de neige (CemaNeige)](snow-models.md) - Accumulation et fonte de la neige
- [Modèles d'ETP (Oudin)](pet-models.md) - Calcul de l'évapotranspiration potentielle
- [Algorithmes de calage (SCE-UA)](calibration-algorithms.md) - Optimisation automatique des paramètres
- [Métriques de performance](metrics.md) - RMSE, NSE et KGE expliqués
