# Modèle TOPMODEL

## Aperçu

TOPMODEL (le *TOPography-based hydrological MODEL*) a été introduit par Beven et Kirkby en 1979 comme l'un des premiers modèles pluie-débit conceptuels à exploiter explicitement l'information topographique numérique.
Sa prémisse centrale est que la *distribution spatiale des zones saturées* d'un bassin versant peut être prédite à partir d'un unique descripteur statistique de la topographie — l'indice topographique $\ln(a/\tan\beta)$, calculé pour chaque cellule d'un modèle numérique de terrain.
C'était une rupture radicale avec les modèles à réservoirs globaux de son époque, et TOPMODEL est devenu l'ancêtre conceptuel de toute une famille de modèles « semi-distribués » qui tentent de combler l'écart entre les simulateurs à base physique entièrement distribués et les modèles globaux parcimonieux.

La formulation originale de Beven & Kirkby compte environ dix degrés de liberté (capacités, transmissivités, plus la distribution de l'indice topographique elle-même).
Perrin (2000) a montré que, pour une modélisation pluie-débit globale journalière sans modèle numérique de terrain disponible, la distribution de l'indice topographique peut être approchée par une *fonction logistique* à deux paramètres, ramenant la structure à **sept paramètres à caler**.
C'est la version implémentée dans HOLMES, suivant la fiche n°33 de l'Annexe 1 de Perrin et l'implémentation de référence HM18 de HOOPLA.

Structurellement, le TOPMODEL simplifié représente un bassin versant par trois réservoirs : un réservoir d'interception $S$, un réservoir de déficit souterrain non borné $T$ et un réservoir de routage de surface quadratique $R$.
Ce qui le rend distinctif — et pédagogiquement précieux — est que la répartition de la pluie efficace entre recharge et ruissellement de surface ne se fait pas par un seuil dur ni une courbe de saturation, mais par une *fonction sigmoïde* qui dépend de l'état courant de $T$.
Le même mécanisme sigmoïde est utilisé une seconde fois pour répartir l'évapotranspiration résiduelle entre le sol et le réservoir souterrain.
Les étudiants choisissent typiquement TOPMODEL quand ils veulent étudier en quoi une fonction de partage probabiliste lisse se comporte différemment des partages à seuil utilisés dans des modèles comme HBV ou BUCKET.

## Concepts clés

- **Indice topographique** : un descripteur spatial de la forme $\ln(a/\tan\beta)$, où $a$ est l'aire contributive amont par unité de longueur de courbe de niveau et $\tan\beta$ la pente locale. Les valeurs élevées marquent les zones humides concaves près du chenal; les valeurs faibles marquent les sommets secs. Dans la réduction de Perrin, cette distribution est remplacée par une courbe logistique à deux paramètres.

- **Réservoir d'interception ($S$)** : un petit réservoir de surface de capacité $X_3$ qui intercepte la pluie et consomme la première part de l'ETP. Le débordement de $S$ devient la pluie efficace $P_r$ qui alimente le reste du modèle.

- **Réservoir de déficit souterrain ($T$)** : un réservoir *non borné* qui suit l'état souterrain moyen du bassin. Contrairement aux réservoirs de sol de GR4J ou HBV, $T$ n'a ni plafond ni plancher — il peut dériver en positif (saturation) ou en négatif (déficit profond). Ce caractère non borné est structurel dans TOPMODEL et fait partie des raisons pour lesquelles l'initialisation compte.

- **Partage sigmoïde de la recharge** : la fraction de la pluie efficace $P_r$ qui recharge $T$ est donnée par la fonction logistique $1/(1 + \exp(X_6 - T/X_5))$ — une alternative probabiliste lisse aux seuils de saturation durs utilisés dans d'autres modèles. Quand $T$ monte (bassin plus humide), la sigmoïde approche 1 et presque tout recharge; quand $T$ descend, la sigmoïde tombe à zéro et presque tout devient écoulement de surface.

- **ET souterraine sigmoïde** : une seconde fonction logistique $1/(1 + \exp(X_7 - T/X_5))$ répartit l'ETP résiduelle entre le sol et le réservoir souterrain. Suivant la Fiche 33 de Perrin — préservée littéralement depuis HOOPLA — ce terme est *ajouté* à $T$ plutôt que soustrait, une idiosyncrasie de la formulation que les étudiants questionnent souvent.

- **Débit de base exponentiel** : la vidange souterraine $Q_t = X_2 \exp(T/X_2)$ est exponentielle en $T$ : elle croît vite quand le bassin se sature et décroît lentement pendant les périodes sèches. Le fait que $X_2$ apparaisse à la fois comme préfacteur et comme échelle de récession couple l'amplitude du débit de base à la durée de la récession — un choix inhabituel aux conséquences pratiques pour le calage.

- **Réservoir de routage quadratique ($R$)** : un réservoir de routage de surface non linéaire de vidange $Q_r = R^2/(R + X_1)$. Comparée aux réservoirs linéaires de BUCKET ou HBV, cette forme quadratique livre des pics de crue plus aigus à fort stockage et des queues plus douces à faible stockage.

- **Routage par délai fractionnaire** : comme dans GR4J/GARDENIA/SACRAMENTO, le débit sortant sommé $Q_t + Q_r$ passe par un registre à décalage à deux poids de longueur $\lceil X_4 \rceil + 1$, laissant les délais non entiers se traduire en un décalage temporel lisse sans interpolation à chaque pas.

## Fonctionnement

Le modèle TOPMODEL traite les précipitations et l'évapotranspiration selon les étapes suivantes :

**Étape 1 : réservoir d'interception et pluie efficace**.
La précipitation $P$ est ajoutée au réservoir d'interception $S$, puis l'ETP en consomme la première part $E_s = \min(S, E)$.
L'ETP résiduelle, $E' = E - E_s$, alimentera l'évaporation souterraine en aval.
Si $S$ dépasse sa capacité $X_3$, le débordement $P_r$ devient la « pluie efficace » qui entre dans le reste du modèle.

**Étape 2 : recharge sigmoïde du réservoir souterrain ($P_r \to T$)**.
La pluie efficace $P_r$ est scindée en une composante de recharge $P_s$ (allant vers $T$) et une composante d'écoulement rapide $P_r - P_s$ (allant vers le réservoir de routage de surface $R$).
Le partage est gouverné par la fonction logistique $P_s = P_r / (1 + \exp(X_6 - T/X_5))$ — quand $T$ est haut (bassin humide), la majeure partie de l'eau recharge $T$; quand $T$ est bas (bassin sec), la majeure partie devient écoulement rapide.
L'état souterrain $T$ est ensuite mis à jour par $T \leftarrow T + P_r - P_s$ — c'est-à-dire que $T$ ne reçoit que la fraction *non rechargée*, parce que le $P_s$ rechargé est considéré comme ayant transité directement vers le drainage profond.

**Étape 3 : évapotranspiration souterraine sigmoïde**.
L'ETP résiduelle $E'$ est répartie par une seconde sigmoïde : $E_t = E' / (1 + \exp(X_7 - T/X_5))$.
Suivant la fiche n°33 de l'Annexe 1 de Perrin et HOOPLA HM18, ce terme est *ajouté* à $T$ plutôt que soustrait : $T \leftarrow T + E_t$.
Cette convention de signe est préservée littéralement depuis la source même si elle contredit la lecture physique évidente; elle fait partie de la formulation et la retirer changerait le comportement calé.

**Étape 4 : réservoir de routage de surface ($R$, vidange quadratique)**.
L'écoulement rapide $P_s$ (interprété comme la fraction d'excès de saturation non absorbée par $T$) est ajouté au réservoir de routage de surface $R$.
Le réservoir se vide ensuite de façon non linéaire selon $Q_r = R^2 / (R + X_1)$, une fonction de vidange quadratique qui produit des pics plus aigus à fort stockage et des queues plus douces à faible stockage qu'un réservoir linéaire.

**Étape 5 : débit de base exponentiel depuis $T$**.
Le réservoir souterrain $T$ se vide selon $Q_t = X_2 \exp(T/X_2)$, puis $T$ est mis à jour par $T \leftarrow T - Q_t$.
Comme $X_2$ apparaît à la fois comme préfacteur et comme échelle de récession, doubler $X_2$ double l'amplitude du débit de base et *divise par deux* le taux de décroissance de la récession de $T$ — les deux ne sont pas calables indépendamment, une limitation connue de la réduction à sept paramètres.

**Étape 6 : routage par délai fractionnaire du débit sortant total**.
Les deux débits sortants $Q_t$ et $Q_r$ sont sommés et poussés dans un registre décalage-et-addition $\{HY_k\}$ de longueur $n = \lceil X_4 \rceil + 1$, avec deux poids non nuls en $DL_{n-2}$ et $DL_{n-1}$ qui encodent le délai non entier $X_4$.
Le premier élément du registre, borné à zéro, est retourné comme débit simulé pour le pas de temps courant.

## Paramètres

Le TOPMODEL possède sept paramètres à caler.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ | Capacité du réservoir de routage quadratique | 1–1000 | mm | Échelle de stockage du réservoir de routage de surface $R$. Des valeurs plus grandes lissent l'hydrogramme en étalant la réponse de surface sur davantage de pas de temps. |
| $X_2$ | Paramètre de drainage souterrain exponentiel | 0.1–50 | mm | Fixe à la fois l'amplitude du débit de base à saturation ($Q_t = X_2$ quand $T = 0$) et la durée de décroissance de la récession. Les deux rôles sont couplés. |
| $X_3$ | Capacité du réservoir d'interception | 0.1–100 | mm | Capacité du réservoir de canopée/dépressions $S$. Au-delà de $X_3$, le débordement d'interception devient pluie efficace. Souvent faiblement identifiable. |
| $X_4$ | Délai de routage | 0.5–10 | jours | Délai fractionnaire du registre d'hydrogramme unitaire. N'affecte que le décalage temporel, pas la forme. |
| $X_5$ | Échelle de la distribution de l'indice topographique | 1–200 | mm | Fixe la raideur des deux fonctions de partage sigmoïdes via le terme $T/X_5$. Des valeurs plus petites font basculer les sigmoïdes plus abruptement entre les régimes humide et sec. |
| $X_6$ | Décalage de la sigmoïde de l'indice topographique | -10 – 10 | - | Décale horizontalement la sigmoïde de recharge. Des valeurs négatives favorisent la recharge; des valeurs positives favorisent l'écoulement rapide. |
| $X_7$ | Décalage de la sigmoïde d'ETP souterraine | -10 – 10 | - | Décale horizontalement la sigmoïde d'ET souterraine. Contrôle la part de l'ETP résiduelle qui finit par moduler $T$. |

**Comprendre les paramètres :**

- **$X_2$ a un double rôle et est le paramètre le plus sensible** : il fixe à la fois le taux de débit de base à saturation et la longueur de la récession exponentielle.
Doubler $X_2$ double l'amplitude du débit de base *et* double l'échelle de longueur de la récession, si bien qu'un bassin mal calé peut facilement mener à des amplitudes de débit de base incontrôlées si les bornes sont trop généreuses.
Restez dans la plage 1–30 mm pour la plupart des bassins, sauf raison sérieuse de faire autrement.
- **$X_5$ contrôle la raideur des sigmoïdes**, tandis que $X_6$ et $X_7$ contrôlent leurs décalages.
Ces trois paramètres déterminent ensemble tout le comportement de partage de TOPMODEL.
Un piège de calage courant consiste à fixer $X_5$ à une valeur modérée (disons 50 mm) et à explorer $X_6$ et $X_7$ d'abord — le modèle est bien moins identifiable quand les trois sont libres.
- **$X_1$ façonne la réponse de crue** sans affecter le bilan hydrique de long terme.
Un petit $X_1$ produit des pics nerveux; un grand $X_1$ lisse l'hydrogramme.
C'est le paramètre le plus facile à régler par inspection visuelle.
- **$X_3$ est souvent faiblement identifiable** — des capacités d'interception sous ~5 mm produisent des hydrogrammes presque indiscernables dans la plupart des bassins tempérés.
La discussion de Perrin dans la Fiche 33 note explicitement que $X_3$ « peut être fixé » sans grande perte.
- **$X_4$ est un pur paramètre de translation** : il décale l'hydrogramme dans le temps sans changer sa forme.
Calez-le en dernier, une fois que les autres se sont stabilisés dans une forme raisonnable.

**Pourquoi le réservoir souterrain est non borné** : le $T$ de TOPMODEL représente un *déficit* par rapport à une référence de saturation notionnelle, pas un stock d'eau.
Il n'y a aucune raison physique de le plafonner — un bassin peut être arbitrairement humide ($T$ positif) ou arbitrairement sec ($T$ négatif).
La fonction de vidange exponentielle $Q_t = X_2 \exp(T/X_2)$ rend le modèle autorégulé : quand $T$ croît, le débit de base croît exponentiellement et ramène $T$ vers le bas.
C'est structurellement différent des réservoirs de sol bornés de HBV/SACRAMENTO/GR4J.

## Formulation mathématique

### Initialisation

États initiaux des réservoirs (depuis `ini_HydroMod18.m` de HOOPLA, conforme à la fiche de Perrin) :

$$S_0 = 10 \ \text{mm}, \quad T_0 = -50 \ \text{mm}, \quad R_0 = 0.2 \cdot X_1$$

Le $T$ initial fortement négatif est intentionnel : il supprime le débit de base exponentiel $Q_t = X_2 \exp(T/X_2)$ pendant la mise en route, laissant la recharge remplir $T$ vers son équilibre stationnaire sans produire de pointe de vidange au démarrage.

Le tableau de routage par délai fractionnaire $\{DL_k\}$ de longueur $n = \lceil X_4 \rceil + 1$ est construit pour que seuls les deux derniers éléments soient non nuls :

$$DL_{n-2} = \frac{1}{X_4 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

C'est le même gabarit à deux poids que celui utilisé par GR4J, GARDENIA et SACRAMENTO.

### Phase de surface (réservoir d'interception)

$$S \leftarrow S + P$$

$$E_s = \min(S, E), \quad S \leftarrow S - E_s, \quad E' = E - E_s$$

$$P_r = \max(0, \ S - X_3), \quad S \leftarrow S - P_r$$

### Recharge sigmoïde du réservoir souterrain

La pluie efficace $P_r$ est répartie par une fonction logistique dépendant de $T$ :

$$P_s = \frac{P_r}{1 + \exp\left(X_6 - \dfrac{T}{X_5}\right)}$$

$$T \leftarrow T + (P_r - P_s)$$

### Évapotranspiration souterraine sigmoïde

$$E_t = \frac{E'}{1 + \exp\left(X_7 - \dfrac{T}{X_5}\right)}$$

$$T \leftarrow T + E_t$$

(Le signe suit littéralement la fiche n°33 de l'Annexe 1 de Perrin et HOOPLA HM18 — voir la note d'implémentation dans la source.)

### Réservoir de routage de surface

L'écoulement rapide $P_s$ entre dans le réservoir de routage quadratique $R$ :

$$R \leftarrow R + P_s$$

$$Q_r = \frac{R^2}{R + X_1}, \quad R \leftarrow R - Q_r$$

### Débit de base exponentiel depuis $T$

$$Q_t = X_2 \exp\left(\frac{T}{X_2}\right), \quad T \leftarrow T - Q_t$$

### Débit total et délai fractionnaire

Les deux débits sortants sont sommés et poussés dans le registre de délai décalage-et-addition $\{HY_k\}$ de longueur $n = \lceil X_4 \rceil + 1$ :

$$Q = Q_t + Q_r$$

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

Le premier élément du registre est retourné comme débit simulé; le registre avance ensuite d'une position, prêt pour le pas suivant.

## Références

Beven, K. J., & Kirkby, M. J. (1979).
A physically based, variable contributing area model of basin hydrology.
*Hydrological Sciences Bulletin*, 24(1), 43–69.
[https://doi.org/10.1080/02626667909491834](https://doi.org/10.1080/02626667909491834)

Beven, K. (1997).
TOPMODEL: a critique.
*Hydrological Processes*, 11(9), 1069–1085.

Franchini, M., Wendling, J., Obled, C., & Todini, E. (1996).
Physical interpretation and sensitivity analysis of the TOPMODEL.
*Journal of Hydrology*, 175, 293–338.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°33 (TOPMODEL), pp. 453–458.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
