# Modèle GR4J

## Aperçu

GR4J (Génie Rural à 4 paramètres Journalier) est un modèle pluie-débit global journalier développé par l'IRSTEA (anciennement Cemagref) en France.
Son nom reflète à la fois ses origines dans la gestion de l'eau agricole française et sa conception parcimonieuse.

GR4J est devenu l'un des modèles hydrologiques conceptuels les plus utilisés au monde, présent dans des centaines de publications scientifiques et de systèmes de prévision opérationnels.
Sa popularité tient à un équilibre soigné : il est assez simple pour être calé de façon fiable avec peu de données, tout en étant assez complet pour capturer la dynamique essentielle de l'hydrologie d'un bassin versant.
Avec seulement quatre paramètres, GR4J évite les problèmes de surparamétrisation qui affligent les modèles plus complexes, tout en atteignant de solides performances prédictives dans des conditions climatiques et physiographiques variées.

Le modèle représente un bassin versant par deux réservoirs interconnectés : un réservoir de production qui assure le suivi de l'humidité du sol et un réservoir de routage qui contrôle la génération du débit de base.
L'eau traverse le système par deux voies parallèles aux temps de réponse différents, ce qui permet au modèle de reproduire à la fois la réponse rapide aux événements pluvieux et la récession plus lente du débit de base.

## Concepts clés

- **Modèle global** : traite le bassin versant entier comme une seule unité, sans discrétisation spatiale.
Tous les processus sont moyennés sur la superficie du bassin.

- **Approche conceptuelle** : utilise des réservoirs et des fonctions de transfert pour représenter les processus physiques plutôt que de résoudre directement la physique sous-jacente.
On sacrifie un peu de réalisme physique au profit de l'applicabilité pratique.

- **Réservoir de production** : le réservoir supérieur, qui répartit l'eau entrante entre stockage, évaporation et percolation.
On peut le voir comme la capacité du sol à absorber et retenir l'eau.

- **Réservoir de routage** : le réservoir inférieur, qui génère le débit de base et reçoit l'eau du réservoir de production.
Il représente la composante souterraine, plus lente, du débit.

- **Hydrogrammes unitaires** : fonctions mathématiques qui répartissent l'écoulement dans le temps, représentant le délai entre l'entrée de l'eau dans le système et son arrivée à l'exutoire.
GR4J utilise deux hydrogrammes unitaires de longueurs différentes.

- **Échanges souterrains** : un terme permettant à l'eau d'entrer ou de sortir du système modélisé, représentant les interactions avec des aquifères profonds ou des bassins voisins qui ne peuvent pas être mesurées directement.

## Fonctionnement

GR4J fonctionne au pas de temps journalier et transforme précipitations et évapotranspiration potentielle en débit.
La structure du modèle peut se comprendre comme une suite de transformations de l'eau :

**Étape 1 : entrées nettes**. Le modèle détermine d'abord si la journée est humide (les précipitations dépassent l'ETP) ou sèche (l'ETP dépasse les précipitations).
Cela détermine si l'eau entre dans le réservoir de production ou en sort.

**Étape 2 : dynamique du réservoir de production**. En période humide, les précipitations remplissent le réservoir de production selon une courbe de saturation — un réservoir presque vide accepte l'eau facilement, tandis qu'un réservoir presque plein en accepte peu.
En période sèche, l'évaporation vide le réservoir selon une relation non linéaire similaire.
L'eau qui ne peut pas entrer dans le réservoir devient disponible pour le routage.

**Étape 3 : percolation**. Une fraction de l'eau du réservoir de production percole vers le bas quelles que soient les conditions.
Cette percolation croît de façon non linéaire à mesure que le réservoir se remplit, représentant un drainage gravitaire.

**Étape 4 : répartition de l'écoulement**. L'eau disponible pour le routage (excès de surface plus percolation) se divise entre deux voies : 90 % suivent une route plus lente à travers le réservoir de routage, tandis que 10 % empruntent une voie directe plus rapide.

**Étape 5 : convolution par les hydrogrammes unitaires**. L'eau de chaque voie est retardée par un hydrogramme unitaire qui étale la réponse sur plusieurs jours.
La voie lente utilise un hydrogramme plus long (jusqu'à $X_4$ jours), tandis que la voie rapide en utilise un plus court (jusqu'à $2X_4$ jours, mais au pic plus précoce).

**Étape 6 : réservoir de routage et échanges**. L'eau de la voie lente entre dans le réservoir de routage, qui génère un débit sortant selon une loi de puissance.
Simultanément, les échanges souterrains ajoutent ou retirent de l'eau du système.

**Étape 7 : débit total**. Le modèle additionne le débit sortant du réservoir de routage et celui de la voie directe pour produire le débit total.

## Paramètres

GR4J possède exactement quatre paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Capacité du réservoir de production | 10–1500 | mm | Stockage maximal d'eau dans le sol. Des valeurs élevées indiquent un sol plus profond ou une plus grande capacité de rétention. |
| $X_2$ | Coefficient d'échanges souterrains | -5 à 3 | mm/jour | Échanges d'eau avec les aquifères profonds. Des valeurs négatives indiquent des pertes; des valeurs positives, des gains. |
| $X_3$ | Capacité du réservoir de routage | 10–400 | mm | Taille du réservoir de débit de base. Contrôle le volume de stockage à relâchement lent. |
| $X_4$ | Temps de base de l'hydrogramme unitaire | 0.8–10 | jours | Temps de réponse caractéristique. Contrôle la vitesse de réaction du bassin à la pluie. |

**Conseils pratiques sur les paramètres :**

- **$X_1$** se situe généralement entre 100 et 500 mm pour la plupart des bassins.
Des valeurs très élevées (>1000 mm) peuvent indiquer des problèmes d'identifiabilité du modèle.
- **$X_2$** est souvent négatif (les pertes vers les aquifères profonds sont courantes).
Des valeurs proches de zéro suggèrent un bilan hydrique fermé.
- **$X_3$** interagit avec $X_4$ dans le contrôle de la récession.
Un $X_3$ plus grand produit un débit de base plus soutenu.
- **$X_4$** reflète la taille et la pente du bassin.
Les petits bassins pentus ont un $X_4$ faible; les grands bassins plats ont des valeurs plus élevées.

## Formulation mathématique

### Initialisation

Les réservoirs sont initialisés à demi-capacité :

$$S_0 = \frac{X_1}{2}, \quad R_0 = \frac{X_3}{2}$$

où $S$ est le niveau du réservoir de production et $R$ le niveau du réservoir de routage.

### Précipitations et évapotranspiration nettes

Étant donné les précipitations $P$ et l'évapotranspiration potentielle $E$ :

$$P_n = \max(P - E, 0)$$

$$E_n = \max(E - P, 0)$$

où $P_n$ est la précipitation nette (quand $P > E$) et $E_n$ l'évapotranspiration nette (quand $E > P$).

### Réservoir de production

**Remplissage (conditions humides, $P_n > 0$) :**

La fraction de la précipitation nette entrant dans le réservoir suit une fonction de saturation :

$$P_s = \frac{X_1 \left(1 - \left(\frac{S}{X_1}\right)^2\right) \tanh\left(\frac{P_n}{X_1}\right)}{1 + \frac{S}{X_1} \tanh\left(\frac{P_n}{X_1}\right)}$$

Le réservoir est ensuite mis à jour : $S \leftarrow S + P_s$

**Vidange (conditions sèches, $E_n > 0$) :**

Évaporation réelle depuis le réservoir :

$$E_s = \frac{S \left(2 - \frac{S}{X_1}\right) \tanh\left(\frac{E_n}{X_1}\right)}{1 + \left(1 - \frac{S}{X_1}\right) \tanh\left(\frac{E_n}{X_1}\right)}$$

Le réservoir est ensuite mis à jour : $S \leftarrow S - E_s$

**Percolation :**

L'eau percole du réservoir de production quelles que soient les conditions :

$$\text{Perc} = S \left(1 - \left(1 + \left(\frac{4S}{9X_1}\right)^4\right)^{-0.25}\right)$$

Le réservoir est mis à jour : $S \leftarrow S - \text{Perc}$

**Précipitation de routage :**

L'eau disponible pour le routage combine l'excès de surface et la percolation :

$$P_r = P_n - P_s + \text{Perc}$$

(En conditions sèches, $P_n = P_s = 0$, donc $P_r = \text{Perc}$)

### Hydrogrammes unitaires

GR4J utilise deux hydrogrammes unitaires pour répartir l'écoulement dans le temps.
Les deux reposent sur des courbes en S (distributions cumulées) :

**UH1 (pour 90 % de l'écoulement, voie lente) :**

$$SH_1(t) = \begin{cases}
0 & t = 0 \\
\left(\frac{t}{X_4}\right)^{2.5} & 0 < t < X_4 \\
1 & t \geq X_4
\end{cases}$$

**UH2 (pour 10 % de l'écoulement, voie rapide) :**

$$SH_2(t) = \begin{cases}
0 & t = 0 \\
\frac{1}{2}\left(\frac{t}{X_4}\right)^{2.5} & 0 < t < X_4 \\
1 - \frac{1}{2}\left(2 - \frac{t}{X_4}\right)^{2.5} & X_4 \leq t < 2X_4 \\
1 & t \geq 2X_4
\end{cases}$$

Les ordonnées des hydrogrammes unitaires sont calculées comme :

$$UH_1(j) = SH_1(j) - SH_1(j-1), \quad j = 1, 2, \ldots, \lceil X_4 \rceil$$

$$UH_2(j) = SH_2(j) - SH_2(j-1), \quad j = 1, 2, \ldots, \lceil 2X_4 \rceil$$

Les écoulements routés sont calculés par convolution :

$$Q_9(t) = 0.9 \sum_{j=1}^{\lceil X_4 \rceil} UH_1(j) \cdot P_r(t-j+1)$$

$$Q_1(t) = 0.1 \sum_{j=1}^{\lceil 2X_4 \rceil} UH_2(j) \cdot P_r(t-j+1)$$

### Échanges souterrains

Le terme d'échange dépend du niveau du réservoir de routage :

$$F = X_2 \left(\frac{R}{X_3}\right)^{3.5}$$

Un $X_2$ positif ajoute de l'eau au système; un $X_2$ négatif en retire.

### Réservoir de routage

Le réservoir de routage reçoit l'eau de UH1 et échange avec le souterrain :

$$R \leftarrow \max(R + Q_9 + F, 0)$$

Le débit sortant du réservoir de routage suit une loi de puissance :

$$Q_r = R \left(1 - \left(1 + \left(\frac{R}{X_3}\right)^4\right)^{-0.25}\right)$$

Le réservoir est ensuite vidé : $R \leftarrow R - Q_r$

### Écoulement direct

La voie directe reçoit aussi l'échange souterrain :

$$Q_d = \max(Q_1 + F, 0)$$

### Débit total

$$Q = Q_r + Q_d$$

## Références

Perrin, C., Michel, C., & Andréassian, V. (2003).
Improvement of a parsimonious model for streamflow simulation. *Journal of Hydrology*, 279(1-4), 275-289. [https://doi.org/10.1016/S0022-1694(03)00225-7](https://doi.org/10.1016/S0022-1694(03)00225-7)
