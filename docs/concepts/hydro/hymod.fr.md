# Modèle HYMOD

## Aperçu

HYMOD est un modèle pluie-débit global journalier à six paramètres introduit par Boyle (2000) et popularisé pour les études de calage multicritère par Wagener et al. (2001).
Il appartient à la même classe de parcimonie que GR4J et le modèle bucket, mais se distingue par un schéma de suivi de l'humidité du sol spatialement distribué emprunté à Moore (1985).

La caractéristique déterminante de HYMOD est son **réservoir d'humidité du sol à distribution de Pareto**.
Au lieu de traiter le bassin versant comme un unique seau uniforme qui déborde ou non, HYMOD suppose que différentes parties du bassin versant ont différentes capacités de stockage tirées d'une distribution de Pareto.
Cela signifie qu'à mesure que le bassin versant s'humidifie, de plus en plus de cellules saturent progressivement, générant du ruissellement par le mécanisme des zones contributives variables observé dans les bassins réels — un concept que partagent les modèles Xinanjiang et VIC.

Le ruissellement issu du réservoir de sol est ensuite réparti entre une voie d'**écoulement rapide** (trois réservoirs linéaires en cascade, approximant une réponse hypodermique rapide) et une voie d'**écoulement lent** (un unique réservoir souterrain linéaire).
Un court délai de type hydrogramme unitaire tient compte du temps de parcours en chenal.
Bien qu'il n'utilise que six paramètres, HYMOD performe typiquement aussi bien ou mieux que les autres modèles conceptuels globaux dans les études comparatives, ce qui explique pourquoi il demeure un incontournable de la recherche en analyse de sensibilité et en estimation de paramètres.

## Concepts clés

- **Réservoir de sol à distribution de Pareto** : un suivi de l'humidité du sol par zones contributives variables où la capacité de stockage du bassin versant suit une distribution de Pareto.
Le paramètre $C_{\max}$ ($X_1$) fixe la capacité locale maximale, et le paramètre $B_{\exp}$ ($X_2$) contrôle la variabilité spatiale : $B_{\exp} = 0$ donne un seau uniforme, tandis que de plus grandes valeurs produisent des distributions fortement asymétriques où une petite fraction du bassin versant sature rapidement.

- **Ruissellement par excès de saturation** : quand la pluie entrante ferait déborder la fraction déjà saturée du bassin versant, l'excès devient du ruissellement direct.
Ce mécanisme produit une réponse pluie-débit non linéaire même en conditions sèches, parce que la zone saturée croît à mesure que le bassin versant s'humidifie.

- **Répartition rapide/lent** : l'eau en excès hors saturation est répartie entre une voie rapide et une voie lente par le paramètre $\alpha$ ($X_3$).
La fraction $\alpha$ entre dans la voie rapide; la fraction $(1 - \alpha)$ alimente le réservoir souterrain lent.

- **Trois réservoirs linéaires en cascade** : la voie rapide route l'eau à travers trois réservoirs linéaires en série, chacun avec un temps de résidence $R_q$ ($X_6$).
La cascade de trois réservoirs linéaires approxime un temps de parcours distribué selon une loi gamma et produit des pointes de crue plus lisses et plus amorties qu'un seul réservoir linéaire.

- **Réservoir souterrain linéaire** : l'écoulement lent passe par un unique réservoir linéaire de temps de résidence effectif $R_s \cdot R_q$, produisant un débit de base soutenu.

- **Délai de routage** : le débit sortant combiné rapide plus lent est retardé de $X_4$ jours par interpolation linéaire entre pas de temps adjacents, représentant le temps de parcours en chenal jusqu'à l'exutoire du bassin versant.

## Fonctionnement

Le modèle HYMOD traite les précipitations et l'évapotranspiration selon les étapes suivantes :

**Étape 1 : calcul de la capacité saturée courante**.
Étant donné l'eau du sol courante $S$, le modèle calcule l'inverse de la fonction de distribution de Pareto pour déterminer la capacité du bassin versant $C_{\text{prev}}$ actuellement remplie.
Cela représente la fraction du bassin versant dont le stockage est déjà saturé.

**Étape 2 : ruissellement par excès de saturation**.
Si la pluie entrante $P$ plus $C_{\text{prev}}$ dépasse $C_{\max}$, la fraction du bassin versant déjà saturée ne peut pas retenir la pluie et l'excès $U_{t1}$ devient du ruissellement direct immédiat.
C'est le mécanisme classique des zones contributives variables : un petit bassin versant humide produit peu d'excès de saturation, un bassin versant presque saturé en produit beaucoup.

**Étape 3 : mise à jour de l'humidité du sol**.
La pluie nette $P_n = P - U_{t1}$ est distribuée sur le réservoir de Pareto, donnant un nouveau niveau d'eau du sol via l'intégrale inverse de Pareto.
L'augmentation de $S$ représente l'eau retenue dans le sol; tout reste $U_{t2}$ est un excès hors saturation qui quitte aussi le sol comme ruissellement.

**Étape 4 : évapotranspiration**.
L'évapotranspiration potentielle $E$ est retirée du réservoir de sol au plein taux de la demande, bornée pour garder $S$ non négatif.
HYMOD ne met pas l'ET à l'échelle selon le contenu en eau du sol, donc les périodes sèches épuisent directement $S$.

**Étape 5 : répartition des écoulements**.
L'excès hors saturation $U_{t2}$ est réparti entre les voies rapide et lente à l'aide du paramètre $\alpha$.
L'écoulement rapide $U_q = \alpha \cdot U_{t2} + U_{t1}$ recueille tout l'excès de saturation plus une fraction de l'excès normal; l'écoulement lent $U_s = (1 - \alpha) \cdot U_{t2}$ entre dans le réservoir d'eau souterraine.

**Étape 6 : routage lent**.
Le réservoir d'eau souterraine $T$ reçoit $U_s$ et se draine linéairement au taux $T / (R_s \cdot R_q)$, produisant une composante lente de débit de base $Q_t$.

**Étape 7 : routage rapide**.
L'écoulement rapide $U_q$ entre dans le premier réservoir linéaire $R_1$ d'une cascade de trois réservoirs.
Chaque réservoir se draine au taux $R_i / R_q$, alimentant le suivant en séquence.
La sortie du troisième réservoir est la composante de débit à réponse rapide $Q_3$.

**Étape 8 : routage du délai**.
La somme des composantes rapide et lente $(Q_t + Q_3)$ est retardée de $X_4$ jours par interpolation linéaire, produisant le débit simulé final $Q_{\text{sim}}$.

## Paramètres

Le modèle HYMOD possède six paramètres à caler.
Notez que cette implémentation suit la paramétrisation de HOOPLA, où les paramètres de réservoir $R_s$ et $R_q$ sont des **temps de résidence** ($Q = R / R_q$), et non les taux de vidange du HYMOD classique ($Q = R \cdot K_q$) trouvés dans Vrugt et al. (2003) et la littérature connexe.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ ($C_{\max}$) | Capacité maximale d'humidité du sol | 1–1500 | mm | Borne supérieure de la distribution de Pareto des capacités de stockage locales. Des valeurs élevées augmentent la rétention d'eau totale du bassin versant et réduisent la vivacité de la réponse. |
| $X_2$ ($B_{\exp}$) | Variabilité spatiale de la capacité d'humidité du sol | 0.1–2.0 | - | Paramètre de forme de la distribution de Pareto. De petites valeurs donnent un réservoir de sol quasi uniforme; de grandes valeurs concentrent la majeure partie de la capacité dans une petite fraction du bassin versant. |
| $X_3$ ($\alpha$) | Facteur de distribution des écoulements rapide/lent | 0.01–0.99 | - | Fraction de l'excès hors saturation routée vers la cascade rapide. Des valeurs élevées produisent des hydrogrammes plus vifs; des valeurs faibles accentuent le débit de base. |
| $X_4$ (délai) | Longueur du délai de l'hydrogramme unitaire | 0.1–5.0 | jours | Temps de parcours en chenal du bassin versant à l'exutoire. Des valeurs élevées décalent l'hydrogramme entier plus tard. |
| $X_5$ ($R_s$) | Facteur de résidence du routage lent | 1–1000 | - | Multiplicateur combiné avec $R_q$ pour donner le temps de résidence effectif du réservoir d'eau souterraine. Le temps de résidence lent effectif est $R_s \cdot R_q$ jours. |
| $X_6$ ($R_q$) | Temps de résidence du routage rapide | 1–10 | jours | Temps de résidence de chacun des trois réservoirs linéaires de la cascade rapide. Des valeurs élevées amortissent les pointes de crue; des valeurs faibles produisent des pointes plus nettes. |

**Comprendre les paramètres :**

- **$X_1$ et $X_2$ ensemble** définissent le réservoir de sol.
$X_1$ est le plafond absolu du stockage local; $X_2$ contrôle la répartition spatiale du stockage.
À $X_2 = 0.1$, le réservoir de sol se comporte presque comme un seau uniforme de profondeur $X_1 / 1.1$; à $X_2 = 2$, la majeure partie du bassin versant a une faible capacité et sature facilement, mais une petite fraction en retient beaucoup plus.
- **$X_3$** est un simple bouton de répartition des écoulements.
Comme HYMOD n'a pas de base physique pour choisir $\alpha$, ce paramètre est généralement ajusté empiriquement pendant le calage pour reproduire la forme de la récession.
- **$X_4$** est un paramètre purement temporel : il décale l'hydrogramme sans changer son amplitude ni sa forme.
- **$X_5$ et $X_6$ ensemble** contrôlent la composante lente.
Le temps de résidence lent effectif est $X_5 \cdot X_6$ jours, donc un grand $X_5$ donne de longues récessions de débit de base (des semaines à des années).
- **$X_6$ seul** contrôle la cascade rapide.
Avec trois réservoirs en série, le pic de la réponse rapide est retardé et lissé — une seule impulsion d'entrée produit une sortie en forme de loi gamma avec un délai moyen de $3 \cdot X_6$ jours.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs :

$$S_0 = \min\left(0.2 \cdot X_1, \frac{X_1}{X_2 + 1}\right), \quad R_1^{(0)} = R_2^{(0)} = R_3^{(0)} = 1, \quad T_0 = 300$$

où $S$ est le contenu en eau du sol, $R_1, R_2, R_3$ les trois réservoirs rapides et $T$ le réservoir d'eau souterraine.
L'initialisation du sol est bornée à $X_1 / (X_2 + 1)$ pour préserver l'invariant de Pareto $S \leq X_1 / (X_2 + 1)$, requis pour que la formule inverse de Pareto reste à valeurs réelles.

### Réservoir d'humidité du sol de Pareto

La distribution de Pareto des capacités de stockage locales est caractérisée par la fraction cumulée du bassin versant dont la capacité est inférieure à $c$ :

$$F(c) = 1 - \left(1 - \frac{c}{X_1}\right)^{X_2}$$

À tout moment, l'eau du sol $S$ correspond à une « capacité courante » $C_{\text{prev}}$ donnée par l'inverse de la distribution :

$$C_{\text{prev}} = X_1 \cdot \left(1 - \left(1 - \frac{(X_2 + 1) \cdot S}{X_1}\right)^{1 / (X_2 + 1)}\right)$$

La pluie entrante $P$ produit d'abord un excès de saturation depuis la fraction déjà saturée :

$$U_{t1} = \max(P - X_1 + C_{\text{prev}}, 0)$$

$$P_n = P - U_{t1}$$

La nouvelle eau du sol après absorption de $P_n$ est obtenue en intégrant la densité de Pareto :

$$\text{Dum} = \min\left(1, \frac{C_{\text{prev}} + P_n}{X_1}\right)$$

$$S \leftarrow \frac{X_1}{X_2 + 1} \cdot \left(1 - (1 - \text{Dum})^{X_2 + 1}\right)$$

L'excès restant (pluie nette moins l'augmentation du stockage) est la composante de ruissellement hors saturation :

$$U_{t2} = \max(P_n - (S - S_{\text{prev}}), 0)$$

### Évapotranspiration

L'évapotranspiration potentielle est extraite au plein taux de la demande atmosphérique :

$$S \leftarrow \max(S - E, 0)$$

### Répartition des écoulements

L'excès hors saturation $U_{t2}$ est distribué entre les voies d'écoulement rapide et lente à l'aide de la fraction $X_3 = \alpha$ :

$$U_q = \alpha \cdot U_{t2} + U_{t1}$$

$$U_s = (1 - \alpha) \cdot U_{t2}$$

L'écoulement rapide $U_q$ recueille tout l'excès de saturation $U_{t1}$ (qui doit se drainer rapidement) plus une fraction de l'excès normal.

### Réservoir souterrain lent

Le réservoir d'eau souterraine reçoit $U_s$ et se draine linéairement avec un temps de résidence effectif $X_5 \cdot X_6$ :

$$T \leftarrow T + U_s$$

$$Q_t = \frac{T}{X_5 \cdot X_6}$$

$$T \leftarrow T - Q_t$$

### Cascade de réservoirs rapides

La voie rapide route l'eau à travers trois réservoirs linéaires en série, chacun avec un temps de résidence $X_6$ :

$$R_1 \leftarrow R_1 + U_q, \quad Q_1 = \frac{R_1}{X_6}, \quad R_1 \leftarrow R_1 - Q_1$$

$$R_2 \leftarrow R_2 + Q_1, \quad Q_2 = \frac{R_2}{X_6}, \quad R_2 \leftarrow R_2 - Q_2$$

$$R_3 \leftarrow R_3 + Q_2, \quad Q_3 = \frac{R_3}{X_6}, \quad R_3 \leftarrow R_3 - Q_3$$

La convolution de trois réservoirs linéaires identiques approxime une distribution gamma, produisant une réponse unitaire en forme de S avec un délai de pic d'environ $2 \cdot X_6$ jours et une mémoire totale d'environ $5 \cdot X_6$ jours.

### Routage du délai

La somme des composantes rapide et lente $(Q_t + Q_3)$ est retardée de $X_4$ jours par interpolation linéaire.
Le modèle maintient un tableau de délai de taille $\lceil X_4 \rceil + 1$ avec les poids :

$$d_{\lceil X_4 \rceil - 1} = \frac{1}{X_4 - \lceil X_4 \rceil + 3}, \quad d_{\lceil X_4 \rceil} = 1 - d_{\lceil X_4 \rceil - 1}$$

Le débit simulé est obtenu en convoluant la sortie du système avec ce tableau de délai :

$$Q_{\text{sim}}(t) = \text{delayed}(Q_t + Q_3, X_4)$$

## Références

Boyle, D. P. (2000).
*Multicriteria Calibration of Hydrological Models*.
PhD dissertation, Department of Hydrology and Water Resources, University of Arizona, Tucson, USA.

Moore, R. J. (1985).
The probability-distributed principle and runoff production at point and basin scales.
*Hydrological Sciences Journal*, 30(2), 273–297.

Wagener, T., Boyle, D. P., Lees, M. J., Wheater, H. S., Gupta, H. V., & Sorooshian, S. (2001).
A framework for development and application of hydrological models.
*Hydrology and Earth System Sciences*, 5(1), 13–26.

Vrugt, J. A., Gupta, H. V., Bouten, W., & Sorooshian, S. (2003).
A Shuffled Complex Evolution Metropolis algorithm for optimization and uncertainty assessment of hydrologic model parameters.
*Water Resources Research*, 39(8), 1201.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
