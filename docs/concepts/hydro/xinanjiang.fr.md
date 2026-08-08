# Modèle XINANJIANG

## Aperçu

Le modèle **XINANJIANG** a été développé par Zhao, Zhuang, Fang, Liu et Zhang en 1980 à la Hohai University de Nanjing, en Chine, pour la modélisation pluie-débit des bassins versants humides et semi-humides du bassin de la rivière Xin'anjiang.
C'est l'un des modèles hydrologiques les plus utilisés en Chine et il a été l'ossature de calcul de nombreux systèmes opérationnels de prévision de crues.
Le modèle original compte plus d'une douzaine de paramètres; HOLMES implémente la variante à 8 paramètres décrite dans la thèse de Perrin (HOOPLA HM20), qui conserve le squelette structurel de Zhao et al. mais fixe ou absorbe une poignée de paramètres de processus mineurs.

Structurellement, XINANJIANG représente un bassin versant comme **deux réservoirs de stockage à distribution en loi de puissance en série** (un réservoir de sol et un réservoir d'eau libre), qui génèrent tous deux du ruissellement par excès de saturation sur une capacité spatialement variable.
Le réservoir d'eau libre se vide ensuite dans une paire de **réservoirs linéaires parallèles** (un rapide, un lent), et l'écoulement combiné est finalement lissé par un court **hydrogramme unitaire à deux poids** qui gère les délais fractionnaires.

Un étudiant pourrait choisir XINANJIANG plutôt que GR4J ou HBV lorsqu'il souhaite une représentation explicite de la **variabilité spatiale de la capacité de stockage** au sein du bassin versant : le mécanisme de ruissellement par excès de saturation est physiquement motivé par l'observation que différentes parties d'un bassin se saturent à des moments différents, et la distribution en loi de puissance des capacités est la façon la plus simple de capturer cela sans modèle entièrement distribué.

## Concepts clés

- **Ruissellement par excès de saturation** : mécanisme de génération du ruissellement dans lequel la pluie ne devient débit que là où le sol est déjà saturé. La fraction de surface saturée croît à mesure que le stockage moyen du bassin augmente.
- **Stockage à distribution en loi de puissance** : la variabilité spatiale des capacités de stockage ponctuelles est modélisée par un unique paramètre de forme en loi de puissance, de sorte qu'à tout niveau d'humidité du sol une fraction analytique du bassin est saturée.
- **Réservoir de sol $S$** : le réservoir principal d'eau de tension, représentant l'eau retenue par la capillarité du sol. Il pilote l'évapotranspiration et contrôle le déclenchement du ruissellement.
- **Réservoir d'eau libre $R$** : un réservoir secondaire d'eau gravitaire recevant le ruissellement généré par le réservoir de sol. Sa sortie alimente le réseau de routage.
- **Répartition routage rapide / lent** : l'eau quittant le réservoir d'eau libre est répartie entre un réservoir linéaire rapide (surface / écoulement hypodermique) et un réservoir linéaire lent (débit de base) par le coefficient de répartition $X_1$.
- **Réservoirs de routage linéaires $T$ et $M$** : deux réservoirs linéaires parallèles aux constantes de temps différentes; ensemble, ils donnent au modèle une signature de récession bi-exponentielle.
- **Hydrogramme unitaire à deux poids** : un hydrogramme unitaire très court dont la masse porte uniquement sur les deux dernières ordonnées, utilisé pour représenter des délais de concentration fractionnaires entre 0.5 et 10 jours.

## Fonctionnement

À chaque pas de temps, le modèle reçoit une entrée de précipitation $P$ et une demande d'évapotranspiration potentielle $E$, et retourne une valeur de débit $Q$.
La logique interne suit ces sept étapes.

**Étape 1 : entrées nettes**.
Calculer la précipitation nette $P_n = \max(P - E, 0)$ et l'ETP nette $E_n = \max(E - P, 0)$, de sorte qu'au plus une des deux est non nulle.
Si $E_n > 0$, le pas de temps est « sec » et seule l'évapotranspiration a lieu; si $P_n > 0$, il est « humide » et toute la chaîne de production / routage s'active.

**Étape 2 : évapotranspiration par morceaux**.
Lors d'un pas sec, l'ET réelle est prélevée dans le réservoir de sol $S$ à un taux qui dépend de la saturation relative $S / X_5$ : sans entrave quand $S/X_5 \ge 0.9$, à 10 % de la demande quand $S/X_5 < 0.09$, et interpolée linéairement entre les deux.
Cela reproduit l'observation qu'un sol presque vide libère l'eau beaucoup plus lentement qu'un sol humide.

**Étape 3 : excès de saturation du réservoir de sol**.
Lors d'un pas humide, une formule d'excès de saturation à distribution en loi de puissance de type Zhao calcule la fraction du bassin où le réservoir de sol est déjà plein et route la pluie correspondante directement vers le réservoir d'eau libre comme flux traversant $P_s$.
L'exposant de forme fixe $B = 0.25$ de la variante de Perrin est utilisé ici.

**Étape 4 : excès de saturation de l'eau libre**.
Le flux traversant $P_r = P_n - P_s$ entre dans le réservoir d'eau libre $R$ (capacité $X_4$), où une seconde étape d'excès de saturation — cette fois avec l'exposant de forme à caler $X_8$ — calcule la fraction qui dépasse la capacité et est évacuée comme ruissellement de surface $Q_{s0}$.

**Étape 5 : répartition du routage entre réservoirs rapide et lent**.
Le contenu restant de $R$ est vidé à un taux constant par pas $1/X_7$, produisant un flux de recharge $I_R$.
$I_R$ est réparti par le coefficient de répartition $X_1$ : une fraction $X_1$ entre dans le réservoir linéaire rapide $T$ (constante de temps $X_2$ jours), et le reste $(1 - X_1)$ entre dans le réservoir linéaire lent $M$ (constante de temps $X_2 \cdot X_3$ jours).

**Étape 6 : écoulement combiné avant routage**.
Les réservoirs rapide et lent évacuent chacun leur propre débit linéaire $Q_T = T / X_2$ et $Q_M = M / (X_2 X_3)$, qui s'ajoutent au ruissellement de surface direct $Q_{s0}$ calculé à l'Étape 4 pour former le total non routé $Q^\star = Q_{s0} + Q_T + Q_M$.

**Étape 7 : convolution par l'hydrogramme unitaire**.
Enfin, $Q^\star$ passe par un hydrogramme unitaire à deux poids contrôlé par $X_6$ qui concentre tout le poids sur les deux dernières ordonnées.
Cela permet au modèle de représenter des délais fractionnaires autrement impossibles avec un hydrogramme de longueur entière, et le débit $Q$ à ce pas de temps est la première ordonnée (fraîchement libérée).

## Paramètres

Le modèle XINANJIANG possède 8 paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Répartition du routage rapide / lent | [0.01, 0.99] | – | Fraction de la sortie d'eau libre routée par le réservoir rapide; le complément alimente le réservoir lent. |
| $X_2$ | Constante de temps du réservoir rapide | [1, 20] | jours | Constante de vidange du réservoir linéaire rapide $T$; des valeurs plus petites donnent une réponse plus nerveuse. |
| $X_3$ | Multiplicateur du réservoir lent | [1, 50] | – | Rapport entre les constantes de temps lente et rapide; la constante de temps lente effective est $X_2 \cdot X_3$. |
| $X_4$ | Capacité d'eau libre | [1, 500] | mm | Stockage maximal du réservoir d'eau libre (gravitaire) $R$. |
| $X_5$ | Capacité du réservoir de sol | [1, 2000] | mm | Stockage maximal d'humidité du sol $S$; contrôle le déclenchement de la saturation et le régime d'ET. |
| $X_6$ | Délai de l'hydrogramme unitaire | [0.5, 10] | jours | Décalage moyen de l'hydrogramme unitaire à deux poids appliqué au débit sortant. |
| $X_7$ | Constante de vidange de l'eau libre | [1, 50] | jours | Constante de temps du flux de recharge $I_R$ quittant le réservoir d'eau libre. |
| $X_8$ | Exposant de saturation de l'eau libre | [0.01, 5] | – | Forme de la distribution en loi de puissance des capacités d'eau libre; des valeurs plus élevées donnent une réponse d'excès de saturation plus abrupte. |

**Comprendre les paramètres :**

- **$X_5$ est le paramètre de calage dominant** pour le bilan hydrique de long terme.
Les valeurs typiques pour les bassins tempérés humides sont 200–800 mm; des valeurs proches de la borne supérieure indiquent généralement un bassin à sols profonds ou à stockage souterrain important.
- **$X_1$ contrôle la forme de la récession de l'hydrogramme**.
Une valeur proche de 0.5 donne un mélange équilibré de réponses rapide et lente; des valeurs proches de 0.01 coupent essentiellement la voie rapide, et le modèle se réduit à un seul réservoir lent.
- **$X_2$ et $X_3$ définissent ensemble les deux échelles de temps de récession**.
Si les deux se calent au bas de leur plage, le modèle vous dit que le bassin n'a pas de composante lente et qu'une structure plus simple à réservoir unique conviendrait probablement tout aussi bien.
- **$X_4$ et $X_8$ déterminent conjointement la vitesse de saturation du réservoir d'eau libre pendant les tempêtes**.
Un grand $X_4$ combiné à un petit $X_8$ produit un hydrogramme lisse à montée tardive; un petit $X_4$ avec un grand $X_8$ produit une réponse nerveuse à saturation précoce.
- **$X_6$ ne compte que si le bassin a un temps de concentration prononcé**.
Pour les petits bassins de tête, il se cale souvent près de la borne inférieure, ce qui signifie que l'hydrogramme unitaire est effectivement un passage direct en un seul pas.

## Formulation mathématique

### Initialisation

Les états des réservoirs à $t = 0$ sont initialisés à des valeurs de démarrage à chaud prudentes, suivant `ini_HydroMod20` de HOOPLA :

$$
S_0 = X_5, \quad R_0 = 1 \text{ mm}, \quad T_0 = 5 \text{ mm}, \quad M_0 = 400 \text{ mm}
$$

Le réservoir de sol initial est fixé à sa pleine capacité parce que la formulation d'excès de saturation de XINANJIANG est sensible à une sous-initialisation de $S$ et réagit avec grâce à une sur-initialisation.

### Entrées nettes

$$
P_n = \max(P - E, 0), \qquad E_n = \max(E - P, 0)
$$

### Réservoir de sol (pas humide seulement, $P_n > 0$)

Avec l'exposant de forme fixe $B = 0.25$, la formule d'excès de saturation du réservoir de sol est :

$$
\text{base}_S = \max\!\left(1 - \frac{S}{X_5},\ 0\right)
$$

$$
F_S = \left[\max\!\left(\text{base}_S^{\,1/(1+B)} - \frac{P_n}{(1 + B) X_5},\ 0\right)\right]^{1 + B}
$$

$$
P_s = \max\!\bigl(X_5 - S - F_S \cdot X_5,\ 0\bigr), \qquad S \leftarrow \min(S + P_s,\ X_5)
$$

Ici $P_s$ est le flux traversant qui entre dans le réservoir d'eau libre, et la mise à jour d'état $S \leftarrow \min(S + P_s, X_5)$ est la mise à jour de bilan de masse du réservoir de sol.

### ET du réservoir de sol (pas sec seulement, $E_n > 0$)

$$
E_S =
\begin{cases}
\min(S,\, E_n) & \text{if } S/X_5 \ge 0.9 \\[4pt]
\min\!\left(S,\, E_n \cdot \dfrac{S}{0.9\, X_5}\right) & \text{if } 0.09 \le S/X_5 < 0.9 \\[8pt]
\min(S,\, 0.1\, E_n) & \text{if } S/X_5 < 0.09
\end{cases}
$$

$$
S \leftarrow S - E_S
$$

### Réservoir d'eau libre

L'entrée du réservoir d'eau libre est $P_r = P_n - P_s$. Avec l'exposant de forme $X_8$ :

$$
\text{base}_R = \max\!\left(1 - \frac{R}{X_4},\ 0\right)
$$

$$
F_R = \left[\max\!\left(\text{base}_R^{\,1/(1+X_8)} - \frac{P_r}{(1 + X_8) X_4},\ 0\right)\right]^{1 + X_8}
$$

$$
P_r^\prime = \max\!\bigl(X_4 - R - F_R \cdot X_4,\ 0\bigr)
$$

$$
R \leftarrow \min(R + P_r^\prime,\ X_4)
$$

Le ruissellement de surface généré dans cette phase est :

$$
Q_{s0} = \max(P_r - P_r^\prime,\ 0)
$$

### Réservoirs de routage

La recharge quittant le réservoir d'eau libre est :

$$
I_R = \frac{R}{X_7}, \qquad R \leftarrow R - I_R
$$

Elle est répartie entre le réservoir rapide $T$ et le réservoir lent $M$ par $X_1$ :

$$
T \leftarrow T + X_1 \cdot I_R, \qquad Q_T = \frac{T}{X_2}, \qquad T \leftarrow T - Q_T
$$

$$
M \leftarrow M + (1 - X_1) \cdot I_R, \qquad Q_M = \frac{M}{X_2 \cdot X_3}, \qquad M \leftarrow M - Q_M
$$

### Hydrogramme unitaire

L'hydrogramme unitaire à deux poids de longueur $n = \lceil X_6 \rceil + 1$ a pour ordonnées :

$$
d_i =
\begin{cases}
0 & \text{for } 0 \le i < n - 2 \\[4pt]
\dfrac{1}{X_6 - n + 3} & \text{for } i = n - 2 \\[8pt]
1 - d_{n-2} & \text{for } i = n - 1
\end{cases}
$$

La convolution est implémentée comme un décalage-et-addition sur un tampon interne $h$ :

$$
Q^\star = Q_{s0} + Q_T + Q_M
$$

$$
h_i \leftarrow h_{i+1} + d_i \cdot Q^\star \quad \text{for } 0 \le i < n - 1
$$

$$
h_{n-1} \leftarrow d_{n-1} \cdot Q^\star
$$

### Débit total

$$
Q = \max(h_0,\ 0)
$$

Le maximum avec zéro est une garde défensive contre les erreurs d'arrondi en virgule flottante dans le tampon de décalage-et-addition et ne s'active jamais avec des entrées bien conditionnées.

## Références

- Zhao, R. J., Zhuang, Y. L., Fang, L. R., Liu, X. R., & Zhang, Q. S. (1980). The Xinanjiang model. In *Hydrological Forecasting Proceedings Oxford Symposium*, IAHS Publication No. 129 (pp. 351–356).
- Zhao, R. J. (1992). The Xinanjiang model applied in China. *Journal of Hydrology*, 135(1–4), 371–381. [DOI](https://doi.org/10.1016/0022-1694(92)90096-E)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie–débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble.
