# Modèle NAM

## Aperçu

NAM (Nedbør-Afstrømnings-Model, « modèle précipitation-écoulement » en danois) est un modèle pluie-débit global journalier à dix paramètres développé à l'origine par Nielsen et Hansen (1973) à la Technical University of Denmark.
Il est devenu l'un des modèles hydrologiques opérationnels les plus utilisés en Scandinavie et est encore distribué aujourd'hui dans la suite logicielle DHI MIKE, où il alimente la prévision des crues et les études de ressources en eau sur des centaines de bassins versants à travers le monde.

NAM représente le bassin versant par **sept réservoirs** : un stockage de surface $U$, un réservoir d'humidité du sol $L$, deux cascades à deux réservoirs pour l'écoulement hypodermique et le ruissellement de surface ($CK_1 \to CK_2$ et $CK_{1b} \to CK_{2b}$), et un réservoir d'eau souterraine $GW$ qui — fait inhabituel — est suivi comme un *déficit* plutôt que comme un volume stocké.
Les entrées sont réparties entre trois voies d'écoulement (ruissellement de surface, écoulement hypodermique, débit de base) par des règles par morceaux pilotées par le taux de remplissage du sol $L / X_7$, et la réponse en rivière est lissée par un hydrogramme unitaire à délai fractionnaire.

L'implémentation HOLMES est un portage fidèle de l'étape HM12 de HOOPLA (Thiboult et al., 2020), elle-même la version opérationnelle étudiée dans la thèse de Perrin (fiche n°9) : une formulation à dix paramètres plus riche que la réduction NAM0 à quatre paramètres également documentée dans la même thèse.
Nous avons choisi cette variante plus riche parce qu'elle préserve la distinction structurelle de NAM entre ruissellement de surface et écoulement hypodermique, ce qui la rend pédagogiquement intéressante par rapport aux modèles plus simples de HOLMES.

Les étudiants choisissent typiquement NAM pour étudier comment un modèle doté d'un **réservoir souterrain en déficit d'humidité du sol** et d'une **séparation explicite entre ruissellement de surface et écoulement hypodermique** se comporte sous des conditions d'humidité du sol variables, en particulier la façon dont la remontée capillaire depuis l'aquifère profond « réalimente » le réservoir de sol en période sèche.

## Concepts clés

- **Stockage de surface ($U$)** : un réservoir rapide de canopée et de dépressions de capacité $X_9$ qui intercepte la pluie, se draine latéralement en écoulement hypodermique et s'évapore au plein taux d'ETP avant que l'eau n'atteigne le sol.
Quand $U$ déborde, le surplus $PN$ entre dans la phase de production.

- **Réservoir d'humidité du sol ($L$)** : le principal réservoir de suivi de l'humidité, de capacité $X_7$.
Son taux de remplissage $L / X_7$ contrôle chaque décision de répartition de l'écoulement dans le modèle : plus il est élevé, plus l'eau va au ruissellement de surface et à la percolation profonde, et moins elle reste dans le sol.

- **Déficit souterrain ($GW$)** : la caractéristique distinctive de NAM.
Contrairement à la plupart des modèles pluie-débit, $GW$ suit à quel point l'aquifère profond est *vide* plutôt que plein.
La recharge depuis le sol réduit $GW$, le débit de base ne s'enclenche que lorsque $GW$ tombe sous le seuil $X_1$, et la remontée capillaire depuis la zone saturée est pilotée par l'*inverse* de $GW$.

- **Cascade d'écoulement hypodermique ($CK_1 \to CK_2$)** : une cascade linéaire à deux réservoirs de constante de temps partagée $X_2$.
Elle lisse l'écoulement hypodermique $QIF$ extrait de la surface avant qu'il n'atteigne la rivière, contribuant la composante de vitesse moyenne de l'hydrogramme.

- **Cascade de ruissellement de surface ($CK_{1b} \to CK_{2b}$)** : une seconde cascade linéaire à deux réservoirs, également de constante de temps $X_2$, qui lisse le ruissellement de surface $QOF$.
Deux cascades parallèles de même constante de temps permettent à NAM de distinguer *d'où* vient l'eau (saturation de surface vs écoulement hypodermique) sans distinguer *à quelle vitesse* elle voyage.

- **Évapotranspiration à trois branches** : après que l'ETP a été débitée de $U$, le modèle aboutit à l'un de trois états : (a) $U$ encore positif — aucune demande d'ETP restante; (b) $U$ devenu négatif — la demande insatisfaite $E_1$ est transmise au sol; (c) $U$ a débordé $X_9$ — le surplus $PN$ alimente la phase de production.

- **Remontée capillaire** : un petit flux ascendant $caflu$ qui déplace l'eau de la zone saturée vers le réservoir de sol.
Il est proportionnel à $\sqrt{1 - L/X_7}$ (la fraction *non saturée* du sol) et à $(X_{10} / GW)^2$ (l'*inverse au carré* du déficit souterrain), de sorte qu'il croît rapidement quand les deux réservoirs sont secs.
C'est le seul transfert d'eau ascendant dans NAM.

- **Hydrogramme unitaire à délai fractionnaire** : les quatre flux dirigés vers la rivière ($BF + BF_1 + B_1 + B_2$) sont sommés et poussés dans un registre à décalage de longueur $\lceil X_4 \rceil + 1$, de construction identique au mécanisme de délai de GR4J / SACRAMENTO, de sorte qu'un temps de routage non entier $X_4$ se traduit par un décalage lisse sans interpolation à chaque pas.

## Fonctionnement

Le modèle NAM traite la pluie et l'ETP à travers les étapes suivantes à chaque pas de temps journalier :

**Étape 1 : stockage de surface et extraction de l'écoulement hypodermique**.
La pluie $P$ est ajoutée au réservoir de surface $U$.
L'écoulement hypodermique $QIF = \min(U, \, (L/X_7) \cdot U / X_3)$ est ensuite extrait; le taux de remplissage du sol $L/X_7$ agit comme une *porte* — quand le sol est sec, très peu d'écoulement hypodermique se forme même si $U$ est plein.
$QIF$ alimente le premier réservoir de la cascade hypodermique $CK_1$, puis se propage à travers $CK_2$ pour produire l'écoulement hypodermique dirigé vers la rivière $B_2 = CK_2 / X_2$.

**Étape 2 : évapotranspiration à trois branches depuis $U$**.
L'ETP $E$ est débitée de $U$.
Si $U$ reste dans $[0, X_9]$, il n'y a pas de demande résiduelle.
Si $U$ est devenu négatif, la demande insatisfaite $E_1 = -U$ est reportée sur le réservoir de sol.
Si $U$ a débordé $X_9$, le surplus $PN = U - X_9$ entre dans la phase de production ci-dessous.

**Étape 3 : répartition du surplus $PN$ en ruissellement de surface**.
Quand $PN > 0$, le surplus est divisé en trois composantes :
le ruissellement de surface $QOF = PN \cdot (L / X_7) / X_8$,
la recharge de la nappe $G = (PN - QOF) \cdot (L/X_7 - X_5) / (1 - X_5)$ — seulement quand le sol est plus humide que le seuil de percolation $X_5$,
et la recharge du réservoir de sol $DL_0 = PN - QOF - G$.
Une subtilité comptable : quand $DL_0$ pousserait le réservoir de sol au-dessus de sa capacité $X_7$, le surplus est forcé dans $G$ mais $DL_0$ lui-même n'est *pas* décrémenté; le rognage explicite $L \leftarrow \min(L, X_7)$ plus loin restaure la conservation de la masse.

**Étape 4 : cascade de ruissellement de surface**.
Le ruissellement de surface $QOF$ alimente $CK_{1b}$, qui se propage à travers $CK_{2b}$, produisant le ruissellement de surface dirigé vers la rivière $B_1 = CK_{2b} / X_2$.

**Étape 5 : mise à jour de l'humidité du sol**.
Le réservoir de sol reçoit $DL_0$ de l'étape 3 puis subit l'évaporation du déficit de surface reporté $E_1$, pondéré par le taux de remplissage : $L \leftarrow \max(0, \, L - E_1 \cdot L / X_7)$.
Cette forme limitée par l'eau empêche un sol très sec d'être poussé en négatif par une demande d'ETP insatisfaite.

**Étape 6 : mise à jour du déficit souterrain et débit de base**.
$GW$ absorbe d'abord la recharge $G$ (qui *réduit* le déficit puisque $GW$ est de signe inversé).
Si le nouveau déficit tombe sous le seuil $X_1$, le débit de base $BF = (X_1 - GW) / X_6$ s'enclenche et comble l'écart vers $X_1$ selon la constante de temps $X_6$.
Si le débit de base devait amener $GW$ à zéro ou en dessous — ce qui provoquerait plus tard une division par zéro dans le terme de remontée capillaire — une réinitialisation d'urgence $BF_1$ évacue le surplus et borne $GW$ à un petit plancher positif.

**Étape 7 : remontée capillaire**.
Un petit flux ascendant $caflu = \sqrt{1 - L/X_7} \cdot (X_{10} / GW)^2$ déplace l'eau de la zone saturée vers le réservoir de sol, plafonné à la capacité libre du sol $X_7 - L$.
$caflu$ est ajouté à $L$ et *aussi* à $GW$ (le déficit croît de nouveau à mesure que l'eau quitte l'aquifère).
C'est le seul transfert d'eau ascendant du modèle.

**Étape 8 : routage en rivière**.
Les quatre flux dirigés vers la rivière sont sommés en $Q = BF + BF_1 + B_1 + B_2$ et poussés dans le registre à décalage à délai fractionnaire $\{HY_k\}$ de longueur $n = \lceil X_4 \rceil + 1$.
Le premier élément du registre est retourné (borné à zéro) comme débit simulé pour le pas de temps courant.

## Paramètres

Le modèle NAM possède dix paramètres à caler.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ | Seuil de débit de base souterrain | 1–1000 | mm | Le déficit d'humidité du sol auquel le débit de base s'enclenche. Quand $GW$ tombe sous cette valeur, l'aquifère commence à relâcher de l'eau. |
| $X_2$ | Constante de temps des réservoirs de routage | 1–100 | jours | Constante de temps partagée des quatre réservoirs en cascade ($CK_1$, $CK_2$, $CK_{1b}$, $CK_{2b}$). Contrôle le degré de lissage appliqué à l'écoulement hypodermique et au ruissellement de surface. |
| $X_3$ | Constante de temps de l'écoulement hypodermique | 1–100 | jours | Amortit l'extraction de l'écoulement hypodermique $QIF = (L/X_7) \cdot U / X_3$. Des valeurs élevées affament la voie hypodermique et déplacent plus d'eau vers le ruissellement de surface ou la percolation. |
| $X_4$ | Délai de routage | 0.5–10 | jours | Délai fractionnaire appliqué à l'apport total en rivière via l'hydrogramme unitaire. Paramètre purement temporel — n'affecte pas la forme de l'hydrogramme. |
| $X_5$ | Seuil de percolation du sol | 0.01–0.99 | - | Taux de remplissage du sol au-dessus duquel la recharge de la nappe $G$ s'active. En dessous, toute l'eau du surplus reste dans les cascades de surface et de ruissellement. |
| $X_6$ | Constante de temps du débit de base | 1–500 | jours | Constante de temps de récession du réservoir souterrain. Des valeurs élevées donnent des récessions de débit de base longues et lentes. |
| $X_7$ | Capacité du réservoir de sol | 1–1000 | mm | Capacité de stockage du réservoir d'humidité du sol $L$. La plupart des autres paramètres agissent via le taux de remplissage $L / X_7$, ce qui fait de ce paramètre l'*échelle maîtresse* de la phase de production. |
| $X_8$ | Constante de temps du ruissellement de surface | 1–100 | jours | Amortit l'extraction du ruissellement de surface $QOF = (L/X_7) \cdot PN / X_8$. Des valeurs élevées déplacent l'eau du ruissellement de surface vers la recharge de la nappe ou le stockage du sol. |
| $X_9$ | Capacité du réservoir de surface | 1–1000 | mm | Capacité de stockage du réservoir de surface $U$. Agit comme un seuil d'interception : une pluie inférieure à $X_9$ n'atteint jamais la phase de production. |
| $X_{10}$ | Échelle de remontée capillaire | 0.01–10 | mm | Numérateur du terme moteur de la remontée capillaire $(X_{10}/GW)^2$. Des valeurs élevées produisent un flux ascendant plus fort pendant les périodes sèches. |

**Comprendre les paramètres :**

- **$X_7$ est l'échelle maîtresse du modèle**.
Presque chaque règle de répartition de l'écoulement dépend du taux de remplissage $L / X_7$, de sorte que la valeur calée de $X_7$ fixe implicitement les sensibilités liées à l'humidité.
Les valeurs typiques calées par Perrin se situent dans la plage 100–500 mm; sous 50 mm le modèle est hyper-réactif, au-dessus de 800 mm il devient apathique.

- **$X_1$ et $X_6$ façonnent ensemble le débit de base**.
$X_1$ fixe *quand* le débit de base s'enclenche (le seuil de déficit), tandis que $X_6$ fixe *à quelle vitesse* il décroît.
Un petit $X_1$ avec un grand $X_6$ produit une queue de débit de base retardée mais très longue; un grand $X_1$ avec un petit $X_6$ donne une réponse de débit de base rapide et marquée.
Utilisez la constante de récession observée du bassin comme point de départ pour $X_6$.

- **$X_3$ vs $X_8$ contrôle l'équilibre entre écoulement hypodermique et ruissellement de surface**.
Les deux voies sont gouvernées par le même taux de remplissage, de sorte que les grandeurs relatives de $X_3$ et $X_8$ décident laquelle domine.
Un petit $X_3$ et un grand $X_8$ rendent le modèle dominé par l'écoulement hypodermique; l'inverse le rend dominé par le ruissellement de surface.

- **$X_5$ est l'interrupteur de percolation**.
Sous ce taux de remplissage du sol, *aucune* recharge de la nappe n'a lieu — toute l'eau de la phase de production cascade par les voies de surface.
Les bassins à aquifères peu profonds se calent souvent à un $X_5$ faible (recharge permanente), tandis que les bassins karstiques ou imperméables se calent à un $X_5$ élevé.

- **$X_4$ devrait être calé en dernier**, une fois que les autres paramètres ont produit un hydrogramme de la bonne *forme*.
Il n'affecte que le moment de la réponse, pas sa magnitude ni sa structure de récession.

- **$X_{10}$ est habituellement petit**.
Le terme de remontée capillaire entre comme $(X_{10}/GW)^2$, de sorte que même des valeurs modestes produisent un flux ascendant significatif quand l'aquifère est sec.
Les valeurs calées sont typiquement sous 2 mm; des valeurs au-dessus de 5 mm tendent à suralimenter le sol en période sèche et à dégrader la performance du débit de base estival.

## Formulation mathématique

### Initialisation

États initiaux des réservoirs (du fichier `ini_HydroMod12.m` de HOOPLA) :

$$U_0 = X_9, \quad L_0 = \frac{X_7}{2}, \quad GW_0 = 50 \ \text{mm}$$

$$CK_{1,0} = CK_{2,0} = CK_{1b,0} = CK_{2b,0} = 0$$

Le tableau de routage à délai fractionnaire $\{DL_k\}$ a une longueur $n = \lceil X_4 \rceil + 1$ et seules ses deux dernières entrées sont non nulles :

$$DL_{n-2} = \frac{1}{X_4 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

Cela représente un délai non entier de $X_4$ jours comme un gabarit à deux éléments à la fin d'un tableau autrement vide.
Le registre de l'hydrogramme unitaire $\{HY_k\}$ démarre à zéro dans chaque cellule.

### Réservoir de surface et écoulement hypodermique

Ajouter la pluie, puis extraire l'écoulement hypodermique gouverné par le taux de remplissage du sol :

$$U \leftarrow U + P$$

$$QIF = \min\left(U, \ \frac{L}{X_7} \cdot \frac{U}{X_3}\right), \quad U \leftarrow U - QIF$$

L'écoulement hypodermique se propage à travers la cascade à deux réservoirs $CK_1 \to CK_2$ :

$$CK_1 \leftarrow CK_1 + QIF, \quad B_{21} = \frac{CK_1}{X_2}, \quad CK_1 \leftarrow CK_1 - B_{21}$$

$$CK_2 \leftarrow CK_2 + B_{21}, \quad B_2 = \frac{CK_2}{X_2}, \quad CK_2 \leftarrow CK_2 - B_2$$

### Évapotranspiration à trois branches depuis $U$

Débiter l'ETP, puis brancher selon l'état résultant de $U$ :

$$U \leftarrow U - E$$

$$
(E_1, PN) =
\begin{cases}
(0, 0) & \text{if } 0 \le U \le X_9 \\
(-U, \, 0); \ U \leftarrow 0 & \text{if } U < 0 \\
(0, \, U - X_9); \ U \leftarrow X_9 & \text{if } U > X_9
\end{cases}
$$

Un seul de $E_1$ ou $PN$ peut être non nul à un pas de temps donné.

### Répartition du surplus en ruissellement de surface

Quand le réservoir de surface déborde ($PN > 0$), répartir le surplus entre ruissellement de surface, recharge de la nappe et recharge du réservoir de sol :

$$QOF = PN \cdot \frac{L}{X_7} \cdot \frac{1}{X_8}$$

$$G =
\begin{cases}
(PN - QOF) \cdot \dfrac{L/X_7 - X_5}{1 - X_5} & \text{if } L/X_7 > X_5 \\
0 & \text{otherwise}
\end{cases}$$

$$DL_0 = PN - QOF - G$$

Si $DL_0 > X_7$, le surplus est ajouté à $G$ (sans décrémenter $DL_0$ — le trop-plein est corrigé plus loin par un rognage explicite de $L$) :

$$\text{if } DL_0 > X_7: \quad G \leftarrow G + (DL_0 - (X_7 - L))$$

### Cascade de ruissellement de surface

Le ruissellement de surface se propage à travers la seconde cascade à deux réservoirs $CK_{1b} \to CK_{2b}$ :

$$CK_{1b} \leftarrow CK_{1b} + QOF, \quad B_{12} = \frac{CK_{1b}}{X_2}, \quad CK_{1b} \leftarrow CK_{1b} - B_{12}$$

$$CK_{2b} \leftarrow CK_{2b} + B_{12}, \quad B_1 = \frac{CK_{2b}}{X_2}, \quad CK_{2b} \leftarrow CK_{2b} - B_1$$

### Réservoir d'humidité du sol

Recharger, puis évaporer le déficit de surface résiduel, pondéré par le taux de remplissage et borné à zéro :

$$L \leftarrow L + DL_0$$

$$L \leftarrow \max\!\left(0, \ L - E_1 \cdot \frac{L}{X_7}\right)$$

### Déficit souterrain et débit de base

Rappelons que $GW$ est un *déficit* : soustraire la recharge $G$ rend l'aquifère plus humide.

$$GW \leftarrow GW - G$$

Le débit de base s'enclenche quand le déficit tombe sous le seuil $X_1$ :

$$BF =
\begin{cases}
\dfrac{X_1 - GW}{X_6} & \text{if } GW \le X_1 \\
0 & \text{otherwise}
\end{cases}, \quad GW \leftarrow GW + BF$$

Si le débit de base devait amener $GW \le 0$, une réinitialisation d'urgence relâche le surplus et borne le déficit à un petit plancher positif :

$$BF_1 =
\begin{cases}
-GW + 0.1; \ GW \leftarrow 0.1 & \text{if } GW \le 0 \\
0 & \text{otherwise}
\end{cases}$$

### Plafonnement du sol et remontée capillaire

Restaurer la conservation de la masse en rognant le réservoir de sol à sa capacité :

$$L \leftarrow \min(L, X_7)$$

Remontée capillaire de l'aquifère vers le sol, plafonnée à la capacité libre du sol :

$$caflu = \min\!\left(\sqrt{1 - L/X_7} \cdot \left(\frac{X_{10}}{GW}\right)^2, \ X_7 - L\right)$$

$$L \leftarrow L + caflu, \quad GW \leftarrow GW + caflu$$

### Débit total et délai fractionnaire

Les quatre flux dirigés vers la rivière sont sommés :

$$Q = BF + BF_1 + B_1 + B_2$$

Le registre de l'hydrogramme unitaire $\{HY_k\}$ de longueur $n = \lceil X_4 \rceil + 1$ avance d'un pas et ajoute la nouvelle contribution :

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n-2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

Le premier élément du registre est retourné comme débit simulé pour le pas de temps courant; le reste du registre est décalé à l'appel suivant.

## Références

Nielsen, S. A., & Hansen, E. (1973).
Numerical simulation of the rainfall-runoff process on a daily basis.
*Nordic Hydrology*, 4(3), 171–190.
[https://doi.org/10.2166/nh.1973.0013](https://doi.org/10.2166/nh.1973.0013)

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°9 (NAM).

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
