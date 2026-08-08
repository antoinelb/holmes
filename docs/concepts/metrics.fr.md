# Métriques de performance

## Aperçu

Après avoir calé un modèle hydrologique, il faut évaluer sa performance.
Les métriques de performance quantifient l'accord entre débits simulés et observés, fournissant des mesures objectives de la qualité du modèle.

Aucune métrique ne capture à elle seule tous les aspects de la performance d'un modèle.
Débits de pointe, étiages, chronologie, volume et variabilité racontent chacun une partie de l'histoire.
Utiliser plusieurs métriques donne une image plus complète des forces et des faiblesses du modèle.

HOLMES implémente trois métriques largement utilisées : le RMSE (Root Mean Square Error, l'erreur quadratique moyenne), le NSE (Nash-Sutcliffe Efficiency) et le KGE (Kling-Gupta Efficiency).
Chacune met l'accent sur des aspects différents de la performance et convient à des applications différentes.

## Notation

Dans toute cette page :

- $O_i$ = débit observé au pas de temps $i$
- $S_i$ = débit simulé au pas de temps $i$
- $\bar{O}$ = moyenne des débits observés
- $\bar{S}$ = moyenne des débits simulés
- $\sigma_O$ = écart-type des observations
- $\sigma_S$ = écart-type des simulations
- $n$ = nombre de pas de temps

## RMSE : erreur quadratique moyenne

### Définition

$$RMSE = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(O_i - S_i)^2}$$

### Interprétation

Le RMSE mesure l'ampleur moyenne des erreurs entre valeurs simulées et observées.
Il a les mêmes unités que les données (par exemple mm/jour ou m³/s), ce qui le rend directement interprétable comme « taille d'erreur typique ».

**Propriétés clés :**

- **Étendue** : $[0, \infty)$
- **Score parfait** : 0 (aucune erreur)
- **Unités** : les mêmes que les données d'entrée
- **Mise au carré** : les grandes erreurs contribuent de façon disproportionnée (une erreur de 10 mm/jour compte 100 fois plus qu'une erreur de 1 mm/jour)

### Quand utiliser le RMSE

- Quand vous avez besoin de l'ampleur de l'erreur en unités physiques
- Quand les grandes erreurs sont particulièrement problématiques
- Pour comparer des modèles appliqués au même bassin versant (pas pour comparer entre bassins, car le RMSE varie avec l'ampleur des débits)

### Limites

- **Dépendant de l'échelle** : un grand bassin versant à forts débits aura naturellement un RMSE plus élevé qu'un petit bassin, même si les deux modèles performent aussi bien en relatif
- **Sensible aux valeurs extrêmes** : quelques grandes erreurs peuvent dominer la métrique
- **Aucune référence de compétence** : le RMSE ne dit pas si le modèle fait mieux qu'une référence simple

### Exemple d'interprétation

Si RMSE = 2.5 mm/jour pour un bassin versant au débit moyen de 5 mm/jour, l'erreur typique est d'environ 50 % du débit moyen — signe d'une performance modérée.
Pour un bassin versant au débit moyen de 25 mm/jour, le même RMSE indiquerait une excellente performance (10 % d'erreur).

## NSE : efficacité de Nash-Sutcliffe

### Définition

$$NSE = 1 - \frac{\sum_{i=1}^{n}(O_i - S_i)^2}{\sum_{i=1}^{n}(O_i - \bar{O})^2}$$

### Interprétation

Le NSE compare les erreurs du modèle à la variance des observations.
Il répond à la question : « Le modèle fait-il mieux que la simple utilisation de la moyenne observée comme prédicteur? »

**Propriétés clés :**

- **Étendue** : $(-\infty, 1]$
- **Score parfait** : 1 (les simulations coïncident exactement avec les observations)
- **Score de référence** : 0 (le modèle vaut la moyenne)
- **Valeurs négatives** : le modèle fait pire que la moyenne
- **Adimensionnel** : comparable entre bassins versants

### Décomposition

Le NSE peut se comprendre comme :

$$NSE = 1 - \frac{MSE}{Var(O)}$$

où MSE est l'erreur quadratique moyenne et Var(O) la variance des observations.
Le modèle doit expliquer plus de variance qu'il n'introduit d'erreur pour atteindre un NSE positif.

### Barème indicatif

| NSE | Interprétation |
|-----|----------------|
| > 0.75 | Très bon |
| 0.65 – 0.75 | Bon |
| 0.50 – 0.65 | Satisfaisant |
| 0.40 – 0.50 | Acceptable pour certains usages |
| < 0.40 | Insatisfaisant |

Ces seuils sont des repères, pas des règles strictes.
La performance acceptable dépend de l'application.

### Quand utiliser le NSE

- Pour une évaluation générale de la performance
- Pour comparer des modèles entre bassins versants différents
- Pour les publications scientifiques (le NSE est la métrique la plus souvent rapportée)

### Limites

- **Accent sur les hauts débits** : parce que les erreurs sont mises au carré, le NSE est dominé par la performance pendant les débits de pointe.
  Un modèle qui capture bien les pointes mais rate les étiages peut quand même avoir un NSE élevé.
- **Sensible à la chronologie** : une simulation correcte en amplitude mais décalée dans le temps aura un mauvais NSE.
- **Référence de la moyenne** : utiliser la moyenne comme référence peut être trop facile dans les bassins versants à forte autocorrélation.

## KGE : efficacité de Kling-Gupta

### Définition

$$KGE = 1 - \sqrt{(r-1)^2 + (\alpha-1)^2 + (\beta-1)^2}$$

où :

- $r$ = coefficient de corrélation de Pearson entre $O$ et $S$
- $\alpha = \frac{\sigma_S}{\sigma_O}$ = ratio des écarts-types (ratio de variabilité)
- $\beta = \frac{\bar{S}}{\bar{O}}$ = ratio des moyennes (ratio de biais)

### Interprétation des composantes

Le KGE décompose la performance en trois aspects indépendants :

| Composante | Symbole | Valeur optimale | Signification |
|------------|---------|-----------------|---------------|
| Corrélation | $r$ | 1 | Chronologie et forme |
| Ratio de variabilité | $\alpha$ | 1 | Amplitude des variations |
| Ratio de biais | $\beta$ | 1 | Bilan hydrique moyen |

**Corrélation ($r$)** : mesure la concordance de la chronologie et du motif des débits simulés avec les observations.
Une corrélation élevée signifie que pointes et creux surviennent aux bons moments, même si les amplitudes diffèrent.

**Ratio de variabilité ($\alpha$)** : compare la « dispersion » des simulations à celle des observations.
$\alpha > 1$ signifie des simulations trop variables; $\alpha < 1$ des simulations trop amorties.

**Ratio de biais ($\beta$)** : compare les débits moyens.
$\beta > 1$ signifie que le modèle surestime en moyenne; $\beta < 1$ qu'il sous-estime.

### Forme développée

Les composantes se calculent comme :

$$r = \frac{\sum_{i=1}^{n}(O_i - \bar{O})(S_i - \bar{S})}{\sqrt{\sum_{i=1}^{n}(O_i - \bar{O})^2} \cdot \sqrt{\sum_{i=1}^{n}(S_i - \bar{S})^2}}$$

$$\alpha = \frac{\sigma_S}{\sigma_O} = \frac{\sqrt{\frac{1}{n}\sum_{i=1}^{n}(S_i - \bar{S})^2}}{\sqrt{\frac{1}{n}\sum_{i=1}^{n}(O_i - \bar{O})^2}}$$

$$\beta = \frac{\bar{S}}{\bar{O}}$$

### Propriétés clés

- **Étendue** : $(-\infty, 1]$
- **Score parfait** : 1 (toutes les composantes égales à 1)
- **Référence** : KGE = -0.41 correspond à l'utilisation de la moyenne observée (comme NSE = 0)
- **Adimensionnel** : comparable entre bassins versants
- **Diagnostique** : les composantes révèlent les aspects à améliorer

### Barème indicatif

| KGE | Interprétation |
|-----|----------------|
| > 0.75 | Très bon |
| 0.50 – 0.75 | Bon |
| 0.00 – 0.50 | Acceptable |
| < 0.00 | Mauvais |

### Quand utiliser le KGE

- Quand vous voulez une information diagnostique sur les erreurs du modèle
- Quand le bilan hydrique (le biais) compte pour votre application
- Quand vous voulez une évaluation plus équilibrée que celle du NSE
- Pour l'hydrologie opérationnelle, où les volumes totaux comptent

### Avantages sur le NSE

1. **Évaluation équilibrée** : le NSE peut être élevé malgré un biais important si la variabilité est capturée.
   Le KGE pénalise explicitement le biais.

2. **Valeur diagnostique** : les composantes disent quoi corriger.
   Mauvais $r$? Travaillez la chronologie.
   Mauvais $\beta$? Ajustez le bilan hydrique.

3. **Référence plus intuitive** : NSE = 0 correspond à l'utilisation de la moyenne, mais KGE = 0 est un seuil plus significatif en pratique.

## Comparaison des métriques

| Aspect | RMSE | NSE | KGE |
|--------|------|-----|-----|
| **Unités** | Les mêmes que les données | Adimensionnel | Adimensionnel |
| **Étendue** | $[0, \infty)$ | $(-\infty, 1]$ | $(-\infty, 1]$ |
| **Parfait** | 0 | 1 | 1 |
| **Comparaison entre bassins** | Non | Oui | Oui |
| **Accent** | Toutes les erreurs également (au carré) | Hauts débits | Équilibré |
| **Diagnostique** | Non | Limité | Oui (3 composantes) |
| **Sensibilité au biais** | Implicite | Faible | Élevée |
| **Usage le plus courant** | Ampleur de l'erreur | Recherche | Opérationnel |

## Choisir une métrique

Le choix de la métrique doit s'aligner sur vos objectifs de modélisation :

**Pour la prévision des crues** : NSE ou RMSE, car la précision des débits de pointe compte le plus.

**Pour la planification des ressources en eau** : KGE, parce que le bilan hydrique (les volumes totaux) est critique.

**Pour l'évaluation des étiages** : envisagez de transformer les débits (logarithme ou racine carrée) avant de calculer les métriques, ou utilisez des métriques d'étiage spécifiques.

**Pour la recherche et la publication** : rapportez plusieurs métriques.
Le NSE pour la comparabilité avec la littérature; le KGE pour l'éclairage diagnostique; le RMSE pour l'interprétation physique.

**Bonne pratique** : rapportez toujours au moins deux métriques.
Un NSE élevé avec de mauvaises composantes de KGE (par exemple une moyenne biaisée) révèle des limites importantes du modèle.

## Conseils pratiques

1. **Examinez les graphiques de séries temporelles** en plus des métriques.
   Une métrique est un résumé; le graphique montre les détails.

2. **Calculez les métriques par sous-périodes** : calage vs validation, années humides vs sèches, saisons différentes.
   La performance peut varier.

3. **Envisagez une transformation des débits** : la transformation logarithmique met l'accent sur les étiages; la racine carrée offre un accent intermédiaire.

4. **Méfiez-vous des valeurs suspectes** : une seule observation manquante codée -999 peut ruiner toutes les métriques.
   Vérifiez d'abord la qualité des données.

5. **Rapportez l'incertitude** : si vous lancez plusieurs calages, rapportez l'étendue des métriques, pas seulement la meilleure exécution.

## Références

Nash, J. E., & Sutcliffe, J. V. (1970). River flow forecasting through conceptual models part I—A discussion of principles. *Journal of Hydrology*, 10(3), 282-290. [https://doi.org/10.1016/0022-1694(70)90255-6](https://doi.org/10.1016/0022-1694(70)90255-6)

L'article fondateur introduisant le NSE, l'un des articles les plus cités en hydrologie.
Il établit le concept de comparaison des erreurs du modèle à la variance des observations.

Gupta, H. V., Kling, H., Yilmaz, K. K., & Martinez, G. F. (2009). Decomposition of the mean squared error and NSE performance criteria: Implications for improving hydrological modelling. *Journal of Hydrology*, 377(1-2), 80-91. [https://doi.org/10.1016/j.jhydrol.2009.08.003](https://doi.org/10.1016/j.jhydrol.2009.08.003)

Introduit le KGE et démontre ses avantages sur le NSE.
Montre comment le NSE peut masquer d'importantes déficiences du modèle.

Moriasi, D. N., Arnold, J. G., Van Liew, M. W., Bingner, R. L., Harmel, R. D., & Veith, T. L. (2007). Model evaluation guidelines for systematic quantification of accuracy in watershed simulations. *Transactions of the ASABE*, 50(3), 885-900.

Fournit des lignes directrices largement citées sur les niveaux de performance acceptables (NSE > 0.5 pour une performance satisfaisante).
