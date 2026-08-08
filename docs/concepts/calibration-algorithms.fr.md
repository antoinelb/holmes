# Algorithmes de calage

## SCE-UA : Shuffled Complex Evolution

### Aperçu

Le calage d'un modèle consiste à trouver les valeurs de paramètres qui rapprochent le plus possible les sorties du modèle des observations.
En modélisation pluie-débit, cela signifie ajuster des paramètres comme la capacité du sol, les taux de récession et les temps de routage jusqu'à ce que le débit simulé ressemble au débit observé.

C'est fondamentalement un problème d'optimisation : on cherche les valeurs de paramètres qui minimisent (ou maximisent) une fonction objectif mesurant l'écart entre simulations et observations.
La difficulté est que les modèles hydrologiques ont des surfaces de réponse complexes comportant de multiples optimums locaux — les méthodes simples fondées sur le gradient restent souvent piégées dans des solutions sous-optimales.

SCE-UA (Shuffled Complex Evolution - University of Arizona) est un algorithme d'optimisation globale conçu spécifiquement pour le calage des modèles hydrologiques.
Développé par Duan, Sorooshian et Gupta au début des années 1990, il est devenu le standard de fait pour le calage automatique des modèles pluie-débit conceptuels.
SCE-UA combine des éléments de plusieurs traditions d'optimisation pour explorer efficacement l'espace des paramètres et trouver de façon fiable l'optimum global.

### Concepts clés

- **Fonction objectif** : une mesure mathématique de l'adéquation du modèle aux observations.
  Les choix courants incluent l'efficacité de Nash-Sutcliffe (NSE), l'efficacité de Kling-Gupta (KGE) ou l'erreur quadratique moyenne (RMSE).
  L'algorithme de calage tente d'optimiser cette fonction.

- **Espace des paramètres** : l'espace multidimensionnel défini par les bornes des paramètres.
  Pour un modèle à 4 paramètres comme GR4J, c'est un hypercube à 4 dimensions.

- **Optimisation globale vs locale** : les méthodes locales trouvent le minimum le plus proche; les méthodes globales explorent tout l'espace.
  Les modèles hydrologiques exigent des méthodes globales parce que leurs surfaces de réponse comportent de nombreux minimums locaux.

- **Recherche par population** : plutôt que de suivre une seule solution, SCE-UA maintient une population de solutions candidates qui explorent collectivement l'espace des paramètres.

- **Complexe** : un sous-ensemble de la population qui évolue de façon semi-indépendante.
  L'aspect « shuffled » (mélangé) vient du mélange périodique des complexes pour partager l'information.

### Fonctionnement de SCE-UA

SCE-UA procède par un processus itératif d'évolution et de mélange :

**Étape 1 : initialisation**.
Générer une population aléatoire de jeux de paramètres couvrant l'espace des paramètres faisable.
Évaluer la fonction objectif pour chacun.

**Étape 2 : partition en complexes**.
Trier la population par valeur de la fonction objectif et distribuer les points entre les complexes en tourniquet (round-robin).
Chaque complexe contient un mélange de bonnes et de mauvaises solutions.

**Étape 3 : évolution de chaque complexe**.
Au sein de chaque complexe, sélectionner de façon répétée un sous-ensemble de points (simplexe) et l'améliorer par une procédure de Nelder-Mead modifiée :

- Sélectionner les points en favorisant les meilleures solutions (par une distribution triangulaire)
- Calculer un point de réflexion qui s'éloigne de la pire solution
- Si la réflexion améliore la solution, la conserver
- Sinon, essayer une contraction vers le centroïde
- Si tout échoue, générer un point aléatoire

**Étape 4 : mélange**.
Recombiner tous les complexes en une seule population, trier par fonction objectif et redistribuer en nouveaux complexes.
Cela permet à l'information de circuler entre les complexes.

**Étape 5 : vérification de la convergence**.
Arrêter si :

- Le nombre maximal d'évaluations de la fonction est atteint
- Les paramètres ont convergé (tous les complexes ont trouvé des solutions similaires)
- La fonction objectif ne s'améliore plus

**Étape 6 : répéter** à partir de l'étape 2 jusqu'à convergence.

### Paramètres de l'algorithme

SCE-UA possède plusieurs paramètres d'algorithme qui contrôlent son comportement :

| Paramètre | Description | Valeur typique | Effet |
|-----------|-------------|----------------|-------|
| `n_complexes` | Nombre de complexes | 2–5 | Plus de complexes = plus d'exploration, convergence plus lente |
| `max_evaluations` | Nombre maximal d'évaluations de la fonction | 5000–50000 | Budget de calcul |
| `geometric_range_threshold` | Critère de convergence | 0.001 | Arrêt quand les paramètres convergent à cette précision |
| `p_convergence_threshold` | Seuil d'amélioration de l'objectif | 0.1% | Arrêt quand l'amélioration passe sous ce seuil |
| `k_stop` | Nombre d'itérations pour le contrôle d'amélioration | 10 | Fenêtre d'évaluation de l'amélioration |

**Choisir le nombre de complexes :**

- Pour les problèmes simples (4 paramètres) : 2–3 complexes
- Pour les problèmes complexes (7 paramètres et plus) : 4–5 complexes
- Plus de complexes réduisent le risque de convergence prématurée mais augmentent le calcul

### Détails mathématiques

#### Structure de la population

Pour $n$ paramètres de modèle, SCE-UA utilise :

- Points par complexe : $m = 2n + 1$
- Taille du simplexe : $n + 1$
- Pas d'évolution par complexe : $m$
- Population totale : $p = m \times n_{complexes}$

#### Sélection du simplexe

Les points d'un complexe sont sélectionnés pour le simplexe selon une distribution de probabilité triangulaire qui favorise les meilleures solutions :

$$L_{pos} = \left\lfloor (m + 0.5) - \sqrt{(m + 0.5)^2 - m(m+1) \cdot U} \right\rfloor$$

où $U$ est un nombre aléatoire uniforme dans $[0, 1]$.
Cela donne une probabilité plus élevée aux points ayant de meilleures valeurs d'objectif (indices plus faibles dans le complexe trié).

#### Évolution du simplexe

Le pas d'évolution utilise des coefficients de réflexion et de contraction :

- Coefficient de réflexion : $\alpha = 1.0$
- Coefficient de contraction : $\beta = 0.5$

**Réflexion :**

$$\mathbf{x}_{reflect} = \mathbf{c} + \alpha(\mathbf{c} - \mathbf{x}_{worst})$$

où $\mathbf{c}$ est le centroïde de tous les points du simplexe sauf le pire.

**Contraction :**

$$\mathbf{x}_{contract} = \mathbf{x}_{worst} + \beta(\mathbf{c} - \mathbf{x}_{worst})$$

Si ni la réflexion ni la contraction n'améliorent le pire point, un point aléatoire est généré dans les bornes des paramètres.

#### Critères de convergence

**Étendue géométrique normalisée (GNRNG) :**

$$GNRNG = \exp\left(\frac{1}{n}\sum_{i=1}^{n} \ln\left(\frac{range_i}{bounds_i}\right)\right)$$

où $range_i$ est l'étendue du paramètre $i$ dans la population courante et $bounds_i$ son étendue faisable.
Convergence quand $GNRNG < threshold$.

**Critère de variation en pourcentage :**

$$\Delta = \frac{|f_t - f_{t-k}|}{\bar{f}} \times 100$$

où $f_t$ est la meilleure valeur d'objectif à l'itération $t$ et $\bar{f}$ la moyenne des meilleures valeurs récentes.
Convergence quand $\Delta < threshold$.

### Considérations pratiques

#### Avant le calage

1. **Définir soigneusement les bornes des paramètres**.
   Les bornes doivent être physiquement réalistes mais assez larges pour permettre l'exploration.
   Des bornes trop étroites peuvent exclure le véritable optimum; des bornes trop larges gaspillent l'effort de calcul.

2. **Choisir une fonction objectif appropriée**.
   Le NSE met l'accent sur les débits de pointe; le KGE fournit une évaluation plus équilibrée.
   Réfléchissez aux aspects de l'hydrogramme qui comptent le plus pour votre application.

3. **Utiliser une période d'initialisation**.
   La première année de simulation est souvent affectée par les conditions initiales.
   Excluez-la du calcul de la fonction objectif.

4. **Réserver des données pour la validation**.
   N'utilisez pas toutes vos données pour le calage.
   Gardez quelques années de côté pour tester si le modèle calé généralise.

#### Pendant le calage

1. **Suivre la progression**.
   Surveillez :
   - Une amélioration régulière de la fonction objectif
   - Des paramètres convergeant vers des valeurs similaires
   - Une exploration adéquate de l'espace des paramètres

2. **Être patient**.
   L'optimisation globale prend du temps.
   Un arrêt prématuré peut manquer de meilleures solutions.

3. **Exécutions multiples**.
   Lancez le calage plusieurs fois avec des graines aléatoires différentes.
   Si les résultats diffèrent sensiblement, le problème peut avoir plusieurs optimums.

#### Interpréter les résultats

1. **Vérifier les valeurs des paramètres**.
   Des paramètres sur les bornes ou près d'elles peuvent indiquer :
   - Des bornes trop restrictives
   - Une structure de modèle inappropriée
   - Des problèmes de qualité des données

2. **Examiner les résidus**.
   Tracez les débits simulés contre les débits observés.
   Des motifs systématiques (par exemple des pointes toujours sous-estimées) suggèrent des limites structurelles du modèle.

3. **Comparer les métriques**.
   Calculez plusieurs métriques de performance (RMSE, NSE, KGE) même si vous n'en avez optimisé qu'une.
   Cela révèle les compromis.

4. **Valider sur des données indépendantes**.
   Appliquez le modèle calé à des données non utilisées pour le calage.
   Une dégradation de la performance indique un surajustement.

### Problèmes courants et solutions

| Problème | Causes possibles | Solutions |
|----------|------------------|-----------|
| Le calage ne converge jamais | Bornes trop larges, évaluations insuffisantes | Resserrer les bornes, augmenter `max_evaluations` |
| Des exécutions différentes donnent des résultats différents | Optimums locaux multiples | Augmenter `n_complexes`, lancer plusieurs fois |
| Les paramètres atteignent les bornes | Bornes trop restrictives, problèmes de données | Élargir les bornes, vérifier la qualité des données |
| Mauvaise performance en validation | Surajustement, bassin versant non stationnaire | Utiliser une période de calage plus courte, ajouter de la régularisation |
| Progression très lente | Trop de paramètres, modèle coûteux | Réduire la complexité, utiliser une implémentation efficace |

### Options de transformation

HOLMES permet d'appliquer des transformations au débit avant de calculer la fonction objectif :

| Transformation | Formule | Effet |
|----------------|---------|-------|
| Aucune | $Q' = Q$ | Poids égal à tous les débits |
| Logarithmique | $Q' = \ln(Q)$ | Met l'accent sur les étiages |
| Racine carrée | $Q' = \sqrt{Q}$ | Accent modéré sur les étiages |

La transformation logarithmique est utile quand vous voulez que le modèle capture fidèlement la récession, pas seulement les débits de pointe.

### Références

Duan, Q., Sorooshian, S., & Gupta, V. (1992). Effective and efficient global optimization for conceptual rainfall-runoff models. *Water Resources Research*, 28(4), 1015-1031. [https://doi.org/10.1029/91WR02985](https://doi.org/10.1029/91WR02985)

L'article original de SCE-UA, présentant l'algorithme et démontrant son efficacité sur le modèle Sacramento Soil Moisture Accounting.

Duan, Q., Sorooshian, S., & Gupta, V. K. (1994). Optimal use of the SCE-UA global optimization method for calibrating watershed models. *Journal of Hydrology*, 158(3-4), 265-284. [https://doi.org/10.1016/0022-1694(94)90057-4](https://doi.org/10.1016/0022-1694(94)90057-4)

Un article de suivi fournissant des conseils pratiques sur les réglages de l'algorithme et les critères de convergence.

Nelder, J. A., & Mead, R. (1965). A simplex method for function minimization. *The Computer Journal*, 7(4), 308-313.

L'algorithme du simplexe original qui fonde le pas d'évolution des complexes dans SCE-UA.
