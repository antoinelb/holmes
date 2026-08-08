# Modèle PDM

## Aperçu

PDM (Probability-Distributed Model) est un modèle pluie-débit global journalier à huit paramètres développé à l'origine par Moore et Clarke (1981) à l'Institute of Hydrology, Wallingford, au Royaume-Uni.
C'est l'un des modèles conceptuels les plus utilisés en hydrologie opérationnelle britannique, et son idée centrale — une capacité d'humidité du sol distribuée selon une loi de Pareto — a ensuite été adoptée par HYMOD, Xinanjiang et VIC.

L'implémentation HOLMES suit la version modifiée à huit paramètres de HOOPLA (HM13), qui étend le PDM0 à six paramètres de Perrin avec un facteur de correction de la pluie ($X_7$) et un mécanisme de vidange à seuil contrôlé par $X_3$ et $X_8$.
Structurellement, le modèle représente un bassin versant par quatre réservoirs en interaction : un réservoir de sol de Pareto, un réservoir souterrain cubique et deux réservoirs linéaires de routage rapide en série, reliés par un hydrogramme unitaire à délai fractionnaire.

PDM est un choix naturel quand l'analyste veut une représentation explicite de la variabilité spatiale de la capacité d'humidité du sol sans s'engager dans un modèle entièrement distribué.
Son réservoir souterrain cubique fournit également une récession de débit de base non linéaire que beaucoup de modèles linéaires plus simples ne peuvent pas reproduire.

## Concepts clés

- **Réservoir de sol distribué selon Pareto** : le bassin versant est modélisé comme un ensemble de colonnes de sol dont les capacités maximales suivent une distribution de Pareto.
Le paramètre $C_{\max}$ ($X_1$) fixe la plus grande capacité, et le paramètre $b$ ($X_2$) contrôle la variabilité spatiale : un $b$ faible donne un réservoir quasi uniforme, un $b$ élevé signifie qu'une petite fraction du bassin sature rapidement.

- **Excès de saturation** : quand la pluie tombe sur des parties du bassin déjà pleines, elle ne peut pas s'infiltrer et devient immédiatement du ruissellement de surface ($U_{t1}$).

- **Excès d'infiltration** : même pour les parties du bassin qui ne sont pas complètement saturées, la pluie nette peut dépasser l'augmentation du stockage du sol, produisant un ruissellement additionnel ($U_{t2}$).

- **Vidange à seuil** : la vidange de subsurface du réservoir de sol ne se produit que lorsque $S$ dépasse une fraction $\alpha$ ($X_3$) du stockage maximal du sol, à un taux contrôlé par la constante de temps de vidange $X_8$.

- **Réservoir souterrain cubique** : un réservoir non linéaire où la sortie dépend du cube du volume stocké rapporté à un stockage caractéristique $X_5$, produisant une courbe de récession concave qui reproduit mieux le comportement observé du débit de base.

- **Cascade linéaire à deux étages** : le ruissellement de surface passe par deux réservoirs linéaires en série (tous deux de temps de résidence $X_6$), produisant une réponse rapide lissée et retardée.

- **Routage à délai fractionnaire** : la sortie combinée rapide-plus-lente est retardée de $X_4$ jours par interpolation linéaire, représentant le temps de parcours en rivière jusqu'à l'exutoire du bassin.

- **Facteur de correction de la pluie** : les précipitations brutes sont multipliées par $X_7$ avant d'entrer dans le modèle, permettant de corriger la sous-captation du pluviomètre ou la représentativité spatiale.

## Fonctionnement

Le modèle PDM traite les précipitations et l'évapotranspiration potentielle à travers les étapes suivantes :

**Étape 1 : correction de la pluie**.
Les précipitations brutes sont multipliées par $X_7$ pour obtenir la précipitation efficace $P_1 = P \cdot X_7$.
Cela corrige le biais systématique du pluviomètre et le sous-échantillonnage spatial.

**Étape 2 : excès de saturation**.
Le modèle calcule la profondeur uniforme équivalente actuellement remplie à l'aide de la distribution de Pareto inverse, puis détermine quelle fraction du bassin est déjà saturée.
Toute pluie dépassant la capacité restante sur la fraction saturée devient l'excès de saturation $U_{t1}$, qui quitte le réservoir de sol immédiatement.

**Étape 3 : mise à jour de l'humidité du sol**.
La pluie nette $P_n = P_1 - U_{t1}$ est distribuée sur le réservoir de Pareto par l'intégrale de Pareto directe, mettant à jour l'eau du sol $S$.
Toute pluie nette qui n'a pas pu entrer dans le réservoir (parce que le sol a absorbé moins que $P_n$) devient l'excès d'infiltration $U_{t2}$.

**Étape 4 : évapotranspiration**.
L'ETP est pondérée par une fonction non linéaire du remplissage courant du sol : $\text{factor} = 1 - (1 - \text{fill})^2$, où $\text{fill} = S / X_1 \cdot (X_2 + 1)$.
L'évapotranspiration est donc maximale quand le sol est humide et diminue quadratiquement à mesure qu'il s'assèche.

**Étape 5 : vidange à seuil**.
Si l'eau du sol $S$ dépasse le seuil $\alpha \cdot S_{\max}$ (où $S_{\max} = X_1 / (X_2 + 1)$), l'excès se vide vers le réservoir souterrain au taux $(S - \text{threshold}) / X_8$.
Quand $S$ est sous le seuil, aucune vidange ne se produit — le sol retient toute son eau.

**Étape 6 : routage rapide**.
Le ruissellement de surface $U_q = U_{t1} + U_{t2}$ entre dans une cascade de deux réservoirs linéaires (M et N), chacun se vidant au taux $1/X_6$ par pas de temps.
Les deux réservoirs en série lissent la réponse rapide, produisant une pointe d'hydrogramme amortie.

**Étape 7 : routage lent**.
La vidange de l'étape 5 entre dans le réservoir souterrain cubique $T$, qui relâche l'eau selon $Q_t = T \cdot (1 - (1 + (T/X_5)^2)^{-1/2})$.
Cette formule non linéaire produit de grandes sorties quand le réservoir est plein mais des sorties infimes en période sèche.

**Étape 8 : routage par délai**.
La somme des composantes rapide et lente $(Q_t + Q_3)$ est convoluée avec un hydrogramme unitaire à délai fractionnaire de longueur $\lceil X_4 \rceil + 1$, produisant le débit simulé final.

## Paramètres

Le modèle PDM possède huit paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ ($C_{\max}$) | Capacité maximale d'humidité du sol | 10–2000 | mm | Borne supérieure de la distribution de Pareto des capacités de stockage locales. Des valeurs élevées augmentent la rétention totale d'eau et réduisent la vivacité de la réponse. |
| $X_2$ ($b$) | Variabilité spatiale de la capacité d'humidité du sol | 0.01–2.0 | - | Paramètre de forme de la distribution de Pareto. Des valeurs faibles donnent un seau uniforme; des valeurs élevées concentrent la capacité dans une petite fraction du bassin. |
| $X_3$ ($\alpha$) | Fraction seuil de vidange | 0.01–0.99 | - | Fraction du stockage maximal du sol qui doit être remplie avant que la vidange vers la nappe ne commence. Des valeurs élevées suppriment la vidange sauf en période humide. |
| $X_4$ (Délai) | Délai de routage | 0.5–5.0 | jours | Temps de parcours en rivière jusqu'à l'exutoire du bassin. Décale l'hydrogramme entier sans en changer la forme. |
| $X_5$ ($S_c$) | Stockage caractéristique du réservoir souterrain cubique | 1–2000 | mm | Paramètre d'échelle du réservoir souterrain non linéaire. Des valeurs élevées ralentissent la récession du débit de base et augmentent le volume retenu en subsurface. |
| $X_6$ ($\tau_q$) | Constante de vidange du routage linéaire | 1–30 | jours | Temps de résidence de chacun des deux réservoirs linéaires rapides. Contrôle la largeur et l'amortissement de la pointe d'écoulement rapide. |
| $X_7$ ($P_{\text{corr}}$) | Facteur de correction de la pluie | 0.5–1.5 | - | Mise à l'échelle multiplicative des précipitations brutes. Des valeurs sous 1.0 réduisent la pluie efficace; des valeurs au-dessus de 1.0 l'augmentent. |
| $X_8$ ($\tau_d$) | Constante de temps de vidange | 1–100 | jours | Contrôle la vitesse à laquelle l'eau du sol au-dessus du seuil se vide vers le réservoir souterrain. De petites valeurs donnent une vidange rapide; de grandes valeurs la rendent paresseuse. |

**Comprendre les paramètres :**

- **$X_1$ et $X_2$ ensemble** définissent le réservoir de sol, exactement comme dans HYMOD.
$X_1$ fixe le plafond; $X_2$ détermine si toutes les cellules saturent à des profondeurs similaires ($X_2 \approx 0$) ou si quelques cellules saturent très tôt tandis que d'autres retiennent beaucoup plus ($X_2 \approx 2$).
- **$X_3$ et $X_8$ ensemble** contrôlent le mécanisme de vidange à seuil.
$X_3$ détermine quand la vidange commence (à quel point le sol doit être humide), et $X_8$ détermine sa vitesse une fois le seuil franchi.
Un $X_3$ élevé avec un grand $X_8$ donne très peu de recharge du débit de base; un $X_3$ faible avec un petit $X_8$ alimente le réservoir souterrain agressivement.
- **$X_5$** gouverne la non-linéarité de la récession du débit de base.
Quand le réservoir souterrain $T$ est petit par rapport à $X_5$, la sortie est quasi cubique ($\propto T^3$); quand $T \gg X_5$, la sortie tend vers $T$ (linéaire).
En pratique, $X_5$ devrait être calé pour reproduire la forme des récessions de débit de base observées.
- **$X_6$** affecte le moment du pic et l'atténuation de l'écoulement rapide.
Avec deux réservoirs en série, la cascade agit comme un filtre gamma de délai moyen $2 \cdot X_6$.
- **$X_7$** est utile quand le réseau de pluviomètres sous-représente le bassin, ou quand il existe un biais d'altitude connu.

## Formulation mathématique

### Initialisation

$$S_0 = \min\left(0.2 \cdot X_1, \frac{X_1}{X_2 + 1}\right), \quad T_0 = 20, \quad M_0 = 30, \quad N_0 = 30$$

où $S$ est l'eau du sol, $T$ le réservoir souterrain et $M, N$ les deux réservoirs de routage rapide.
L'initialisation du sol est bornée à $X_1 / (X_2 + 1)$ pour préserver l'invariant de Pareto nécessaire pour que la formule inverse reste à valeurs réelles.

### Réservoir d'humidité du sol de Pareto

La formule de Pareto inverse donne la capacité équivalente actuellement remplie :

$$C_{\text{prev}} = X_1 \cdot \left(1 - \max\left(1 - \frac{(X_2 + 1) \cdot S}{X_1},\, 0\right)^{1/(X_2 + 1)}\right)$$

Excès de saturation issu de la pluie $P_1 = P \cdot X_7$ :

$$U_{t1} = \max(P_1 - X_1 + C_{\text{prev}},\, 0)$$

$$P_n = P_1 - U_{t1}$$

Mise à jour de Pareto directe :

$$\text{Dum} = \min\left(1, \frac{C_{\text{prev}} + P_n}{X_1}\right)$$

$$S \leftarrow \frac{X_1}{X_2 + 1} \cdot \left(1 - (1 - \text{Dum})^{X_2 + 1}\right)$$

Excès d'infiltration :

$$U_{t2} = \max(P_n - (S - S_{\text{prev}}),\, 0)$$

### Évapotranspiration

L'évapotranspiration est pondérée par la fraction de remplissage courante du sol selon une réduction quadratique :

$$\text{fill} = \frac{S}{X_1} \cdot (X_2 + 1)$$

$$\text{factor} = 1 - (1 - \text{fill})^2$$

$$S \leftarrow \max(S - E \cdot \text{factor},\, 0)$$

### Vidange à seuil

La vidange ne se produit que lorsque le sol dépasse une fraction $X_3$ du stockage maximal :

$$\text{threshold} = \frac{X_1}{X_2 + 1} \cdot X_3$$

$$D = \begin{cases} \frac{S - \text{threshold}}{X_8} & \text{if } S > \text{threshold} \\ 0 & \text{otherwise} \end{cases}$$

$$S \leftarrow S - D$$

### Routage rapide : cascade linéaire à deux étages

Le ruissellement de surface $U_q = U_{t1} + U_{t2}$ entre dans deux réservoirs linéaires en série :

$$M \leftarrow M + U_q, \quad Q_1 = \frac{M}{X_6}, \quad M \leftarrow M - Q_1$$

$$N \leftarrow N + Q_1, \quad Q_2 = \frac{N}{X_6}, \quad N \leftarrow N - Q_2$$

### Routage lent : réservoir souterrain cubique

Le réservoir souterrain $T$ reçoit la vidange $D$ et relâche l'eau de façon non linéaire :

$$T \leftarrow T + D$$

$$Q_t = T \cdot \left(1 - \left(1 + \left(\frac{T}{X_5}\right)^2\right)^{-1/2}\right)$$

$$T \leftarrow T - Q_t$$

Cette formule produit un comportement quasi cubique pour $T \ll X_5$ et quasi linéaire pour $T \gg X_5$.

### Routage par délai

La sortie combinée $(Q_t + Q_2)$ est convoluée avec un hydrogramme unitaire fractionnaire de longueur $k = \lceil X_4 \rceil + 1$ :

$$d_{k-2} = \frac{1}{X_4 - k + 3}, \quad d_{k-1} = 1 - d_{k-2}$$

$$Q_{\text{sim}}(t) = \max\left(\text{delayed}(Q_t + Q_2, X_4),\, 0\right)$$

## Références

Moore, R. J., & Clarke, R. T. (1981).
A distribution function approach to rainfall runoff modeling.
*Water Resources Research*, 17(5), 1367–1382.

Moore, R. J. (1985).
The probability-distributed principle and runoff production at point and basin scales.
*Hydrological Sciences Journal*, 30(2), 273–297.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis).
INPG, Grenoble.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
