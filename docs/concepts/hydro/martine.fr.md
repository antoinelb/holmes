# Modèle MARTINE

## Aperçu

MARTINE est un modèle pluie-débit global journalier à sept paramètres développé au Bureau de Recherches Géologiques et Minières (BRGM) à Orléans, en France, par Mazenc, Sanchez et Thiery (1984).
Il a été conçu à l'origine pour des études de **régionalisation** : les auteurs voulaient un modèle assez simple pour que ses paramètres puissent être reliés aux descripteurs physiographiques des bassins versants (superficie, pente, type de sol), permettant la prévision du débit sur des sites non jaugés à travers la Bretagne.

La variante implémentée dans HOLMES est la version **MART** à sept paramètres décrite dans l'annexe 1 de Perrin (2000).
Elle représente le bassin versant par quatre réservoirs : un **réservoir de surface** qui intercepte la pluie et produit un débordement, un **réservoir de routage direct quadratique** qui génère le ruissellement rapide, un **réservoir intermédiaire** doté à la fois d'une vidange linéaire et d'une voie de débordement, et un **réservoir souterrain** qui se vide linéairement pour produire le débit de base.
Un délai fractionnaire est appliqué à l'exutoire pour tenir compte du temps de parcours en rivière.

Ce qui distingue MARTINE parmi les modèles de HOLMES est son **réservoir intermédiaire à double voie**.
Contrairement aux modèles où l'écoulement de subsurface suit une seule loi de sortie, le réservoir intermédiaire $T$ se vide à la fois linéairement ($Q_{t1} = T/X_7$) *et* par débordement ($Q_{t2} = \max(0, T - X_2)$) — la voie linéaire fournit un écoulement hypodermique soutenu tandis que le débordement ne s'active que lorsque le réservoir dépasse sa capacité, produisant une poussée de débit de base déclenchée par un seuil en période humide.
Cette structure double, combinée au routage direct quadratique, donne à MARTINE une forme d'hydrogramme flexible sans exiger beaucoup de paramètres.

## Concepts clés

- **Réservoir de surface à débordement** : le réservoir le plus haut $S$ a une capacité fixe $X_1$.
La pluie qui fait dépasser $X_1$ à $S$ déborde en pluie efficace $P_r$; le reste demeure dans $S$ et est disponible pour l'évaporation.

- **Coefficient de distribution** : le paramètre $X_5$ répartit la pluie efficace $P_r$ entre la voie rapide (routage direct) et la voie lente (intermédiaire) : $X_5 \cdot P_r$ va au réservoir de routage $R$, tandis que $(1 - X_5) \cdot P_r$ va au réservoir intermédiaire $T$.

- **Routage direct quadratique** : le réservoir de routage $R$ se vide selon $Q_r = R^2 / (R + X_3)$, la même loi non linéaire que dans GARDENIA.
Pour un $R$ élevé, la réponse tend vers une vidange linéaire; pour un $R$ faible, elle devient quadratique, produisant une transition douce entre les pointes de crue et la récession.

- **Réservoir intermédiaire à double voie** : le réservoir intermédiaire $T$ possède deux voies de sortie opérant en séquence — une vidange linéaire $Q_{t1} = T / X_7$ suivie d'un débordement $Q_{t2} = \max(0, T - X_2)$ quand le réservoir dépasse sa capacité.
Les deux sorties alimentent le réservoir souterrain.

- **Évapotranspiration résiduelle** : après que le réservoir de surface a satisfait autant d'ETP qu'il le peut ($E_s = \min(S, E)$), le reliquat insatisfait $E_t = E - E_s$ est appliqué au réservoir intermédiaire.
Le réservoir intermédiaire peut donc s'assécher pendant des périodes chaudes prolongées même sans débordement de surface.

- **Récession souterraine linéaire** : le réservoir souterrain $L$ se vide linéairement au taux $Q_l = L / X_4$, produisant un débit de base soutenu.
Toutes les sorties intermédiaires ($Q_{t1}$ et $Q_{t2}$) rechargent ce réservoir.

- **Routage par délai fractionnaire** : parce que le paramètre de délai $X_6$ est un nombre réel (typiquement 0.5–5 jours), MARTINE utilise un registre de délai fractionnaire à deux éléments qui interpole entre les délais entiers adjacents — p. ex. $X_6 = 2.3$ place 77 % du flux au jour 2 et 23 % au jour 3.

## Fonctionnement

Le modèle MARTINE traite les précipitations et l'évapotranspiration à travers les étapes suivantes chaque jour :

**Étape 1 : entrée et débordement du réservoir de surface**.
La pluie est ajoutée au réservoir de surface : $S \leftarrow S + P$.
Tout excédent au-dessus de la capacité $X_1$ déborde en pluie efficace $P_r = \max(0, S - X_1)$, et le réservoir est réduit : $S \leftarrow S - P_r$.

**Étape 2 : évaporation de surface et ETP résiduelle**.
L'ETP est déduite du réservoir de surface à hauteur de ce qu'il contient : $E_s = \min(S, E)$, $S \leftarrow S - E_s$.
Le reliquat insatisfait $E_t = E - E_s$ est reporté et appliqué au réservoir intermédiaire à l'étape 4.

**Étape 3 : réservoir de routage direct**.
Le réservoir de routage reçoit la fraction rapide de la pluie efficace : $R \leftarrow R + X_5 \cdot P_r$.
Il se vide ensuite selon la loi quadratique $Q_r = R^2 / (R + X_3)$, qui génère un fort ruissellement rapide quand $R$ est grand et très peu quand $R$ est petit.
Le réservoir est mis à jour : $R \leftarrow R - Q_r$.

**Étape 4 : réservoir intermédiaire**.
L'ETP résiduelle de l'étape 2 est d'abord soustraite : $T \leftarrow \max(0, T - E_t)$.
Puis la fraction lente de la pluie efficace est ajoutée : $T \leftarrow T + (1 - X_5) \cdot P_r$.
La vidange linéaire produit $Q_{t1} = T / X_7$, et tout excédent au-dessus de la capacité produit un débordement $Q_{t2} = \max(0, T - X_2)$.
Les deux sont déduits de $T$ et envoyés au réservoir souterrain.

**Étape 5 : réservoir souterrain**.
Le réservoir souterrain reçoit les deux sorties intermédiaires : $L \leftarrow L + Q_{t1} + Q_{t2}$.
Il se vide linéairement : $Q_l = L / X_4$, $L \leftarrow L - Q_l$.
$X_4$ contrôle la vitesse de récession du débit de base.

**Étape 6 : registre de délai**.
La sortie instantanée totale $Q_l + Q_r$ est injectée dans un registre de délai fractionnaire de taille $\lceil X_6 \rceil + 1$.
Le registre se décale d'une position à chaque pas de temps et son premier élément est retourné comme débit simulé, borné à zéro.

## Paramètres

Le modèle MARTINE possède sept paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ (CRSM) | Capacité du réservoir de surface | 1–2000 | mm | Stockage maximal du réservoir de surface (interception + sol superficiel). Des valeurs élevées absorbent plus de pluie avant de produire un débordement. |
| $X_2$ (HMAM) | Capacité du réservoir intermédiaire | 1–2000 | mm | Seuil de capacité du réservoir intermédiaire. Le débordement $Q_{t2}$ n'est produit que lorsque $T > X_2$, créant une seconde voie de débit de base qui s'active en conditions humides. |
| $X_3$ (RUIM) | Paramètre du réservoir de routage quadratique | 0.01–1000 | mm | Stockage caractéristique au dénominateur de la loi quadratique $Q_r = R^2/(R+X_3)$. Un $X_3$ plus petit donne un ruissellement direct plus rapide et plus vif; un $X_3$ plus grand amortit la réponse. |
| $X_4$ (TB) | Constante de vidange du réservoir souterrain | 1–500 | jours | Temps de résidence du réservoir souterrain linéaire. Contrôle la vitesse et la persistance de la récession du débit de base. |
| $X_5$ (CRUM) | Coefficient de distribution | 0.01–0.99 | - | Fraction de la pluie efficace routée vers la voie rapide (quadratique). $1 - X_5$ va à la voie intermédiaire (lente). |
| $X_6$ | Délai | 0.5–5 | jours | Délai pur appliqué à l'exutoire via une interpolation fractionnaire. Décale l'hydrogramme sans en changer la forme. |
| $X_7$ (TP) | Constante de vidange du réservoir intermédiaire | 1–500 | jours | Temps de résidence de la vidange linéaire du réservoir intermédiaire ($Q_{t1} = T/X_7$). Une vidange plus lente ($X_7$ plus grand) signifie que plus d'eau reste dans $T$ et finit par déborder vers le réservoir souterrain. |

**Comprendre les paramètres :**

- **$X_1$** est le seuil d'interception de la pluie / du sol superficiel — la quantité de pluie que le bassin absorbe en surface avant qu'un ruissellement ne soit généré.
Il se cale typiquement entre 50 et 500 mm selon la profondeur du sol et l'occupation du territoire.
- **$X_2$ et $X_7$ ensemble** contrôlent le comportement du réservoir intermédiaire.
$X_7$ est la constante de temps de la vidange linéaire (la vitesse à laquelle l'eau percole vers la nappe), tandis que $X_2$ est le seuil de débordement (le moment où le réservoir déverse dans la nappe sous forme d'impulsion).
Un petit $X_7$ avec un grand $X_2$ donne une percolation régulière; un grand $X_7$ avec un petit $X_2$ donne des débordements par à-coups.
- **$X_3$** contrôle la forme de la récession du routage direct.
De petites valeurs (< 10 mm) font drainer les crues rapidement avec des pointes aiguës; de grandes valeurs (> 100 mm) aplatissent et retardent la composante de ruissellement direct.
- **$X_5$** est le principal levier de répartition de l'écoulement.
Des valeurs proches de 1 envoient la majeure partie de l'eau par la voie rapide (quadratique), produisant des hydrogrammes plus vifs; des valeurs proches de 0 favorisent la voie lente à travers les réservoirs intermédiaire et souterrain.
- **$X_4$** contrôle la durée de persistance du débit de base après les périodes humides.
Un $X_4$ long (semaines à mois) produit un aquifère profond et lent à mémoire saisonnière; un $X_4$ court (jours) rend le bassin plus réactif.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs :

$$S_0 = X_1, \quad T_0 = \frac{X_2}{2}, \quad L_0 = 5, \quad R_0 = 0.1 \, X_3$$

où $S$ est le réservoir de surface (initialisé à sa capacité), $T$ le réservoir intermédiaire, $L$ le réservoir souterrain et $R$ le réservoir de routage direct.
Ces valeurs initiales produisent un court transitoire de mise en route qui se dissipe généralement en quelques semaines de simulation.

Le registre de délai est un tableau fractionnaire à deux poids de taille $n = \lceil X_6 \rceil + 1$, dont seules les deux dernières entrées sont non nulles :

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### Réservoir de surface

La pluie entre dans le réservoir de surface; l'excès au-dessus de la capacité $X_1$ devient la pluie efficace :

$$S \leftarrow S + P$$

$$P_r = \max(0,\; S - X_1)$$

$$S \leftarrow S - P_r$$

L'évapotranspiration est déduite du réservoir de surface, bornée à zéro :

$$E_s = \min(S,\; E)$$

$$S \leftarrow S - E_s$$

Le reliquat insatisfait est reporté au réservoir intermédiaire :

$$E_t = E - E_s$$

### Réservoir de routage direct

La fraction rapide de la pluie efficace alimente le réservoir de routage, qui se vide de façon quadratique :

$$R \leftarrow R + X_5 \cdot P_r$$

$$Q_r = \frac{R^2}{R + X_3}$$

$$R \leftarrow R - Q_r$$

La forme quadratique produit un fort ruissellement quand $R$ est grand ($Q_r \approx R$) et un ruissellement très faible quand $R$ est petit ($Q_r \approx R^2 / X_3$).

### Réservoir intermédiaire

L'ETP résiduelle est appliquée en premier, puis la fraction lente de la pluie efficace est ajoutée :

$$T \leftarrow \max(0,\; T - E_t)$$

$$T \leftarrow T + (1 - X_5) \cdot P_r$$

Deux voies de sortie opèrent en séquence — vidange linéaire suivie d'un débordement de capacité :

$$Q_{t1} = \frac{T}{X_7}, \quad T \leftarrow T - Q_{t1}$$

$$Q_{t2} = \max(0,\; T - X_2), \quad T \leftarrow T - Q_{t2}$$

### Réservoir souterrain

Le réservoir souterrain reçoit les deux sorties intermédiaires et se vide linéairement :

$$L \leftarrow L + Q_{t1} + Q_{t2}$$

$$Q_l = \frac{L}{X_4}$$

$$L \leftarrow L - Q_l$$

### Routage par délai

La sortie instantanée totale avant routage est :

$$Q = Q_l + Q_r$$

Le registre $\{H_k\}$ est mis à jour selon la règle de décalage-addition, le nouveau flux $Q$ n'étant injecté que dans les deux dernières positions via les poids de délai fractionnaire $\{d_k\}$ :

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

Le débit simulé est le premier élément du registre, borné à zéro :

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## Références

Mazenc, B., Sanchez, M., & Thiery, D. (1984).
Analyse de l'influence de la physiographie d'un bassin versant sur les paramètres d'un modèle hydrologique global et sur les débits caractéristiques à l'exutoire.
*Journal of Hydrology*, 69, 97–118.
[DOI](https://doi.org/10.1016/0022-1694(84)90159-6)

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°19 (MARTINE), pp. 387–390.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
