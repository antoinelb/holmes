# Modèle MOHYSE

## Aperçu

MOHYSE (MOdèle HYdrologique Simplifié à l'Extrême) est un modèle pluie-débit global journalier développé par Fortin et Turcotte à l'Université Laval, au Canada (2007).
Son nom reflète sa philosophie de conception : capturer les processus essentiels de l'hydrologie d'un bassin versant avec le moins de composantes structurelles possible.

Le modèle représente un bassin versant avec seulement deux réservoirs (sol et eau souterraine) reliés par des voies de vidange linéaires, avec un hydrogramme unitaire en forme de gamma pour répartir l'écoulement dans le temps.
Avec sept paramètres et une structure entièrement linéaire (aucune sortie en loi de puissance, aucune dynamique de sol non linéaire), MOHYSE est l'un des modèles les plus simples de la collection HOLMES.
Cela en fait un excellent point de départ pédagogique pour comprendre comment la production, le routage et la convolution interagissent dans un modèle conceptuel.

Malgré sa simplicité, MOHYSE fournit un bon point de référence pour comparer des structures de modèles plus complexes.
Quand un modèle plus complexe ne parvient pas à surpasser MOHYSE, cela suggère que la complexité structurelle additionnelle n'est pas justifiée par les données.

## Concepts clés

- **Interception** : évaporation directe d'une fraction de la pluie avant qu'elle n'atteigne la surface du sol.
MOHYSE intercepte exactement $\min(P, E)$ — la pluie à hauteur de la demande atmosphérique — en la retirant avant tout autre processus.

- **Infiltration limitée par la capacité** : l'eau entre dans le réservoir de sol à un taux qui décroît linéairement à mesure que le réservoir se remplit vers sa capacité maximale $X_2$.
Quand le sol est saturé, toute la pluie nette devient du ruissellement de surface.

- **Transpiration** : évapotranspiration puisée dans le réservoir de sol, contrôlée par le coefficient $X_1$.
Le taux de transpiration réel est limité à la fois par l'humidité du sol disponible et par la demande atmosphérique résiduelle après interception.

- **Drainage de la zone vadose** : écoulement gravitaire depuis le sol non saturé par deux voies parallèles : l'une drainant directement vers la rivière ($X_4$) et l'autre percolant vers le réservoir d'eau souterraine ($X_3$).

- **Débit de base souterrain** : vidange lente du réservoir d'eau souterraine vers la rivière, contrôlée par le coefficient de vidange $X_5$.
Représente la composante d'écoulement soutenue qui persiste entre les événements pluvieux.

- **Hydrogramme unitaire gamma** : une fonction de transfert en forme de cloche définie par un paramètre de forme ($X_6$) et un paramètre d'échelle ($X_7$) qui étale l'écoulement total sur plusieurs pas de temps.
Contrairement aux hydrogrammes unitaires triangulaires ou rectangulaires plus simples, la distribution gamma permet un contrôle flexible à la fois du moment du pic et de la longueur de la queue.

## Fonctionnement

**Étape 1 : interception**.
La pluie passe d'abord par une couche d'interception où une quantité égale à $\min(P, E)$ s'évapore directement.
Cela représente l'interception par la canopée et l'évaporation de surface.
La pluie restante $(P - E_d)$ est disponible pour l'infiltration et le ruissellement, tandis que la demande atmosphérique restante $(E - E_d)$ peut alimenter la transpiration depuis le sol.

**Étape 2 : infiltration et ruissellement de surface**.
La pluie nette s'infiltre dans le réservoir de sol à un taux proportionnel à la capacité de stockage restante : $I = (P - E_d) \cdot (1 - S / X_2)$.
Quand le sol est presque vide, presque toute l'eau s'infiltre; quand il approche de sa capacité $X_2$, la majeure partie devient du ruissellement de surface $Q_1 = P - E_d - I$.

**Étape 3 : transpiration**.
L'atmosphère puise l'eau du sol à un taux proportionnel à la teneur en eau du sol, modulé par le coefficient $X_1$.
La transpiration est limitée au plus petit de $X_1 \cdot S$ et de l'ETP résiduelle après interception, garantissant que le sol ne peut fournir plus d'eau qu'il n'en contient ou que l'atmosphère n'en demande.

**Étape 4 : drainage de subsurface**.
Deux voies de vidange linéaires vident le réservoir de sol en parallèle.
Une fraction $X_4 \cdot S$ draine directement vers la rivière (représentant un écoulement hypodermique peu profond), tandis que $X_3 \cdot S$ percole vers le réservoir d'eau souterraine (représentant une recharge plus profonde).
Les deux coefficients sont petits (0.001 à 1.0), reflétant la vidange relativement lente de la zone vadose.

**Étape 5 : débit de base souterrain**.
Le réservoir d'eau souterraine relâche de l'eau vers la rivière au taux $X_5 \cdot R$, produisant la composante lente du débit de base.
Le réservoir reçoit l'eau du drainage du sol et n'en perd que par cette sortie linéaire.

**Étape 6 : routage par l'hydrogramme unitaire**.
L'écoulement total des trois voies ($Q_1 + Q_2 + Q_3$) est routé à travers un hydrogramme unitaire en forme de gamma défini par les paramètres de forme ($X_6$) et d'échelle ($X_7$).
Comme les trois sorties passent par la même convolution, cela équivaut (par linéarité) à router chaque composante séparément puis à sommer les résultats.
La mémoire de l'hydrogramme unitaire s'étend sur 80 pas de temps, ce qui est suffisamment long pour capturer la queue complète de la distribution gamma pour toute combinaison de paramètres dans les bornes de calage.

## Paramètres

Le modèle MOHYSE possède 7 paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Coefficient de transpiration | 0.01–1.0 | - | Fraction de l'humidité du sol disponible pour la transpiration par pas de temps. Des valeurs élevées permettent un assèchement plus rapide du sol. |
| $X_2$ | Capacité maximale d'infiltration | 1–2000 | mm | Stockage maximal d'eau dans le sol. Contrôle la quantité d'eau que le sol peut retenir avant de saturer. |
| $X_3$ | Coefficient de vidange de la zone vadose vers l'aquifère | 0.001–1.0 | - | Fraction de l'humidité du sol drainant vers le réservoir d'eau souterraine par pas de temps. |
| $X_4$ | Coefficient de vidange de la zone vadose vers la rivière | 0.001–1.0 | - | Fraction de l'humidité du sol drainant directement vers la rivière par pas de temps. |
| $X_5$ | Coefficient de vidange de l'aquifère vers la rivière | 0.001–1.0 | - | Fraction du stockage d'eau souterraine relâchée en débit de base par pas de temps. |
| $X_6$ | Paramètre de forme de l'hydrogramme unitaire | 1.0–5.0 | - | Forme (alpha) de la distribution gamma. Des valeurs élevées décalent le pic plus tard et produisent une forme plus symétrique. |
| $X_7$ | Paramètre d'échelle de l'hydrogramme unitaire | 0.5–5.0 | - | Échelle (beta) de la distribution gamma. Des valeurs élevées étalent la réponse sur plus de pas de temps. |

**Comprendre les paramètres :**

- **$X_1$** et **$X_2$** gouvernent ensemble la phase de production.
Un grand $X_2$ (sol profond) retarde la saturation, tandis qu'un grand $X_1$ (transpiration rapide) accélère l'assèchement entre les événements.
Commencez le calage en ajustant $X_2$ pour reproduire le bilan hydrique global, puis affinez $X_1$ pour reproduire la récession en période sèche.
- **$X_3$**, **$X_4$** et **$X_5$** contrôlent la répartition de l'écoulement.
Augmenter $X_4$ par rapport à $X_3$ envoie plus d'eau directement à la rivière (réponse plus vive); augmenter $X_3$ en gardant $X_5$ petit produit un hydrogramme plus lent, davantage dominé par l'eau souterraine.
Le rapport $X_4 / X_3$ est souvent plus informatif que chacune des valeurs prises isolément.
- **$X_6$** et **$X_7$** façonnent l'hydrogramme unitaire.
Avec $X_6 \approx 1$, l'HU est en décroissance exponentielle (pic au jour 1); avec $X_6 = 3\text{–}5$, le pic se décale aux jours 2–4 et la réponse devient plus en forme de cloche.
$X_7$ étire ou comprime la queue.
- Parce que les cinq coefficients de vidange ($X_1$ à $X_5$) sont fractionnaires et linéaires, MOHYSE peut présenter de l'équifinalité quand $X_3$ et $X_4$ se compensent mutuellement.
Fixer l'un d'eux ou contraindre leur rapport peut améliorer l'identifiabilité.

## Formulation mathématique

### Initialisation

Les états initiaux des réservoirs suivent les valeurs par défaut de HOOPLA HM10 :

$$S_0 = 40 \text{ mm}, \quad R_0 = 30 \text{ mm}$$

où $S$ est le réservoir d'humidité du sol et $R$ le réservoir d'eau souterraine.

### Interception

L'évaporation directe retire le plus petit des précipitations et de l'ETP :

$$E_d = \min(P, E)$$

### Transpiration

L'eau puisée dans le sol est limitée par la teneur du sol et la demande atmosphérique résiduelle :

$$T_r = \min(X_1 \cdot S, \; E - E_d)$$

### Infiltration

La pluie nette entre dans le sol à un taux qui décroît linéairement avec la saturation :

$$
I = \begin{cases}
(P - E_d) \cdot \left(1 - \dfrac{S}{X_2}\right) & \text{if } S < X_2 \\[6pt]
0 & \text{if } S \geq X_2
\end{cases}
$$

### Ruissellement de surface

L'eau qui ne peut pas s'infiltrer devient du ruissellement de surface :

$$Q_1 = P - E_d - I$$

### Drainage de la zone vadose

Deux voies de vidange parallèles vident le réservoir de sol :

$$Q_2 = X_4 \cdot S \quad \text{(direct to river)}$$

$$Q_t = X_3 \cdot S \quad \text{(to groundwater)}$$

### Débit de base souterrain

$$Q_3 = X_5 \cdot R$$

### Mise à jour des états

$$S \leftarrow \max(S + I - T_r - Q_t - Q_2, \; 0)$$

$$R \leftarrow \max(R + Q_t - Q_3, \; 0)$$

### Hydrogramme unitaire gamma

Les ordonnées de l'hydrogramme unitaire sont calculées à partir d'une distribution gamma de forme $\alpha = X_6$ et d'échelle $\beta = X_7$ :

$$h(t) = \frac{t^{\alpha - 1} \cdot e^{-t/\beta}}{\displaystyle\sum_{j=1}^{k} j^{\alpha - 1} \cdot e^{-j/\beta}}, \quad t = 1, 2, \ldots, k$$

où $k = 80$ est la longueur de mémoire fixe et le dénominateur normalise les ordonnées pour qu'elles somment à 1.

### Débit total

L'écoulement total est la somme des trois voies, routée à travers l'hydrogramme unitaire par convolution en décalage-addition :

$$Q_{\text{total}}(t) = Q_1(t) + Q_2(t) + Q_3(t)$$

$$Q(t) = \sum_{j=1}^{k} h(j) \cdot Q_{\text{total}}(t - j + 1)$$

Le débit de sortie $Q(t) = \max(Q(t), 0)$ est contraint à être non négatif.

## Références

- Fortin, V., & Turcotte, R. (2007). *Le modèle hydrologique MOHYSE*. Note de cours pour SCA7420, Département des sciences de la terre et de l'atmosphère, Université du Québec à Montréal.
- Arsenault, R., Brissette, F., Martel, J.-L., Troin, M., Lévesque, G., Davidson-Chaput, J., Gonzalez, M. C., Ameli, A., & Poulin, A. (2020). A comprehensive, multisource database for hydrometeorological modeling of 14,425 North American watersheds. *Scientific Data*, 7(1), 243. [DOI](https://doi.org/10.1038/s41597-020-00583-2)
