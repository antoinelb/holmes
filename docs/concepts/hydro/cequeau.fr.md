# Modèle CEQUEAU

## Aperçu

CEQUEAU est un modèle pluie-débit conceptuel développé à l'origine à l'INRS-Eau (Institut National de la Recherche Scientifique) au Québec, Canada, par Girard, Morin et Charbonneau (1972).
Le nom vient de l'ancien nom de l'institut.
Dans sa forme originale, CEQUEAU est un modèle spatialement distribué conçu pour être utilisé avec des bases de données physiographiques, mais il peut aussi fonctionner en mode global.

La version implémentée dans HOLMES suit la variante simplifiée « CEQU » décrite dans Perrin (2000), qui réduit la formulation originale à 11 paramètres à 9 paramètres.
Cette version simplifiée supprime le mécanisme de répartition des surfaces imperméables, fixe le seuil d'évapotranspiration et ajoute un paramètre de délai temporel pur.
Malgré ces simplifications, la structure centrale à deux réservoirs du modèle original est préservée.

CEQUEAU représente le bassin versant à l'aide de deux réservoirs interconnectés : un réservoir de surface (sol) qui gère les précipitations, l'évapotranspiration et l'infiltration, et un réservoir d'eau souterraine qui reçoit l'eau percolée et produit les composantes d'écoulement plus lentes.
Les deux réservoirs génèrent plusieurs voies de sortie — certaines à seuil, d'autres continues — ce qui donne au modèle une flexibilité considérable pour reproduire différentes formes d'hydrogrammes.

## Concepts clés

- **Réservoir de surface** : le réservoir supérieur, qui reçoit directement les précipitations.
Il produit trois voies de sortie distinctes (débordement, drainage à seuil et drainage continu) et perd de l'eau à la fois par évapotranspiration et par infiltration vers le réservoir d'eau souterraine.

- **Réservoir d'eau souterraine** : le réservoir inférieur, alimenté par l'infiltration depuis le réservoir de surface.
Il produit deux voies de sortie (écoulement hypodermique à seuil et débit de base continu) et est aussi soumis à l'évapotranspiration issue de la demande d'ETP restante.

- **Drainage à seuil** : plusieurs sorties de CEQUEAU ne s'activent que lorsque le niveau du réservoir dépasse un seuil.
Cela permet au modèle de représenter un comportement non linéaire où certaines voies d'écoulement ne contribuent qu'en conditions humides.

- **Drainage continu** : d'autres sorties sont proportionnelles au niveau courant du réservoir indépendamment de tout seuil, fournissant une contribution de base en tout temps.

- **Délai de routage** : une translation temporelle pure appliquée au débit total avant la sortie, représentant le temps de parcours de l'eau à travers le réseau de chenaux jusqu'à l'exutoire du bassin versant.

## Fonctionnement

CEQUEAU fonctionne au pas de temps journalier et traite les précipitations et l'évapotranspiration potentielle selon la séquence suivante :

**Étape 1 : entrée des précipitations**. Toutes les précipitations entrent directement dans le réservoir de surface.
Contrairement au modèle CEQUEAU original, la version simplifiée ne répartit pas les précipitations entre le ruissellement des surfaces imperméables et l'entrée du sol (le coefficient TRI est fixé à zéro).

**Étape 2 : évapotranspiration de surface**. Le réservoir de surface perd de l'eau par évapotranspiration.
L'évapotranspiration réelle est limitée à la fois par la demande d'ETP et par l'eau disponible, avec un facteur d'échelle linéaire qui dépend du rapport entre le niveau du réservoir et la moitié de sa capacité ($X_5/2$).
Quand le réservoir est plus qu'à moitié plein, l'ET réelle égale l'ET potentielle; en dessous, elle diminue linéairement.

**Étape 3 : infiltration (percolation)**. L'eau au-dessus du seuil d'infiltration $X_1$ percole vers le réservoir d'eau souterraine à un taux contrôlé par la constante d'infiltration $X_3$.
C'est la seule voie reliant les deux réservoirs.

**Étape 4 : drainage de surface**. Le réservoir de surface produit trois sorties en séquence : un drainage latéral à seuil (au-dessus de $X_2$, contrôlé par $X_4$), un drainage latéral continu (contrôlé par $X_4 \cdot X_8$) et un débordement si le réservoir dépasse sa capacité $X_5$.
Chaque sortie est soustraite du réservoir avant le calcul de la suivante, donc leur ordre compte.

**Étape 5 : dynamique de l'eau souterraine**. Le réservoir d'eau souterraine reçoit l'eau infiltrée et produit deux sorties : un écoulement hypodermique à seuil (au-dessus de $X_7$, contrôlé par $X_4 \cdot X_9$) et un débit de base continu (contrôlé par $X_4 \cdot X_8 \cdot X_9^2$).
Toute demande d'ETP restante après l'évapotranspiration de surface est appliquée au réservoir d'eau souterraine, encore une fois avec une mise à l'échelle linéaire relative à $X_7$.

**Étape 6 : débit total et délai**. Les cinq composantes de sortie sont additionnées pour produire le débit total, qui est ensuite retardé de $X_6$ pas de temps par interpolation linéaire pour les délais non entiers.

## Paramètres

CEQUEAU (variante CEQU) possède neuf paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Seuil d'infiltration | 0–3000 | mm | Niveau du réservoir de surface au-dessus duquel l'eau s'infiltre vers le réservoir d'eau souterraine. Des valeurs élevées réduisent la percolation. |
| $X_2$ | Seuil de drainage du sol | 1–3000 | mm | Niveau du réservoir de surface au-dessus duquel le drainage latéral à seuil se produit. Contrôle le moment où l'écoulement latéral rapide s'active. |
| $X_3$ | Constante d'infiltration | 1–100 | - | Contrôle le taux d'infiltration. Des valeurs élevées ralentissent l'infiltration vers le réservoir d'eau souterraine. |
| $X_4$ | Constante de drainage supérieure | 1–50 | - | Constante de temps de drainage principale du réservoir de surface. Apparaît aussi comme facteur dans les constantes de drainage de l'eau souterraine. |
| $X_5$ | Capacité du réservoir de surface | 1–8000 | mm | Capacité maximale du réservoir de surface (sol). Détermine aussi le seuil de mise à l'échelle de l'évapotranspiration à $X_5/2$. |
| $X_6$ | Délai de routage | 0.1–20 | jours | Translation temporelle pure appliquée au débit total. Reflète le temps de parcours en chenal jusqu'à l'exutoire. |
| $X_7$ | Seuil de drainage de l'eau souterraine | 0.01–500 | mm | Niveau du réservoir d'eau souterraine au-dessus duquel l'écoulement hypodermique se produit. Met aussi à l'échelle l'évapotranspiration de l'eau souterraine. |
| $X_8$ | Constante de drainage inférieure | 1–1000 | - | Multiplicateur du drainage continu (lent) du réservoir de surface. Contribue aussi à la constante de débit de base de l'eau souterraine. |
| $X_9$ | Constante de drainage de l'eau souterraine | 1–3000 | - | Contrôle à la fois le taux d'écoulement hypodermique (comme $X_4 \cdot X_9$) et le taux de débit de base (comme $X_4 \cdot X_8 \cdot X_9^2$). |

**Comprendre les paramètres :**

- **$X_1$ et $X_2$** sont des seuils qui contrôlent l'activation des différentes voies de drainage.
Si $X_1$ est très grand, presque aucune eau n'atteint le réservoir d'eau souterraine; si $X_2$ est très grand, le drainage de surface à seuil s'active rarement.
- **$X_3$ et $X_4$** sont les constantes de drainage principales.
$X_4$ apparaît dans plusieurs équations de sortie, ce qui en fait un paramètre central qui influence la vitesse globale de la réponse du bassin versant.
- **$X_5$** joue un double rôle : il fixe le seuil de débordement du réservoir de surface et détermine quand l'évapotranspiration devient limitée par l'eau disponible (à $X_5/2$).
- **$X_6$** est un paramètre purement temporel — il décale l'hydrogramme entier sans changer sa forme.
- **$X_8$ et $X_9$** interagissent avec $X_4$ pour former des constantes de drainage composites pour les voies d'écoulement plus lentes.
Cette paramétrisation signifie qu'ajuster $X_4$ affecte tous les taux de drainage simultanément.

## Formulation mathématique

### Initialisation

Le réservoir de surface est initialisé à un niveau fixe, tandis que le réservoir d'eau souterraine est fixé à 20 % de son paramètre de capacité :

$$S_0 = 500, \quad T_0 = 0.2 \cdot X_5$$

où $S$ est le niveau du réservoir de surface et $T$ le niveau du réservoir d'eau souterraine.

### Réservoir de surface : précipitations et évapotranspiration

Les précipitations sont ajoutées directement au réservoir de surface :

$$S \leftarrow S + P$$

L'évapotranspiration réelle du réservoir de surface est limitée à la fois par la demande d'ETP et par l'eau disponible, avec une mise à l'échelle linéaire quand le réservoir est sous la moitié de sa capacité :

$$E_s = \min\!\left(S,\ E \cdot \min\!\left(1,\ \frac{2S}{X_5}\right)\right)$$

Le réservoir est mis à jour et la demande d'ETP restante est calculée :

$$S \leftarrow S - E_s, \quad E' = E - E_s$$

### Réservoir de surface : infiltration

L'eau au-dessus du seuil d'infiltration percole vers le réservoir d'eau souterraine :

$$I_s = \frac{\max(0,\ S - X_1)}{X_3}$$

$$S \leftarrow S - I_s$$

### Réservoir de surface : drainage

Trois sorties sont calculées séquentiellement, chacune vidant le réservoir avant la suivante :

**Drainage latéral à seuil** (activé quand $S > X_2$) :

$$Q_{s2} = \frac{\max(0,\ S - X_2)}{X_4}$$

$$S \leftarrow S - Q_{s2}$$

**Drainage latéral continu** (toujours actif) :

$$Q_{s3} = \frac{S}{X_4 \cdot X_8}$$

$$S \leftarrow S - Q_{s3}$$

**Débordement** (quand le réservoir dépasse sa capacité) :

$$Q_{s1} = \max(0,\ S - X_5)$$

$$S \leftarrow S - Q_{s1}$$

### Réservoir d'eau souterraine

Le réservoir d'eau souterraine reçoit l'infiltration du réservoir de surface :

$$T \leftarrow T + I_s$$

**Écoulement hypodermique à seuil** (activé quand $T > X_7$) :

$$Q_{t1} = \frac{\max(0,\ T - X_7)}{X_4 \cdot X_9}$$

$$T \leftarrow T - Q_{t1}$$

**Débit de base continu** :

$$Q_{t2} = \frac{T}{X_4 \cdot X_8 \cdot X_9^2}$$

$$T \leftarrow T - Q_{t2}$$

**Évapotranspiration de l'eau souterraine** issue de la demande d'ETP restante :

$$E_t = \min\!\left(T,\ E' \cdot \min\!\left(1,\ \frac{T}{X_7}\right)\right)$$

$$T \leftarrow T - E_t$$

### Débit total

Le débit total est la somme des cinq composantes de drainage :

$$Q_{total} = Q_{s1} + Q_{s2} + Q_{s3} + Q_{t1} + Q_{t2}$$

### Délai de routage

Le débit total est retardé de $X_6$ pas de temps selon un schéma d'interpolation linéaire.
Pour un délai de $X_6$ jours, une ligne de délai de longueur $\lceil X_6 \rceil + 1$ répartit l'écoulement entre deux positions adjacentes pour gérer les délais non entiers :

$$Q(t) = \text{delayed}(Q_{total},\ X_6)$$

## Différences par rapport au CEQUEAU original

La variante CEQU implémentée dans HOLMES diffère du modèle CEQUEAU original (Girard et al., 1972) de trois façons :

1. **Pas de répartition des surfaces imperméables** : le coefficient TRI et le seuil HRIMP sont supprimés.
Toutes les précipitations entrent directement dans le réservoir de surface, ce qui réduit le nombre de paramètres de deux.

2. **Seuil d'évapotranspiration fixé** : le modèle original utilise un paramètre distinct (HINT) comme seuil au-dessus duquel l'ET réelle égale l'ET potentielle.
La version simplifiée fixe ce seuil à la moitié de la capacité du réservoir de surface ($X_5/2$), ce qui élimine un paramètre.

3. **Délai de routage ajouté** : un paramètre de délai temporel pur ($X_6$) est ajouté pour translater le débit total dans le temps, représentant le routage en chenal.
Le modèle original gère le routage à travers sa structure de grille distribuée.

## Références

Girard, G., Morin, G., & Charbonneau, R. (1972). Modèle précipitations-débits à discrétisation spatiale. *Cahiers ORSTOM, Série Hydrologie*, IX(4), 35-52.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*. PhD Thesis, INPG Grenoble, Appendix 1, pp. 322-326. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
