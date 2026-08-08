# Modèle SIMHYD

## Aperçu

SIMHYD (SIMple HYDrological model) est un modèle pluie-débit conceptuel à huit paramètres développé en Australie par Chiew, Peel et Western (2002).
Il appartient à la famille des modèles à seuils où la capacité d'infiltration décroît exponentiellement avec la saturation du sol, une simplification courante dans la pratique australienne de gestion des ressources en eau.

L'implémentation de HOLMES suit la version modifiée de la boîte à outils HOOPLA (Thiboult et al., 2020, HM15), qui ajoute à la formulation originale deux réservoirs de routage et un paramètre de délai fractionnaire.
Le modèle représente un bassin versant par un réservoir d'interception, un réservoir d'humidité du sol et deux réservoirs de routage linéaires (souterrain et principal) reliés par un registre de délai.

SIMHYD est un bon choix lorsqu'on souhaite un modèle simple avec des voies explicites pour l'écoulement hypodermique et la recharge de la nappe.
Ses huit paramètres sont faciles à interpréter physiquement, ce qui le rend bien adapté à l'enseignement et à la comparaison avec des modèles plus complexes.

## Concepts clés

- **Réservoir d'interception** : un réservoir conceptuel de capacité $X_1$ qui capte les précipitations avant qu'elles n'atteignent le sol, limité à la fois par la pluie et par l'ETP disponible.
- **Réservoir d'humidité du sol** : un réservoir de capacité $X_2$ qui reçoit l'eau infiltrée et perd de l'eau par évapotranspiration, écoulement hypodermique, recharge de la nappe et débordement.
- **Infiltration exponentielle** : le taux d'infiltration maximal décroît selon $X_8 \cdot e^{-2\,S/X_2}$ — un sol saturé n'admet que très peu d'eau supplémentaire.
- **Écoulement hypodermique** : écoulement latéral de subsurface proportionnel à la saturation du sol et inversement proportionnel à $X_6$.
- **Recharge de la nappe** : percolation profonde proportionnelle à la saturation du sol et inversement proportionnelle à $X_7$.
- **Réservoir souterrain** : un réservoir linéaire lent (constante de vidange $X_3 \cdot X_5$) qui reçoit l'excès du sol et la recharge.
- **Réservoir de routage** : un réservoir linéaire rapide (constante de vidange $X_5$) qui recueille toutes les composantes de l'écoulement avant le routage par délai.
- **Délai fractionnaire** : un hydrogramme unitaire à deux poids de base $X_4$ jours qui décale l'écoulement routé dans le temps.

## Fonctionnement

**Étape 1 : interception.**
Les précipitations entrantes $P$ sont d'abord interceptées jusqu'à une limite fixée à la fois par la capacité d'interception $X_1$ et par l'ETP disponible $E$.
La quantité interceptée est $\text{CAP} = \min(P,\, X_1,\, E)$.
Si les précipitations dépassent cette quantité, l'excès $\text{EXC} = P - \text{CAP}$ passe à l'infiltration; sinon toutes les précipitations sont interceptées et il ne reste aucun excès.

**Étape 2 : infiltration.**
La pluie en excès est répartie entre ruissellement de surface et infiltration selon la capacité du sol à absorber l'eau.
La capacité d'infiltration est $\text{RINF} = X_8 \cdot e^{-2\,S/X_2}$, qui décroît exponentiellement à mesure que le sol se sature.
Si l'excès dépasse cette capacité, le surplus devient le ruissellement de surface $Q_\text{srun}$ et seul $\text{RINF}$ s'infiltre.

**Étape 3 : écoulement hypodermique et recharge de la nappe.**
Dans l'eau infiltrée, une fraction proportionnelle à la saturation du sol $S/X_2$ est détournée en écoulement hypodermique ($\text{SINT}$, gouverné par $X_6$) et en recharge de la nappe ($\text{REC}$, gouvernée par $X_7$).
Ces deux quantités augmentent à mesure que le sol approche de la saturation, traduisant l'idée qu'un sol plus humide perd de l'eau plus vite par les voies latérales et verticales.

**Étape 4 : suivi de l'humidité du sol.**
Le réservoir de sol $S$ reçoit l'eau infiltrée moins ce qui a été perdu en écoulement hypodermique et en recharge.
Si $S$ dépasse la capacité $X_2$, l'excès $\text{EX}_2$ déborde vers le réservoir souterrain.
L'ETP restante (après interception) alimente l'évapotranspiration réelle depuis le sol, limitée à $10 \cdot S / X_2$ mm, et le niveau du sol est borné à zéro.

**Étape 5 : routage.**
L'excès du sol et la recharge alimentent le **réservoir souterrain** $R$ (voie lente, se vidant au taux $1/(X_3 \cdot X_5)$).
Le ruissellement de surface, l'écoulement hypodermique et le débit sortant du réservoir souterrain alimentent le **réservoir de routage** $T$ (voie rapide, se vidant au taux $1/X_5$).
Cet agencement à deux réservoirs permet au modèle de séparer la réponse rapide du débit de base lent.

**Étape 6 : délai et débit.**
La sortie du réservoir de routage $Q_t$ est convoluée avec une fonction de délai fractionnaire à deux poids de base $X_4$ jours, produisant le débit simulé final $Q$.
Le délai décale le pic de l'hydrogramme dans le temps sans en changer le volume, représentant le temps de parcours dans le réseau de chenaux.

## Paramètres

Le modèle SIMHYD possède 8 paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Capacité du réservoir d'interception | 0.5 – 10.0 | mm | Pluie maximale pouvant être retenue par la canopée avant d'atteindre le sol |
| $X_2$ | Capacité du réservoir d'humidité du sol | 1.0 – 500.0 | mm | Quantité totale d'eau que le sol peut retenir avant de déborder |
| $X_3$ | Constante de vidange du réservoir souterrain | 1.0 – 1000.0 | - | Multiplicateur qui ralentit le réservoir souterrain par rapport au réservoir de routage |
| $X_4$ | Délai | 0.5 – 5.0 | j | Décalage temporel fractionnaire appliqué au débit routé |
| $X_5$ | Constante de vidange du réservoir de routage | 1.0 – 500.0 | j | Contrôle la vitesse de vidange du réservoir de routage principal |
| $X_6$ | Constante d'écoulement hypodermique | 1.0 – 1000.0 | - | Des valeurs élevées réduisent l'écoulement hypodermique; inversement proportionnelle au paramètre SUB du SIMHYD standard |
| $X_7$ | Constante de recharge de la nappe | 1.0 – 1000.0 | - | Des valeurs élevées réduisent la percolation profonde; inversement proportionnelle au paramètre CRAK du SIMHYD standard |
| $X_8$ | Capacité d'infiltration maximale | 1.0 – 500.0 | mm | Taux d'infiltration quand le sol est complètement sec; décroît exponentiellement avec la saturation |

**Comprendre les paramètres :**

- $X_1$ est petit (typiquement 1–5 mm) parce que l'interception par la canopée est une composante mineure du bilan hydrique.
Il affecte surtout le moment des pics et la répartition de l'ET.
- $X_2$ contrôle l'humidité globale du bassin versant — des valeurs plus élevées signifient plus de tamponnage avant que l'excès du sol ne déclenche un débordement vers le réservoir souterrain.
- $X_3$ et $X_5$ contrôlent ensemble la séparation entre écoulement lent et rapide : le réservoir de routage se vide au taux $1/X_5$ tandis que le réservoir souterrain se vide au taux $1/(X_3 \cdot X_5)$.
Augmenter $X_3$ rend le débit de base plus persistant.
- $X_6$ et $X_7$ se disputent l'eau infiltrée — quand les deux sont petits, le sol perd rapidement de l'eau par les voies latérales et verticales; quand les deux sont grands, l'eau reste plus longtemps dans le sol et finit par être perdue en ET ou en débordement.
- $X_8$ fixe le plafond d'infiltration.
Sur un sol sec, la totalité des $X_8$ mm est disponible, mais quand $S \to X_2$ l'infiltration effective chute à environ $14\%$ de $X_8$ (parce que $e^{-2} \approx 0.135$).

## Formulation mathématique

### Initialisation

$$S_0 = \frac{X_2}{2}, \quad R_0 = 80, \quad T_0 = 1$$

### Interception

$$\text{CAP} = \min(P,\, X_1,\, E)$$

$$\text{EXC} = \max(0,\; P - \text{CAP}), \quad E_1 = \begin{cases} \text{CAP} & \text{if } P > \text{CAP} \\ P & \text{otherwise} \end{cases}$$

### Infiltration

$$\text{RINF} = X_8 \cdot \exp\!\left(-2\,\frac{S}{X_2}\right)$$

$$Q_\text{srun} = \max(0,\; \text{EXC} - \text{RINF}), \quad \text{FILT} = \min(\text{EXC},\; \text{RINF})$$

### Écoulement hypodermique et recharge de la nappe

$$\text{SINT} = \frac{S}{X_2} \cdot \frac{\text{FILT}}{X_6}$$

$$\text{REC} = \max\!\left(0,\; \frac{S}{X_2} \cdot \frac{\text{FILT} - \text{SINT}}{X_7}\right)$$

### Suivi de l'humidité du sol

$$S \leftarrow S + \text{FILT} - \text{SINT} - \text{REC}$$

$$\text{EX}_2 = \max(0,\; S - X_2), \quad S \leftarrow \min(S,\; X_2)$$

$$\text{ET} = \min\!\left(E - E_1,\; 10 \cdot \frac{S}{X_2}\right), \quad S \leftarrow \max(0,\; S - \text{ET})$$

### Réservoir souterrain (lent)

$$R \leftarrow R + \text{EX}_2 + \text{REC}$$

$$Q_r = \frac{R}{X_3 \cdot X_5}, \quad R \leftarrow R - Q_r$$

### Réservoir de routage (rapide)

$$T \leftarrow T + \text{SINT} + Q_\text{srun} + Q_r$$

$$Q_t = \frac{T}{X_5}, \quad T \leftarrow T - Q_t$$

### Débit total

$$Q = \text{delay}(Q_t,\; X_4)$$

où $\text{delay}(\cdot, X_4)$ est une convolution de délai fractionnaire à deux poids de base $\lceil X_4 \rceil + 1$ pas de temps.

## Références

- Chiew, F.H.S., Peel, M.C., & Western, A.W. (2002). Application and testing of the simple rainfall-runoff model SIMHYD. In V.P. Singh, D.K. Frevert (Eds.), *Mathematical Models of Small Watershed Hydrology and Applications* (pp. 335–367). Water Resources Publications.
- Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020). The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory. *Hydrology and Earth System Sciences Discussions*.
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble.
