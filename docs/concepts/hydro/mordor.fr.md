# Modèle MORDOR

## Aperçu

MORDOR (Modèle à Réservoirs de Drainage Ordinaire) est un modèle pluie-débit conceptuel développé à Électricité de France (EDF) par Garçon (1999) pour la prévision opérationnelle des apports aux réservoirs hydroélectriques.
La version implémentée dans HOLMES suit la variante globale à six paramètres cataloguée comme HM11 dans le cadre HOOPLA.

Le modèle représente un bassin versant par quatre réservoirs en cascade — surface (U), intermédiaire (L), sol profond (Z) et eau souterraine (N) — qui filtrent progressivement la pluie en composantes d'écoulement plus lentes et plus profondes.
Les trois sorties d'écoulement (ruissellement de surface, écoulement souterrain rapide, vidange lente de l'eau souterraine) sont routées à travers le même hydrogramme unitaire à deux versants UH2, produisant un hydrogramme composite lisse.

MORDOR occupe un juste milieu en complexité : six paramètres suffisent à capturer les processus dominants du bilan hydrique tout en restant faciles à caler manuellement.
Sa structure en cascade à quatre réservoirs en fait un bon contrepoint pédagogique aux modèles à deux réservoirs plus simples comme GR4J, et sa séparation explicite du stockage du sol profond et de l'eau souterraine le rend bien adapté aux bassins versants à contributions de débit de base importantes.

## Concepts clés

- **Réservoir de surface (U)** : le réservoir le plus haut, recevant la pluie corrigée.
Il se remplit de la pluie qui n'est pas immédiatement évacuée en ruissellement proportionnel, et perd de l'eau par évapotranspiration et débordement.
Sa capacité est fixée par $X_5$.

- **Réservoir intermédiaire (L)** : reçoit l'eau infiltrée provenant du débordement de U.
Il se vide linéairement à un taux contrôlé par la constante de vidange $X_2$, distribuant sa sortie vers le bas à Z et N et latéralement en ruissellement souterrain rapide.

- **Réservoir de sol profond (Z)** : un réservoir à capacité fixe (90 mm) représentant l'humidité du sol profond non saturé.
Il reçoit la percolation issue de la vidange de L, perd de l'eau par évapotranspiration, et agit comme tampon de répartition : plus Z est plein, plus l'eau est dirigée vers l'écoulement souterrain rapide et la recharge de la nappe plutôt que vers la percolation profonde.

- **Réservoir d'eau souterraine (N)** : le réservoir le plus profond, produisant un débit de base lent selon une loi de vidange non linéaire (cubique) contrôlée par $X_3$.

- **Coefficient de correction de la pluie ($X_1$)** : un facteur multiplicatif appliqué aux précipitations brutes pour corriger la sous-captation du pluviomètre ou la représentativité spatiale.

- **Répartition proportionnelle de la pluie** : la pluie corrigée entrante est partagée entre ruissellement direct et infiltration dans U en proportion du taux de remplissage courant $U/X_5$ — plus le réservoir de surface est humide, plus la pluie devient du ruissellement.

- **Hydrogramme unitaire UH2** : un hydrogramme unitaire à deux versants (queue symétrique) d'exposant 2.5 et de temps de base $2 X_4$.
Les trois composantes d'écoulement sont convoluées indépendamment à travers des instances UH2 identiques avant d'être sommées.

## Fonctionnement

**Étape 1 : correction de la pluie**.
Les précipitations brutes $P$ sont multipliées par le coefficient de correction $X_1$ pour obtenir la précipitation efficace $P_L = P \cdot X_1$.
Cela tient compte de la sous-captation systématique du pluviomètre ou de la non-représentativité spatiale des mesures ponctuelles.

**Étape 2 : répartition de la pluie et mise à jour du réservoir de surface**.
La précipitation corrigée est partagée proportionnellement au taux de remplissage courant de U : une fraction $U/X_5$ devient du ruissellement direct, et le reste entre dans le réservoir de surface.
Si le réservoir déborde (dépasse $X_5$), l'excès est ajouté au ruissellement de surface.
La composante totale d'écoulement de surface $V_S$ (ruissellement direct + débordement) sera routée plus tard.

**Étape 3 : évapotranspiration depuis U**.
Le réservoir de surface perd de l'eau par évapotranspiration réelle, limitée à la fois par l'eau disponible et par la demande d'ETP pondérée par le taux de remplissage.
Toute demande d'ETP non satisfaite est transmise au réservoir de sol profond Z à l'étape 5.

**Étape 4 : infiltration du ruissellement de surface vers L**.
Une portion du ruissellement de surface $V_S$ s'infiltre dans le réservoir intermédiaire L.
Le taux d'infiltration dépend de la capacité restante dans L : $A_L = \max(0,\, X_6 - L) \cdot \max(0,\, 1 - L/X_6)$.

**Étape 5 : vidange intermédiaire et dynamique du réservoir profond**.
L se vide linéairement au taux $V_L = L/X_2$.
Cette vidange est répartie selon le taux de remplissage de Z, $Z/Z_{max}$ : une fraction va en percolation profonde dans Z, 20 % du reliquat proportionnel à Z va en ruissellement souterrain rapide, et les 80 % restants rechargent la nappe (N).
Le réservoir profond Z est ensuite mis à jour : il reçoit la percolation, perd l'évapotranspiration résiduelle (issue de toute ETP de surface non satisfaite), et est plafonné à 90 mm.

**Étape 6 : vidange de l'eau souterraine**.
Le réservoir d'eau souterraine N se vide selon une loi cubique non linéaire : $V_N = \min(N,\, (N/X_3)^3)$.
Cela produit un débit de base lent, dominé par la récession, qui ne devient significatif que lorsque N accumule assez d'eau.

**Étape 7 : routage par UH2 et assemblage du débit**.
Les trois composantes d'écoulement — ruissellement de surface net $(V_S - A_L)$, ruissellement souterrain rapide et vidange lente de l'eau souterraine — sont chacune convoluées indépendamment à travers UH2 (temps de base $2 X_4$, exposant 2.5).
Le débit total à chaque pas de temps est la somme des trois composantes routées, bornée à zéro.

## Paramètres

Le modèle MORDOR possède 6 paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Coefficient de correction de la pluie | 0.5–2.0 | - | Mise à l'échelle multiplicative des précipitations observées. Des valeurs sous 1.0 réduisent la pluie (sur-captation du pluviomètre ou perte par interception); des valeurs au-dessus de 1.0 l'augmentent (sous-captation du pluviomètre). |
| $X_2$ | Constante de vidange du réservoir L | 1–1000 | jours | Constante de temps de la vidange linéaire du réservoir intermédiaire. Des valeurs élevées ralentissent la libération de l'eau infiltrée, élargissant la récession. |
| $X_3$ | Constante de vidange du réservoir N | 0.01–100 | - | Contrôle la vidange non linéaire (cubique) du réservoir d'eau souterraine. Des valeurs élevées réduisent la vidange de la nappe, prolongeant la récession des étiages. |
| $X_4$ | Temps de réponse de UH2 | 0.5–10 | jours | Moitié du temps de base de l'hydrogramme unitaire à deux versants. Des valeurs élevées étalent la pointe d'écoulement sur une période plus longue. |
| $X_5$ | Capacité du réservoir U | 1–1000 | mm | Capacité maximale du réservoir de surface. Contrôle la quantité de pluie pouvant être absorbée avant qu'un débordement ne survienne. |
| $X_6$ | Capacité du réservoir L | 1–1000 | mm | Capacité maximale du réservoir intermédiaire. Contrôle la quantité d'eau infiltrée pouvant être stockée avant saturation. |

**Comprendre les paramètres :**

- **$X_1$** se cale habituellement près de 1.0 (entre 0.8 et 1.2).
Des valeurs éloignées de 1.0 peuvent indiquer des problèmes avec les données de précipitations en entrée plutôt que de véritables propriétés du bassin.
- **$X_2$** et $X_3$ contrôlent ensemble la forme de la courbe de récession.
$X_2$ gouverne l'échelle de temps intermédiaire (jours à semaines), tandis que $X_3$ gouverne la composante la plus lente (semaines à mois).
Commencez le calage en ajustant $X_2$ pour reproduire la branche descendante de l'hydrogramme, puis réglez $X_3$ pour reproduire les périodes d'étiage.
- **$X_4$** contrôle le lissage et le moment du pic de l'hydrogramme.
Les petits bassins à réponse vive nécessitent typiquement $X_4 \approx 1$; les bassins plus grands au routage lent nécessitent des valeurs plus élevées.
- **$X_5$** détermine la vitesse à laquelle un bassin « sature » et commence à produire du ruissellement proportionnel.
Un $X_5$ faible rend le modèle vif; un $X_5$ élevé signifie que plus de pluie est absorbée avant que la génération de ruissellement ne devienne significative.

## Formulation mathématique

### Initialisation

États des réservoirs à $t = 0$ :

$$U_0 = \frac{X_5}{2}, \quad L_0 = \frac{X_6}{2}, \quad Z_0 = 50, \quad N_0 = 0.5$$

La constante $Z_{max} = 90$ mm est la capacité fixe du réservoir de sol profond (non calable).

### Correction de la pluie

$$P_L = P \cdot X_1$$

### Répartition de la pluie

Le ruissellement direct est proportionnel au remplissage de U :

$$DTR_1 = P_L \cdot \frac{U}{X_5}$$

Le reste entre dans U :

$$DTU_1 = P_L - DTR_1$$

Le ruissellement de surface comprend à la fois le ruissellement direct et tout débordement :

$$V_S = DTR_1 + \max(0,\, U + DTU_1 - X_5)$$

$$U \leftarrow \min(U + DTU_1,\, X_5)$$

### Évapotranspiration de surface

$$E_U = \min\!\left(U,\, X_5,\, \max\!\left(0,\, E \cdot \frac{U}{X_5}\right)\right)$$

$$U \leftarrow U - E_U$$

### Infiltration vers L

$$A_L = \min\!\left(\max(0,\, X_6 - L),\, V_S \cdot \max\!\left(0,\, 1 - \frac{L}{X_6}\right)\right)$$

$$L \leftarrow L + A_L$$

### Vidange intermédiaire (L)

$$V_L = \frac{L}{X_2}$$

$$L \leftarrow L - V_L$$

### Réservoir de sol profond (Z) et répartition de l'écoulement

Le taux de remplissage de Z détermine comment la vidange de L est distribuée :

$$z_r = \frac{Z}{Z_{max}}$$

$$DTZ = V_L \cdot (1 - z_r) \quad \text{(percolation to Z)}$$

$$RUR = 0.2 \cdot V_L \cdot z_r \quad \text{(rapid underground runoff)}$$

$$A_N = 0.8 \cdot V_L \cdot z_r \quad \text{(groundwater recharge)}$$

Z est mis à jour avec la percolation, l'évapotranspiration résiduelle et le plafonnement :

$$Z \leftarrow Z + DTZ$$

$$E_Z = \min\!\left(Z,\, (E - E_U)^+ \cdot \frac{Z}{Z_{max}}\right)$$

$$Z \leftarrow \max\!\left(0,\, \min(Z - E_Z,\, Z_{max})\right)$$

où $(x)^+ = \max(0, x)$.

### Vidange de l'eau souterraine (N)

$$N \leftarrow N + A_N$$

$$V_N = \min\!\left(N,\, \left(\frac{N}{X_3}\right)^3\right)$$

$$N \leftarrow \max(0,\, N - V_N)$$

### Hydrogramme unitaire UH2

UH2 est un hydrogramme unitaire à deux versants de temps de base $2 X_4$ et d'exposant 2.5.
Sa courbe en S est :

$$SH_2(t) = \begin{cases}
0 & \text{if } t \leq 0 \\
\frac{1}{2}\left(\frac{t}{X_4}\right)^{2.5} & \text{if } 0 < t \leq X_4 \\
1 - \frac{1}{2}\left(2 - \frac{t}{X_4}\right)^{2.5} & \text{if } X_4 < t \leq 2X_4 \\
1 & \text{if } t > 2X_4
\end{cases}$$

Les poids de UH2 sont les différences finies de la courbe en S :

$$UH_2(j) = SH_2(j) - SH_2(j-1), \quad j = 1, \ldots, \lceil 2 X_4 \rceil$$

### Débit total

Chacune des trois composantes d'écoulement est convoluée indépendamment à travers un vecteur d'état UH2, et le débit total est leur somme :

$$Q(t) = \bigl[\text{UH2} * (V_S - A_L)^+\bigr](t) + \bigl[\text{UH2} * RUR\bigr](t) + \bigl[\text{UH2} * V_N\bigr](t)$$

avec $Q(t) \geq 0$ imposé à chaque pas de temps.

## Références

- Garçon, R. (1999). Modèle global pluie-débit pour la prévision et la génération des crues. *La Houille Blanche*, 85(7-8), 88–95. [DOI](https://doi.org/10.1051/lhb/1999088)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
- Thiéry, D. (2014). Logiciel GARDÉNIA, version 8.2 — Guide d'utilisation. *Rapport final BRGM/RP-62797-FR*. (For comparison with the related EDF/BRGM modelling tradition.)
