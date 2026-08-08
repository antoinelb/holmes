# Modèle bucket

## Aperçu

Le modèle bucket est un modèle pluie-débit conceptuel fondé sur le cadre du réservoir linéaire.
Il représente un bassin versant à l'aide de « seaux » ou réservoirs interconnectés : un réservoir d'humidité du sol qui contrôle l'évaporation, et deux réservoirs de routage qui produisent les composantes lente (débit de base) et rapide (écoulement rapide) du débit.

La structure modulaire du modèle sépare explicitement les différentes voies d'écoulement, ce qui rend facile de comprendre comment chaque composante contribue à l'hydrogramme total.
Avec six paramètres, le modèle bucket offre plus de flexibilité que GR4J pour représenter la répartition des écoulements et le comportement de récession, au prix toutefois d'un risque accru d'équifinalité des paramètres.

Les modèles de type bucket (aussi appelés modèles tank) ont une longue histoire en hydrologie et restent largement utilisés.
La structure explicite en réservoirs linéaires capture souvent bien la dynamique de récession, en particulier dans les bassins versants aux composantes de débit de base et d'écoulement rapide distinctes.

## Concepts clés

- **Réservoir d'humidité du sol** : le réservoir principal, qui reçoit les précipitations et perd de l'eau par évapotranspiration.
Quand il est plein, l'excès d'eau se draine vers les réservoirs de routage.

- **Réservoir linéaire** : un concept fondamental en hydrologie où le débit sortant est proportionnel au stockage.
La constante de proportionnalité est le coefficient de récession $K$, qui représente le temps nécessaire pour que le stockage diminue à $1/e$ (environ 37 %) de sa valeur initiale.

- **Débit de base (écoulement lent)** : l'écoulement soutenu qui persiste longtemps après la fin de la pluie, alimenté par le drainage graduel du sol et de l'eau souterraine.
Caractérisé par une longue constante de temps de récession.

- **Écoulement rapide** : la réponse rapide à la pluie qui produit les pointes de crue.
Représente le ruissellement de surface et les voies d'écoulement hypodermique rapides.

- **Délai de routage** : le temps nécessaire pour que l'eau voyage du bassin versant à l'exutoire, implémenté comme une simple translation de l'hydrogramme.

## Fonctionnement

Le modèle bucket traite les précipitations et l'évapotranspiration selon les étapes suivantes :

**Étape 1 : répartition des précipitations**. Les précipitations entrantes se divisent entre l'eau qui entre dans le réservoir de sol et l'eau qui le contourne entièrement (ruissellement direct).
Le paramètre $X_5$ contrôle cette répartition.

**Étape 2 : suivi de l'humidité du sol**. L'eau entrant dans le réservoir de sol est soumise à l'évapotranspiration.
En période humide (les précipitations dépassent l'ETP), le réservoir se remplit.
Quand le réservoir dépasse sa capacité $X_1$, l'excès devient de l'infiltration.
En période sèche (l'ETP dépasse les précipitations), le réservoir se vide exponentiellement.

**Étape 3 : répartition de l'infiltration**. L'eau qui s'infiltre sous le réservoir de sol se divise entre le réservoir lent (devenant le débit de base) et le réservoir rapide (devenant l'écoulement rapide).
Le paramètre $X_2$ contrôle cette répartition.

**Étape 4 : débit sortant des réservoirs linéaires**. Chaque réservoir de routage libère l'eau à un taux proportionnel à son contenu.
Le réservoir lent utilise la constante de temps $X_3$, tandis que le réservoir rapide utilise $X_6$.

**Étape 5 : délai de routage**. Le débit sortant combiné est retardé de $X_4$ jours pour tenir compte du routage en chenal, par interpolation linéaire entre pas de temps adjacents.

## Paramètres

Le modèle bucket possède six paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Capacité d'humidité du sol | 10–1000 | mm | Stockage maximal d'eau dans le sol. Des valeurs élevées permettent une plus grande rétention d'eau avant l'apparition du ruissellement. |
| $X_2$ | Ratio de répartition de l'infiltration | 0–1 | - | Fraction de l'infiltration dirigée vers le réservoir lent. Des valeurs élevées produisent des hydrogrammes davantage dominés par le débit de base. |
| $X_3$ | Constante de récession lente | 1–200 | jours | Échelle de temps de la vidange du débit de base. Des valeurs élevées produisent un débit de base plus lent et plus soutenu. |
| $X_4$ | Délai de routage | 2–10 | jours | Temps de translation de l'écoulement jusqu'à l'exutoire. Reflète la longueur et la vitesse du chenal. |
| $X_5$ | Fraction de ruissellement direct | 0–1 | - | Fraction des précipitations contournant le réservoir de sol. Des valeurs élevées produisent une réponse plus vive. |
| $X_6$ | Constante de récession rapide | 1–400 | jours | Échelle de temps de la vidange de l'écoulement rapide. Généralement bien plus petite que $X_3$. |

**Comprendre les paramètres :**

- **$X_1$** agit comme la profondeur du sol multipliée par la porosité — combien d'eau le sol peut-il retenir avant de déborder?
- **$X_2$ et $X_5$** contrôlent ensemble la forme de l'hydrogramme.
Un $X_5$ élevé et un $X_2$ faible produisent des réponses vives et pointues; un $X_5$ faible et un $X_2$ élevé produisent des réponses amorties, dominées par le débit de base.
- **$X_3$ et $X_6$** contrôlent la vitesse à laquelle le bassin versant « oublie » la pluie passée.
Un cours d'eau avec $X_3 = 100$ jours aura un débit de base qui dure des mois après la fin de la pluie.
- **$X_4$** est avant tout un paramètre de synchronisation — il décale l'hydrogramme entier sans changer sa forme.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs :

$$S_0 = 0.5 \cdot X_1, \quad R_0 = 10, \quad T_0 = 5$$

où $S$ est l'humidité du sol, $R$ le réservoir de routage lent et $T$ le réservoir de routage rapide.

### Répartition des précipitations

Les précipitations $P$ se divisent entre l'entrée du sol et l'écoulement rapide direct :

$$P_s = (1 - X_5) \cdot P$$

$$P_r = X_5 \cdot P$$

où $P_s$ entre dans le réservoir de sol et $P_r$ va directement au réservoir de routage rapide.

### Dynamique de l'humidité du sol

**Conditions humides ($P_s \geq E$) :**

Quand l'apport de précipitations dépasse la demande d'évapotranspiration :

$$S \leftarrow S + P_s - E$$

Tout excès au-dessus de la capacité devient de l'infiltration :

$$I_s = \max(S - X_1, 0)$$

$$S \leftarrow S - I_s$$

**Conditions sèches ($P_s < E$) :**

Quand la demande d'évapotranspiration dépasse l'apport de précipitations, le réservoir se vide exponentiellement :

$$S \leftarrow S \cdot \exp\left(\frac{P_s - E}{X_1}\right)$$

Cette formulation garantit que l'évaporation diminue à mesure que le sol s'assèche (évaporation limitée par l'eau disponible).

### Répartition de l'infiltration

L'infiltration issue du réservoir de sol se divise entre les réservoirs de routage :

$$I_{slow} = (1 - X_2) \cdot I_s$$

$$I_{fast} = X_2 \cdot I_s$$

### Réservoirs de routage

Les deux réservoirs de routage suivent une dynamique de réservoir linéaire.

**Réservoir lent (débit de base) :**

$$R \leftarrow R + I_{slow}$$

$$Q_r = \frac{R}{X_3}$$

$$R \leftarrow R - Q_r$$

**Réservoir rapide (écoulement rapide) :**

$$T \leftarrow T + P_r + I_{fast}$$

$$Q_t = \frac{T}{X_6}$$

$$T \leftarrow T - Q_t$$

### Débit total du système

$$Q_{sys} = Q_r + Q_t$$

### Délai de routage

Le délai de routage est implémenté par interpolation linéaire.
Pour un délai de $X_4$ jours, le modèle maintient un tableau de délai et décale les écoulements vers l'avant :

$$Q(t) = \text{delayed}(Q_{sys}, X_4)$$

Le délai utilise l'interpolation linéaire quand $X_4$ n'est pas entier, répartissant l'eau entre pas de temps adjacents.

## Références

Thornthwaite, C. W., & Mather, J. R. (1955). *The water balance*. Publications in Climatology, 8(1). Drexel Institute of Technology, Laboratory of Climatology.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*  PhD Thesis, INPG Grenoble, Appendix 1, pp. 313-316. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
