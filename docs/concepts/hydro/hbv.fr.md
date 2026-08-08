# Modèle HBV

## Aperçu

HBV est un modèle pluie-débit global journalier à neuf paramètres développé au Swedish Meteorological and Hydrological Institute (SMHI) par Bergström et Forsman (1973) et raffiné au cours des années 1980 et 1990.
Il est devenu l'un des modèles hydrologiques opérationnels les plus utilisés dans les régions nordiques et tempérées grâce à sa simplicité, à sa structure transparente à base de réservoirs et à sa capacité à traiter aussi bien les bassins versants dominés par la neige que ceux dominés par la pluie.

La variante implémentée dans HOLMES est **HBV0** telle que documentée dans l'annexe 1 de Perrin (2000) — une simplification à neuf paramètres du HBV opérationnel complet dans laquelle la routine de neige a été retirée et où seules les composantes du bilan hydrique de la phase terrestre demeurent.
La précipitation efficace (pluie plus fonte optionnelle de CemaNeige, si actif) entre dans un unique réservoir d'humidité du sol qui produit du ruissellement par une fonction non linéaire de la saturation.
Le ruissellement traverse ensuite un réservoir intermédiaire à deux sorties (imitant les voies proches de la surface et hypodermiques) et un réservoir de débit de base linéaire, avant d'être routé par un hydrogramme unitaire triangulaire pour tenir compte du temps de parcours en chenal.
Une caractéristique numérique clé est que le suivi de l'humidité du sol est divisé en **cinq sous-pas par pas de temps** pour réduire l'erreur d'intégration quand le sol est proche de la saturation et que la fonction de production non linéaire est raide.

## Concepts clés

- **Fonction de production non linéaire du sol** : la fraction de la pluie entrante qui contribue au ruissellement à chaque sous-pas est $(S/X_1)^{X_7}$, où $S$ est l'humidité du sol courante et $X_1$ la capacité du sol.
Quand $S \ll X_1$, presque aucun ruissellement n'est généré et la pluie recharge simplement le sol; quand $S$ s'approche de $X_1$, presque toute la pluie ruisselle.
L'exposant $X_7$ (le paramètre $\beta$ de la littérature classique sur HBV) contrôle la vitesse de la transition — des valeurs plus élevées produisent une réponse plus nette, plus proche d'un seuil.

- **Division en sous-pas pour la stabilité numérique** : comme la fonction de production est fortement non linéaire, intégrer une impulsion journalière complète de précipitations en un seul pas peut dépasser la capacité du sol et mal représenter la saturation.
HBV0 divise donc chaque jour en cinq sous-pas égaux, applique un cinquième de la pluie et de l'ET dans chacun, et accumule le ruissellement résultant.
Cette intégration implicite d'ordre supérieur est peu coûteuse et améliore significativement le bilan hydrique lors des jours de fortes pluies.

- **Seuil d'ETP** : l'évapotranspiration est mise à l'échelle par le rapport $S/X_2$, où $X_2$ est un paramètre de seuil (le paramètre $LP$ du HBV classique).
Quand le sol est au-dessus du seuil, le facteur d'échelle est proche de 1 et l'évaporation se produit à un taux quasi potentiel; sous le seuil, l'ET diminue linéairement avec l'humidité du sol, imitant le stress des plantes en situation de limitation en eau.

- **Réservoir intermédiaire à deux sorties** : au lieu d'un seul réservoir linéaire, HBV0 utilise un réservoir intermédiaire $R$ avec deux voies de sortie distinctes.
La **sortie supérieure** $Q_{r1}$ ne s'active que quand $R$ dépasse un seuil $X_8$, représentant la réponse de crue proche de la surface (écoulement hypodermique).
La **sortie inférieure** $Q_{r2}$ est toujours active et représente un drainage souterrain plus lent.
La magnitude relative des deux est contrôlée par $X_3$ et $X_9$.

- **Percolation plafonnée** : l'eau passe du réservoir intermédiaire au réservoir d'eau souterraine à un taux plafonné à $X_5$ mm par jour.
Cela représente la capacité d'infiltration limitée du profil de sol plus profond et découple l'écoulement hypodermique rapide de la recharge lente du débit de base.

- **Débit de base linéaire et routage triangulaire** : le réservoir d'eau souterraine $T$ se draine linéairement avec un temps de résidence $X_4$, produisant un débit de base soutenu.
La sortie totale ($Q_{r1} + Q_{r2} + Q_t$) est ensuite routée par un **hydrogramme unitaire triangulaire** de base $X_6$ jours, représentant le temps de parcours en chenal comme un délai lissé plutôt qu'un simple décalage temporel.

## Fonctionnement

Le modèle HBV0 traite les précipitations et l'évapotranspiration selon les étapes suivantes :

**Étape 1 : division en sous-pas**.
Chaque pas de temps journalier est divisé en cinq sous-pas égaux en divisant la pluie $P$ et l'ETP $E$ en cinquièmes ($P_5 = P/5$, $E_5 = E/5$).
Les étapes 2 à 4 sont appliquées à chaque sous-pas et la génération de ruissellement s'accumule dans un total de sous-pas $Pr$.

**Étape 2 : production non linéaire**.
À chaque sous-pas, la fraction $(S/X_1)^{X_7}$ de $P_5$ est détournée vers le ruissellement $Pr_i$ et le reste remplit le sol : $S \leftarrow S + (P_5 - Pr_i)$.
Comme le multiplicateur est élevé à la puissance $X_7$, le réservoir de sol sature brusquement quand $S$ s'approche de $X_1$, reproduisant le comportement à seuil observé des bassins versants humides.

**Étape 3 : évapotranspiration**.
L'évaporation au niveau du sous-pas est $E_{si} = E_5 \cdot S/X_2$, plafonnée au $S$ courant pour que le sol ne devienne pas négatif.
Quand $S$ est au-dessus de $X_2$, l'évaporation dépasse le taux potentiel (un artefact de modélisation du schéma simplifié), mais le plafond $\min(S, \cdot)$ empêche toute impossibilité physique.
Le sol est mis à jour comme $S \leftarrow S - E_{si}$.

**Étape 4 : fin de la boucle de sous-pas**.
Après cinq sous-pas, le ruissellement total $Pr$ issu du sol est passé à la phase de routage.
Ceci conclut la phase de production du modèle.

**Étape 5 : sortie supérieure (linéaire à seuil)**.
Le réservoir intermédiaire $R$ reçoit d'abord $Pr$.
Si $R$ dépasse le seuil $X_8$, une sortie supérieure $Q_{r1} = (R - X_8)/X_3$ s'active; sinon $Q_{r1} = 0$.
Ce mécanisme à seuil représente l'écoulement hypodermique proche de la surface qui ne s'active que quand le sol est assez humide — une caractéristique courante des implémentations opérationnelles de HBV.
$R$ est ensuite décrémenté : $R \leftarrow R - Q_{r1}$.

**Étape 6 : sortie inférieure (linéaire)**.
Ce qui reste dans $R$ se draine linéairement au taux $Q_{r2} = R / (X_3 \cdot X_9)$.
Contrairement à la sortie supérieure, cette composante est toujours active et représente un drainage souterrain plus lent.
$R$ est mis à jour : $R \leftarrow R - Q_{r2}$.

**Étape 7 : percolation**.
Une fraction du $R$ restant percole vers le réservoir d'eau souterraine, plafonnée au taux maximal $X_5$ : $I_r = \min(R, X_5)$.
$R$ est décrémenté de $I_r$ et le réservoir d'eau souterraine $T$ est incrémenté du même montant.
Ce plafond introduit un découplage entre l'écoulement hypodermique rapide et le débit de base lent — quand $R$ est élevé, la majeure partie de l'eau sort par $Q_{r1}$ et $Q_{r2}$, et seule une quantité fixe limitée recharge l'eau souterraine.

**Étape 8 : débit de base**.
Le réservoir d'eau souterraine se draine linéairement : $Q_t = T / X_4$, puis $T \leftarrow T - Q_t$.
De longs temps de résidence ($X_4$ grand) produisent un débit de base soutenu qui prolonge les courbes de récession sur des semaines.

**Étape 9 : routage triangulaire**.
La sortie totale $Q = Q_{r1} + Q_{r2} + Q_t$ est convoluée avec un hydrogramme unitaire triangulaire de base $X_6$ jours, lissant l'hydrogramme et représentant le temps de parcours en chenal jusqu'à l'exutoire.
Le premier élément du registre de délai est retourné comme débit simulé, borné à zéro.

## Paramètres

Le modèle HBV0 possède neuf paramètres à caler.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ ($F_c$) | Capacité du réservoir de sol | 100–1000 | mm | Stockage maximal du réservoir d'humidité du sol. Des valeurs élevées retardent la génération de ruissellement et prolongent la mémoire des périodes sèches. |
| $X_2$ ($LP$) | Seuil d'ETP | 1–1000 | mm | Niveau d'humidité du sol au-dessus duquel l'évaporation se produit à un taux quasi potentiel. Sous $X_2$, l'ET est réduite linéairement avec $S/X_2$. |
| $X_3$ | Constante de vidange supérieure du réservoir intermédiaire | 1–20 | jours | Facteur de temps de résidence à la fois pour la sortie supérieure à seuil $Q_{r1}$ et pour la sortie linéaire inférieure $Q_{r2}$. Des valeurs élevées ralentissent le réservoir intermédiaire. |
| $X_4$ | Constante de vidange du réservoir souterrain | 1–100 | jours | Temps de résidence du réservoir souterrain linéaire. Des valeurs élevées produisent des récessions de débit de base plus longues. |
| $X_5$ | Coefficient de percolation | 1–20 | mm/jour | Taux maximal de transfert d'eau du réservoir intermédiaire au réservoir d'eau souterraine. Plafonne la recharge du débit de base quelle que soit l'humidité de $R$. |
| $X_6$ | Base de temps de l'hydrogramme unitaire triangulaire | 2–40 | jours | Durée totale de l'hydrogramme unitaire triangulaire. Le pic est à $X_6 / 2$ et la réponse revient à zéro à $X_6$. |
| $X_7$ ($\beta$) | Exposant de non-linéarité du sol | 0–50 | - | Exposant sur $(S/X_1)$ dans la fonction de production. $X_7 = 0$ donne une réponse purement linéaire (toute la pluie ruisselle); de grandes valeurs donnent un comportement à seuil net où la pluie ne ruisselle que quand $S$ est proche de $X_1$. |
| $X_8$ ($UZL$) | Seuil d'écoulement du réservoir intermédiaire | 0–100 | mm | Niveau de $R$ au-dessus duquel la sortie supérieure $Q_{r1}$ s'active. Quand $R < X_8$, seule $Q_{r2}$ draine le réservoir. |
| $X_9$ | Multiplicateur de la constante de vidange inférieure | 1–20 | - | Multiplicateur combiné avec $X_3$ pour donner le temps de résidence effectif de la sortie inférieure $Q_{r2}$. Le produit $X_3 \cdot X_9$ est contraint à être $\geq 1$ par les bornes pour garantir la stabilité numérique. |

**Comprendre les paramètres :**

- **$X_1$ et $X_7$ ensemble** définissent la phase de production.
$X_1$ est la capacité du sol; $X_7$ est l'exposant $\beta$ de Bergström qui contrôle la brusquerie avec laquelle la génération de ruissellement s'accélère à mesure que le sol se remplit.
Un $X_7$ élevé (p. ex. 5–10) donne une réponse de type seuil caractéristique des bassins versants réels, tandis que $X_7 = 0$ fait que toute la pluie génère directement du ruissellement.
- **$X_2$** fixe le niveau d'humidité du sol au-dessus duquel l'ET se produit librement.
Dans la littérature classique sur HBV, c'est le paramètre $LP$, typiquement fixé autour de $0.5$ à $0.8 \cdot X_1$.
- **$X_3$, $X_8$ et $X_9$ ensemble** définissent la dynamique du réservoir intermédiaire.
$X_8$ est le seuil au-dessus duquel la sortie supérieure (rapide) s'active, $X_3$ contrôle la vitesse de drainage des deux sorties, et $X_9$ règle la vitesse relative de la sortie inférieure (lente).
- **$X_4$** est la constante de vidange linéaire de l'eau souterraine — plus elle est longue, plus le débit de base persiste pendant les périodes sèches.
- **$X_5$** est le plafond de percolation.
Il agit comme un plafond sur la quantité d'eau par jour pouvant atteindre le réservoir de débit de base, quelle que soit la plénitude du réservoir intermédiaire.
- **$X_6$** est un paramètre de lissage : une base de temps d'hydrogramme unitaire plus longue retarde *et* lisse le pic de l'hydrogramme, tandis qu'un hydrogramme unitaire court livre la réponse presque instantanément.

**Resserrement des bornes pour la stabilité numérique :**
L'implémentation de référence HOOPLA autorise $X_2 = 0$ et $X_9 = 0$ comme valeurs de paramètres valides, mais cette implémentation HOLMES impose $X_2 \geq 1$ et $X_9 \geq 1$.
La première borne évite une division par zéro dans la formule d'évaporation $E_5 \cdot S / X_2$.
La seconde garantit que $X_3 \cdot X_9 \geq 1$, ce qui garantit à son tour $Q_{r2} \leq R$, de sorte que le réservoir intermédiaire $R$ ne peut jamais devenir négatif par construction — la boucle interne n'a besoin d'aucun bornage à l'exécution.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs :

$$S_0 = X_1, \quad R_0 = 1, \quad T_0 = 10$$

où $S$ est l'humidité du sol, $R$ le réservoir intermédiaire et $T$ le réservoir d'eau souterraine.
Le sol est initialisé à sa capacité (et non vide) pour que le modèle atteigne plus vite un bilan hydrique réaliste pendant la période de mise en route.

Les poids de l'hydrogramme unitaire triangulaire sont construits à partir de $X_6$ comme :

$$h_k = \begin{cases} k - 0.5 & \text{for } 1 \leq k \leq \lfloor X_6 / 2 \rfloor \quad \text{(rising limb)} \\ X_6 + 0.5 - k & \text{for } \lfloor X_6 / 2 \rfloor + 1 \leq k \leq \lceil X_6 \rceil \quad \text{(recession limb)} \end{cases}$$

Les poids sont ensuite normalisés pour que leur somme vaille un : $h_k \leftarrow h_k / \sum_j h_j$.

### Phase de production (cinq sous-pas)

À chaque sous-pas $i = 1, 2, 3, 4, 5$, avec $P_5 = P/5$ et $E_5 = E/5$ :

$$Pr_i = P_5 \cdot \left(\min\left(1, \frac{S}{X_1}\right)\right)^{X_7}$$

$$Pr \leftarrow Pr + Pr_i$$

$$S \leftarrow S + (P_5 - Pr_i)$$

$$E_{si} = \min\left(S, \ E_5 \cdot \frac{S}{X_2}\right)$$

$$S \leftarrow S - E_{si}$$

Après cinq sous-pas, $Pr$ est le ruissellement total quittant le sol pour entrer dans la phase de routage.

### Sortie supérieure (linéaire à seuil)

Le réservoir intermédiaire $R$ reçoit d'abord le ruissellement généré par le sol :

$$R \leftarrow R + Pr$$

La sortie supérieure $Q_{r1}$ ne s'active que quand $R$ est au-dessus du seuil $X_8$ :

$$Q_{r1} = \max\left(0, \ \frac{R - X_8}{X_3}\right)$$

$$R \leftarrow R - Q_{r1}$$

### Sortie inférieure (linéaire)

Ce qui reste se draine à un taux linéaire constant :

$$Q_{r2} = \frac{R}{X_3 \cdot X_9}$$

$$R \leftarrow R - Q_{r2}$$

La contrainte de borne $X_3 \cdot X_9 \geq 1$ garantit $Q_{r2} \leq R$, de sorte que $R$ reste non négatif sans bornage à l'exécution.

### Percolation

La percolation de $R$ vers $T$ est plafonnée à $X_5$ :

$$I_r = \min(R, \ X_5)$$

$$R \leftarrow R - I_r$$

### Réservoir d'eau souterraine

Le réservoir d'eau souterraine reçoit $I_r$ et se draine linéairement :

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_4}$$

$$T \leftarrow T - Q_t$$

### Sortie totale et routage triangulaire

La sortie totale instantanée avant routage est la somme des trois composantes :

$$Q = Q_{r1} + Q_{r2} + Q_t$$

Le débit simulé est obtenu en convoluant $Q$ avec l'hydrogramme unitaire triangulaire $\{h_k\}$ via un registre de décalage-addition $\{H_k\}$ de même longueur que $\{h_k\}$ :

$$H_k \leftarrow H_{k+1} + h_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow h_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ H_0)$$

Le premier élément du registre est retourné comme débit du pas de temps courant, et le registre est décalé d'une position, prêt pour le pas de temps suivant.

## Références

Bergström, S., & Forsman, A. (1973).
Development of a conceptual deterministic rainfall-runoff model.
*Nordic Hydrology*, 4(3), 147–170.

Bergström, S. (1995).
The HBV model.
In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology*, Chapter 13.
Water Resources Publications, 443–476.

Lindström, G., Johansson, B., Persson, M., Gardelin, M., & Bergström, S. (1997).
Development and test of the distributed HBV-96 hydrological model.
*Journal of Hydrology*, 201, 272–288.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°15 (HBV), pp. 366–371.

Seibert, J. (1997).
Estimation of parameter uncertainty in the HBV model.
*Nordic Hydrology*, 28(4/5), 247–262.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
