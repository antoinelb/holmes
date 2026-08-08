# Modèle SACRAMENTO

## Aperçu

SACRAMENTO est un modèle pluie-débit global journalier à neuf paramètres dérivé du modèle Sacramento Soil Moisture Accounting (SAC-SMA) développé par Burnash, Ferral et McGuire (1973) au National Weather Service des États-Unis.
Il est devenu l'épine dorsale du NWS River Forecast System et est opérationnel dans les centres de prévision américains depuis plus de quatre décennies, ce qui en fait l'un des modèles conceptuels les plus rigoureusement éprouvés sur le terrain en hydrologie opérationnelle.

Le SAC-SMA original expose quatorze paramètres répartis sur cinq zones d'humidité du sol (tension de zone supérieure, eau libre de zone supérieure, tension de zone inférieure, eau libre primaire de zone inférieure, eau libre secondaire de zone inférieure), mais Perrin (2000) a montré qu'une variante simplifiée à neuf paramètres conserve l'essentiel de la richesse structurelle tout en étant considérablement plus facile à caler.
La variante implémentée dans HOLMES est cette **« version retenue »** décrite dans l'annexe 1 de la thèse de Perrin (fiche n°27) : elle fusionne les compartiments d'eau libre primaire et secondaire de la zone inférieure en un seul réservoir, fixe la fraction de surface imperméable à zéro, fige la capacité d'interception à 3 mm et simplifie la fonction d'infiltration.
Structurellement, le résultat est une cascade de cinq réservoirs — $S$ (interception), $T$ (tension de zone supérieure), $R$ (eau libre de zone supérieure), $L$ (routage de zone inférieure) et $M$ (routage direct) — reliés par l'évaporation, la percolation, la sortie hypodermique et une correction de bilan de masse qui peut déplacer l'eau *vers le haut* de $R$ vers $L$ quand l'évapotranspiration sur-vide le réservoir inférieur.

Les étudiants choisissent typiquement SACRAMENTO pour étudier comment un schéma de suivi de l'humidité du sol de niveau opérationnel sépare le ruissellement en composantes directe, hypodermique et de débit de base à l'aide de réservoirs explicites pour chaque voie — une décomposition plus riche que celle qu'exposent des modèles plus simples comme GR4J ou BUCKET.

## Concepts clés

- **Réservoir d'interception** : un petit réservoir à capacité fixe $S$ (3 mm) qui intercepte la pluie et consomme la première part de l'ETP avant que l'eau n'atteigne le sol.
Il imite le stockage par la canopée et les dépressions.

- **Eau de tension de zone supérieure ($T$)** : le principal réservoir d'humidité du sol, jouant le rôle de « uztwm » dans la notation de Burnash.
Il reçoit la pluie au sol, relâche de l'eau vers le réservoir d'eau libre $R$ par percolation, se draine latéralement en écoulement hypodermique, perd de l'eau par évapotranspiration et déborde lorsqu'il est saturé.

- **Eau libre de zone supérieure ($R$)** : un réservoir de débit de base rapide qui reçoit la majeure partie de la percolation depuis $T$ et se vide linéairement avec la constante de temps $X_3$.
Dans le modèle original de Burnash, c'est le réservoir « uzfwm ».

- **Réservoir de routage de zone inférieure ($L$)** : un réservoir de petite capacité (plafonné à 30 mm) situé entre $T$ et $R$ qui absorbe une fraction $X_7$ de la percolation et évapore aussi l'ETP résiduelle.
Quand son contenu est sur-vidé par l'ET, une correction de bilan de masse fait remonter de l'eau depuis $R$.

- **Réservoir de routage direct ($M$)** : un réservoir linéaire rapide qui reçoit uniquement le *débordement de saturation* de $T$ et se vide avec la constante de temps $X_1$, produisant la composante de ruissellement direct de l'hydrogramme.

- **Percolation avec rétroaction de remplissage** : la percolation de $T$ vers $R$ est modulée par le taux de remplissage $R/X_2$ du réservoir *récepteur* : à mesure que $R$ se remplit, la percolation ralentit et plus d'eau reste dans $T$ (où elle peut soit s'évaporer, soit se drainer latéralement, soit déborder).
Cette rétroaction est le cœur de l'idée de suivi de l'humidité du sol de Burnash.

- **Correction ascendante de bilan de masse** : si l'ETP résiduelle sur-évapore le réservoir de routage de zone inférieure $L$, le modèle puise le déficit $I_r$ dans l'espace libre de $R$ au-dessus de $X_2 - 30$.
C'est le seul processus du modèle où l'eau se déplace contre la gravité.

- **Routage par délai fractionnaire** : les trois sorties $Q_r$, $Q_m$ et $Q_{t1}$ sont sommées et passées dans un registre de délai fractionnaire de longueur $\lceil X_9 \rceil + 1$, identique au mécanisme de délai de GR4J/GARDENIA — cela permet à des valeurs non entières de $X_9$ de se traduire en un décalage temporel lisse sans recourir à une interpolation à chaque pas.

## Fonctionnement

Le modèle SACRAMENTO traite les précipitations et l'évapotranspiration à travers les étapes suivantes :

**Étape 1 : réservoir d'interception (phase de surface)**.
La pluie $P$ est ajoutée au réservoir d'interception $S$.
L'évaporation $E_s = \min(E, S)$ consomme la première part de l'ETP du jour depuis $S$; le reste de l'ETP, $E' = E - E_s$, devient le « résiduel » qui cascadera à travers le reste du modèle.
Si $S$ déborde son plafond fixe $XF_1 = 3$ mm, le débordement $I_s$ entre dans le réservoir de tension de zone supérieure $T$.

**Étape 2 : percolation vers le réservoir d'eau libre ($T \to R$)**.
Le réservoir de tension $T$ reçoit d'abord $I_s$.
Le taux de percolation est ensuite calculé comme $I_t = X_5 \cdot (1 - R/X_2) \cdot T/X_4$, borné à $[0, T]$ pour ne jamais dépasser l'eau disponible.
Le facteur $(1 - R/X_2)$ implémente la « rétroaction de remplissage » de Burnash — quand $R$ sature, $I_t$ tombe à zéro, et le réservoir de tension doit évacuer son eau par les autres voies.

**Étape 3 : écoulement hypodermique et évaporation depuis $T$**.
L'eau résiduelle dans $T$ produit une sortie hypodermique $Q_{t1} = T/X_6$ (la voie de l'écoulement hypodermique) puis est soumise à l'ETP résiduelle, pondérée par $T/X_4$ pour représenter une évaporation limitée par l'eau.
L'ETP restante après cette étape, $E''$, est ce qui atteint finalement le réservoir de zone inférieure $L$.

**Étape 4 : débordement de saturation de $T$**.
Si $T$ dépasse encore sa capacité $X_4$ après tout ce qui précède, l'excès $Q_{t0} = \max(0, T - X_4)$ déborde dans le réservoir de routage direct $M$.
C'est la composante d'excès de saturation du ruissellement direct.

**Étape 5 : routage vers $L$ et $R$**.
La percolation $I_t$ est divisée par le coefficient de répartition $X_7$ : une fraction $X_7 \cdot I_t$ alimente le réservoir de routage de zone inférieure $L$, tandis que la fraction complémentaire $(1 - X_7) \cdot I_t$ va directement à $R$.
Si $L$ déborde son plafond $XF_2 = 30$ mm, le débordement $I_l$ est dévié directement vers $R$.

**Étape 6 : évaporation résiduelle depuis $L$ et correction ascendante**.
L'ETP résiduelle $E''$ évapore $L$ au taux $E_l = E'' \cdot L / (XF_1 + XF_2)$, proportionnel au taux de remplissage de $L$ rapporté à la capacité combinée interception + routage.
Si cela amène $L$ sous zéro, le modèle puise une compensation $I_r$ dans l'« espace libre » de $R$ au-dessus de $X_2 - XF_2$ — c'est la correction de bilan de masse qui maintient le contenu des réservoirs non négatif tout en préservant le bilan hydrique.

**Étape 7 : débit de base et amortissement par percolation profonde**.
Le réservoir d'eau libre $R$ se vide linéairement selon $Q_r = R / X_3$, puis le débit de base est encore amorti par le coefficient de percolation profonde $X_8 \geq 1$ : $Q_r \leftarrow Q_r / X_8$.
Cet amortissement en deux temps permet au calage de découpler la constante de temps brute du débit de base ($X_3$) de la part du débit de base qui atteint réellement l'exutoire — le reste est traité comme une perte par percolation profonde hors du bassin versant.

**Étape 8 : routage direct et débit total**.
Le réservoir de routage direct $M$ reçoit $Q_{t0}$ de l'étape 4 et se vide linéairement avec la constante de temps $X_1$, produisant $Q_m = M / X_1$.
Les trois composantes $Q_r + Q_m + Q_{t1}$ sont sommées et poussées dans un registre de délai fractionnaire de longueur $\lceil X_9 \rceil + 1$, et le premier élément du registre est retourné comme débit simulé, borné à zéro.

## Paramètres

Le modèle SACRAMENTO possède neuf paramètres à caler.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ | Capacité du réservoir de routage direct (équivalent uzk) | 1–20 | jours | Temps de résidence du réservoir rapide de ruissellement direct $M$. De petites valeurs donnent des pointes de crue vives; de grandes valeurs étalent la pointe sur plusieurs jours. |
| $X_2$ | Capacité d'eau libre de zone supérieure ($uzfwm$) | 30–1000 | mm | Capacité de stockage du réservoir de débit de base rapide $R$. Contrôle aussi la rétroaction de remplissage qui étrangle la percolation depuis $T$ une fois $R$ proche de la saturation. |
| $X_3$ | Constante de vidange de zone inférieure | 10–500 | jours | Constante de temps linéaire du réservoir d'eau libre $R$. Des valeurs élevées produisent des courbes de récession plus longues. |
| $X_4$ | Capacité d'eau de tension de zone supérieure ($uztwm$) | 10–500 | mm | Capacité de stockage du réservoir d'humidité du sol $T$. Au-dessus de $X_4$, le réservoir de tension déborde dans le réservoir de routage direct $M$. |
| $X_5$ | Taux de percolation maximal | 0.01–20 | mm/jour | Facteur d'échelle de la percolation de $T$ vers $R$. Des valeurs élevées déplacent plus d'eau vers la voie rapide du débit de base à chaque pas de temps. |
| $X_6$ | Constante de vidange de l'écoulement hypodermique | 1–100 | jours | Constante de temps de la voie hypodermique $Q_{t1} = T / X_6$. De petites valeurs donnent une réponse de subsurface rapide; de grandes valeurs suppriment l'écoulement hypodermique. |
| $X_7$ | Coefficient de répartition de zone supérieure ($pfree$) | 0.01–0.99 | - | Fraction de la percolation $I_t$ routée vers le réservoir de zone inférieure $L$ (le reste va à $R$). Contrôle le partage entre la dynamique lente de zone inférieure et le débit de base rapide d'eau libre. |
| $X_8$ | Coefficient de percolation profonde | 1–50 | - | Facteur d'amortissement appliqué à $Q_r$ pour représenter la perte d'eau souterraine sous le bassin versant. Des valeurs élevées réduisent le débit de base atteignant l'exutoire sans en changer la forme. |
| $X_9$ | Délai | 0.5–10 | jours | Délai fractionnaire appliqué à la sortie sommée à travers un registre à décalage. Gère les temps de parcours non entiers sans interpolation. |

**Comprendre les paramètres :**

- **$X_4$ et $X_2$ ensemble** fixent le budget en eau du sol du bassin versant : $X_4$ est la capacité d'eau de tension (la quantité de pluie nécessaire pour saturer le sol) et $X_2$ est la capacité d'eau libre (la quantité d'eau que le réservoir de débit de base rapide peut retenir).
Les valeurs typiques dans le jeu calé de Perrin placent $X_4$ dans la plage 100–300 mm et $X_2$ autour de 200–500 mm.
- **$X_5$ et $X_7$** contrôlent la voie de percolation.
$X_5$ fixe le taux maximal auquel $T$ peut alimenter $R$, tandis que $X_7$ décide quelle part est d'abord déviée par le réservoir de zone inférieure $L$.
Un $X_7$ élevé rend le modèle plus sensible à l'évaporation résiduelle (via la correction de bilan de masse), ce qui peut être utile sur des bassins à fort contrôle par la végétation.
- **$X_3$, $X_6$ et $X_1$** sont les trois constantes de temps qui façonnent la récession de l'hydrogramme.
$X_6$ contrôle la queue de l'écoulement hypodermique (heures à jours), $X_1$ contrôle la décroissance du ruissellement direct (jours), et $X_3$ contrôle la décroissance du débit de base (semaines à mois).
Les trois ensemble permettent au modèle d'ajuster des hydrogrammes aux équilibres rapide/lent très différents.
- **$X_8$** est le seul paramètre qui rompt intentionnellement le bilan de masse.
Poser $X_8 = 1$ signifie que tout le débit de base atteint l'exutoire; $X_8 = 50$ signifie que 98 % en est perdu par percolation profonde.
Ce paramètre est pédagogiquement intéressant parce qu'il permet aux étudiants de voir l'impact des pertes souterraines profondes sur le bilan hydrique à long terme.
- **$X_9$** est un paramètre de translation pure : il n'affecte pas la forme de l'hydrogramme, seulement son moment.
Il devrait être calé en dernier, une fois que les autres paramètres ont produit un hydrogramme de la bonne forme.

**Pourquoi les capacités d'interception et de zone inférieure sont fixées** : la « version retenue » de Perrin fige $XF_1 = 3$ mm (interception) et $XF_2 = 30$ mm (routage de zone inférieure).
C'étaient à l'origine des paramètres calés dans le modèle complet de Burnash, mais ils se sont avérés faiblement identifiables, alors Perrin les a fixés à des valeurs physiques raisonnables pour réduire l'espace de recherche et éliminer l'équifinalité associée aux réservoirs de petite capacité.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs (du fichier `ini_HydroMod14.m` de HOOPLA, correspondant à l'état de bassin modérément humide de la fiche de Perrin) :

$$S_0 = 3, \quad T_0 = 10, \quad R_0 = 100, \quad L_0 = 0, \quad M_0 = 0$$

Capacités fixes :

$$XF_1 = 3 \ \text{mm} \ \text{(interception)}, \quad XF_2 = 30 \ \text{mm} \ \text{(lower-zone routing)}$$

Le tableau de routage à délai fractionnaire $\{DL_k\}$ de longueur $n = \lceil X_9 \rceil + 1$ est construit de sorte que seuls les deux derniers éléments soient non nuls :

$$DL_{n-2} = \frac{1}{X_9 - n + 3}, \quad DL_{n-1} = 1 - DL_{n-2}$$

Cette construction représente un délai non entier de $X_9$ pas de temps comme un gabarit à deux éléments à la fin d'un tableau autrement vide.

### Phase de surface (réservoir d'interception)

$$S \leftarrow S + P$$

$$E_s = \min(E, S), \quad S \leftarrow S - E_s, \quad E' = E - E_s$$

$$I_s = \max(0, S - XF_1), \quad S \leftarrow S - I_s$$

### Réservoir de tension de zone supérieure ($T$)

Le débordement $I_s$ entre dans $T$ :

$$T \leftarrow T + I_s$$

Percolation vers le réservoir d'eau libre de zone supérieure $R$, avec amortissement par rétroaction de remplissage :

$$I_t = \mathrm{clamp}\left(X_5 \cdot \left(1 - \frac{R}{X_2}\right) \cdot \frac{T}{X_4}, \ 0, \ T\right)$$

$$T \leftarrow T - I_t$$

Sortie hypodermique (écoulement hypodermique) :

$$Q_{t1} = \frac{T}{X_6}, \quad T \leftarrow T - Q_{t1}$$

Évaporation (limitée par l'eau via le taux de remplissage) :

$$E_t = \min\left(E' \cdot \min\left(1, \frac{T}{X_4}\right), \ T\right), \quad T \leftarrow T - E_t, \quad E'' = E' - E_t$$

Débordement de saturation vers le réservoir de routage direct $M$ :

$$Q_{t0} = \max(0, \ T - X_4), \quad T \leftarrow T - Q_{t0}$$

### Réservoir de routage de zone inférieure ($L$) et correction ascendante

La percolation $I_t$ est divisée entre $L$ (fraction $X_7$) et $R$ (fraction $1 - X_7$) :

$$L \leftarrow L + X_7 \cdot I_t$$

$$I_l = \max(0, \ L - XF_2), \quad L \leftarrow L - I_l$$

$$R \leftarrow R + (1 - X_7) \cdot I_t + I_l$$

L'ETP résiduelle évapore $L$ proportionnellement à son taux de remplissage rapporté à la capacité combinée interception + routage :

$$E_l = E'' \cdot \frac{L}{XF_1 + XF_2}, \quad L \leftarrow L - E_l$$

Si $L$ se retrouve alors sous zéro, le déficit est puisé vers le haut dans l'espace libre de $R$ :

$$\text{if } L < 0: \quad I_r = \min\left(-L, \ \max\left(0, \ R - (X_2 - XF_2)\right)\right)$$

$$L \leftarrow \max(0, \ L + I_r), \quad R \leftarrow R - I_r$$

### Réservoir d'eau libre de zone supérieure ($R$, débit de base)

$$Q_r = \frac{R}{X_3}, \quad R \leftarrow R - Q_r$$

Le débit de base atteignant l'exutoire est amorti par la percolation profonde :

$$Q_r \leftarrow \frac{Q_r}{X_8}$$

### Réservoir de routage direct ($M$)

$$M \leftarrow M + Q_{t0}, \quad Q_m = \frac{M}{X_1}, \quad M \leftarrow M - Q_m$$

### Débit total et délai fractionnaire

Les trois sorties sont sommées et poussées dans le registre de délai en décalage-addition $\{HY_k\}$ de même longueur que $\{DL_k\}$ :

$$Q = Q_r + Q_m + Q_{t1}$$

$$HY_k \leftarrow HY_{k+1} + DL_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$HY_{n-1} \leftarrow DL_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0, \ HY_0)$$

Le premier élément du registre est retourné comme débit simulé pour le pas de temps courant; le registre avance ensuite d'une position, prêt pour le pas suivant.

## Références

Burnash, R. J. C., Ferral, R. L., & McGuire, R. A. (1973).
*A generalized streamflow simulation system – Conceptual modelling for digital computers*.
US Department of Commerce, National Weather Service, and State of California, Department of Water Resources.

Burnash, R. J. C. (1995).
The NWS River Forecast System — catchment modelling.
In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology*, Chapter 10, pp. 311–366.
Water Resources Publications.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°27 (Sacramento), pp. 425–429.

Sorooshian, S., Duan, Q., & Gupta, V. K. (1993).
Calibration of rainfall-runoff models: Application of global optimization to the Sacramento soil moisture accounting model.
*Water Resources Research*, 29(4), 1185–1194.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
