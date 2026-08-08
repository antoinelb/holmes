# Modèle IHACRES

## Aperçu

IHACRES (Identification of unit Hydrographs And Component flows from Rainfall, Evaporation and Streamflow data) est un modèle pluie-débit global journalier à sept paramètres développé conjointement à l'Institute of Hydrology (Wallingford, Royaume-Uni) et à l'Australian National University au début des années 1990.
La formulation originale apparaît dans Jakeman et al. (1990) et la version PC opérationnelle est documentée dans Littlewood et al. (1997).

IHACRES occupe une niche distinctive parmi les modèles globaux : il sépare explicitement un **module de pertes non linéaire** (qui convertit la pluie brute en « pluie efficace ») d'un **module de routage linéaire par hydrogramme unitaire** (qui transforme la pluie efficace en débit).
Le module de pertes est construit autour d'un unique **indice d'humidité du bassin versant** sans dimension $S$ qui décroît exponentiellement entre les événements pluvieux à un taux modulé par l'évapotranspiration potentielle.
Le module de routage place deux réservoirs linéaires parallèles en série avec un délai pur — un réservoir rapide et un réservoir lent partageant un couplage multiplicatif — ce qui le rend équivalent à une réponse impulsionnelle à deux coefficients.

L'implémentation HOLMES suit la « version retenue » du modèle selon Perrin (2000), qui utilise l'ETP à la place de la température dans le terme de taux d'assèchement.
Les étudiants choisissent souvent IHACRES comme contraste pédagogique aux modèles à seaux de sol (GR4J, GARDENIA, BUCKET) : il montre qu'on peut produire un débit réaliste sans « capacité de réservoir » explicite, en s'appuyant plutôt sur un *indice* d'humidité qui module un système par ailleurs linéaire.

## Concepts clés

- **Indice d'humidité du bassin versant ($S$)** : une variable d'état sans dimension qui suit le degré d'humidité du bassin versant.
Contrairement à un seau de sol, $S$ n'a pas de borne supérieure — il croît en période humide et décroît en période sèche à un taux fixé par l'ETP.
- **Pluie efficace ($P_r$)** : la fraction de la pluie entrante qui contribue réellement au débit, calculée comme le produit de l'indice d'humidité et de la hauteur de pluie.
Quand $S$ est petit (sec), la majeure partie de la pluie est perdue; quand $S$ est grand (humide), la majeure partie de la pluie devient du ruissellement.
- **Constante d'assèchement modulée par l'ETP ($\tau_w$)** : la constante de temps de la récession de l'indice d'humidité.
Ce n'est *pas* un paramètre fixe — elle se contracte quand l'ETP est élevée (assèchement plus rapide) et se dilate quand l'ETP est faible (assèchement plus lent), reproduisant l'asymétrie saisonnière entre les récessions d'été et d'hiver.
- **Forçage de bilan de masse ($1/C$)** : un facteur d'échelle calé ($X_1$) qui convertit la pluie brute en incrément de l'indice d'humidité.
Il absorbe les différences systématiques entre les précipitations au pluviomètre à long terme et le ruissellement observé, de sorte que le débit total calé corresponde au débit total observé.
- **Routage parallèle rapide/lent** : la pluie efficace est répartie entre deux réservoirs linéaires par une fraction $X_2$.
Le réservoir rapide se vide avec la constante de temps $X_3$ (réponse de pointe); le réservoir lent se vide avec la constante de temps $X_3 \cdot X_4$ (débit de base).
Le $X_3$ partagé est un couplage structurel — caler l'un affecte les deux.
- **Délai pur ($X_5$)** : une ligne de délai fractionnaire à l'exutoire du bassin versant représentant le temps de parcours en chenal, distribuée entre les deux cellules les plus proches de $\lceil X_5 \rceil$.

## Fonctionnement

Le modèle IHACRES traite les précipitations et l'ETP selon les étapes suivantes :

**Étape 1 : calcul de l'exposant du taux d'assèchement**.
Au pas de temps $k$, le modèle calcule d'abord un exposant d'assèchement $E_l = \max(0, X_7 - E_k / X_6)$, où $X_7$ est la constante d'assèchement de base et $X_6$ le facteur de modulation par l'ETP.
Quand l'ETP est élevée, $E_k / X_6$ devient grand, $E_l$ tend vers zéro et l'indice d'humidité décroît lentement (ou pas du tout dans la limite d'assèchement saturé).
Quand l'ETP est faible, $E_l$ reste proche de $X_7$ et la récession est rapide.

**Étape 2 : mise à jour de l'indice d'humidité du bassin versant**.
L'indice d'humidité obéit à une équation de filtre IIR : la valeur précédente est multipliée par un coefficient de décroissance $1 - 1/\exp(E_l) \in [0, 1)$ et incrémentée de $P_k / X_1$.
Le facteur de bilan de masse $X_1$ convertit la hauteur de pluie en un incrément sans dimension qui maintient la cohérence entre les totaux simulés et observés à long terme.

**Étape 3 : calcul de la pluie efficace**.
La pluie efficace est le produit de l'indice d'humidité moyen sur le pas de temps et de la hauteur de pluie : $P_r = \frac{1}{2}(S_{k-1} + S_k) \cdot P_k$.
La règle du trapèze au point milieu reflète le fait que le bassin versant s'humidifie *pendant* le pas de temps, de sorte que l'humidité contributive est la moyenne des valeurs de début et de fin.

**Étape 4 : répartition entre les voies rapide et lente**.
Une fraction $X_2$ de la pluie efficace entre dans le réservoir linéaire rapide $R$; la fraction complémentaire $1 - X_2$ entre dans le réservoir linéaire lent $T$.
Cette répartition est purement empirique — elle n'a aucune dérivation issue de la physique du sol.

**Étape 5 : vidange des réservoirs de routage**.
Le réservoir rapide libère $Q_r = R / X_3$ à chaque pas; le réservoir lent libère $Q_t = T / (X_3 \cdot X_4)$.
Le $X_3$ partagé couple les deux récessions de sorte que le calage ne peut pas les rendre entièrement indépendantes.
Le réservoir lent hérite d'une mémoire plus longue ($X_4 \geq 1$ impose lent $\geq$ rapide).

**Étape 6 : application du délai pur**.
Le débit sortant combiné $Q_r + Q_t$ entre dans une ligne de délai fractionnaire de longueur $\lceil X_5 \rceil + 1$.
Deux poids non nuls distribuent la nouvelle impulsion sur les deux dernières cellules, produisant une interpolation lisse entre délais entiers.

**Étape 7 : lecture du débit simulé**.
Le débit à l'exutoire du bassin versant est la cellule de tête du tableau de délai, bornée à zéro pour garantir une sortie non négative.

## Paramètres

Le modèle IHACRES possède sept paramètres à caler.
Notez que la borne inférieure de $X_3$ est fixée à 1 jour plutôt qu'aux valeurs plus permissives trouvées dans la littérature originale.
Il s'agit d'une contrainte de *stabilité numérique* : le schéma de routage d'Euler explicite $Q = R / X_3$ suivi de $R \leftarrow R - Q$ devient instable quand $X_3 < 1$, puisque le coefficient de décroissance par pas $|1 - 1/X_3|$ dépasse 1 et le réservoir oscille avec une amplitude croissante.
Un plancher de 1 jour est aussi physiquement raisonnable pour un modèle fonctionnant avec un forçage journalier.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ ($1/C$) | Paramètre de forçage du bilan de masse | 1–1000 | – | Inverse de la constante de forçage calée. De petites valeurs amplifient la pluie dans l'indice d'humidité, produisant plus de ruissellement total. Utilisé pour corriger les erreurs de bilan hydrique à long terme. |
| $X_2$ ($\alpha$) | Fraction d'écoulement rapide de la pluie efficace | 0.01–0.99 | – | Fraction de la pluie efficace routée vers le réservoir rapide. Des valeurs élevées produisent des hydrogrammes plus vifs; des valeurs faibles accentuent le débit de base. |
| $X_3$ | Constante de temps du réservoir de routage rapide | 1–100 | jours | Temps de résidence linéaire du réservoir rapide. De petites valeurs produisent des pointes plus nettes; les valeurs sous 1 sont exclues pour la stabilité numérique. |
| $X_4$ | Multiplicateur du routage lent | 1–1000 | – | Couplage multiplicatif : le réservoir lent a la constante de temps $X_3 \cdot X_4$. Contraint à $\geq 1$ pour imposer « lent $\geq$ rapide ». |
| $X_5$ | Délai pur | 0.5–5.0 | jours | Temps de parcours en chenal du bassin versant à l'exutoire. Une valeur fractionnaire distribue l'impulsion sur deux cellules temporelles adjacentes. |
| $X_6$ ($f$) | Facteur de modulation par l'ETP | 0.1–10 | – | Sensibilité de la constante de temps d'assèchement à l'ETP. De grandes valeurs affaiblissent le couplage avec l'ETP; de petites valeurs rendent la récession fortement saisonnière. |
| $X_7$ ($T_w$) | Constante caractéristique d'assèchement du bassin versant | 0.1–10 | – | Exposant d'assèchement de base à ETP nulle. De grandes valeurs signifient que le bassin versant retient l'humidité plus longtemps. L'échelle de temps naturelle de récession (en jours) est d'environ $1 / (1 - 1/\exp(X_7))$. |

**Comprendre les paramètres :**

- **$X_1$ seul** met à l'échelle tout le bilan de masse.
Le calage le pousse vers la valeur qui fait correspondre les totaux de ruissellement simulés et observés à long terme — sa valeur ne porte aucun sens physique au-delà de « ce que les données exigent ».
Un diagnostic courant pendant le calage manuel est de tracer le ruissellement cumulé simulé contre l'observé : si la pente est fausse, $X_1$ est faux.

- **$X_2$, $X_3$ et $X_4$ ensemble** définissent le routage linéaire.
Comme $X_3$ est partagé entre les récessions rapide ($X_3$) et lente ($X_3 \cdot X_4$), on ne peut pas les caler de façon entièrement indépendante — déplacer $X_3$ remet les deux à l'échelle.
Démarche pratique : fixer $X_3$ à partir d'une analyse de récession sur le débit observé, puis caler $X_2$ et $X_4$ à partir du rapport pointe/débit de base.

- **$X_5$** est un paramètre purement temporel et n'importe que si le bassin versant est assez grand pour introduire un décalage perceptible entre la pointe de pluie et la pointe de débit.
Pour les petits bassins versants à résolution journalière, $X_5 \approx 1$ jour suffit généralement.

- **$X_6$ et $X_7$ ensemble** contrôlent la dynamique de l'indice d'humidité.
La constante de temps d'assèchement est d'environ $\tau_w \approx \exp(X_7 - E/X_6)$ jours quand l'argument est positif.
Pour les bassins versants tempérés avec une ETP estivale d'environ 4 mm/jour, un $X_6$ dans la plage 1–5 et un $X_7$ dans la plage 1–5 donnent typiquement l'asymétrie saisonnière de récession observée dans les données.
Fixer $X_7$ très petit force l'indice d'humidité à décroître agressivement même en hiver, ce qui est rarement réaliste.

## Formulation mathématique

### Initialisation

Les états des réservoirs sont initialisés aux valeurs par défaut HM8 de HOOPLA, indépendamment des valeurs des paramètres :

$$S_0 = 0.5, \quad R_0 = 5, \quad T_0 = 50$$

Le vecteur de délai pur de longueur $n = \lceil X_5 \rceil + 1$ est construit une fois avec un historique entièrement nul et deux poids non nuls aux cellules de queue :

$$d_{n-2} = \frac{1}{X_5 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}, \quad d_i = 0 \text{ for } i < n-2$$

### Exposant d'assèchement

À chaque pas de temps, l'exposant d'assèchement est calculé à partir de l'ETP courante :

$$E_{l,k} = \max\left(0, \; X_7 - \frac{E_k}{X_6}\right)$$

La borne $\max(\cdot, 0)$ implémente la « limite d'assèchement saturé » : peu importe la hauteur de l'ETP, le taux d'assèchement ne peut pas devenir négatif (c.-à-d. que le bassin versant ne peut pas s'anti-assécher).

### Indice d'humidité du bassin versant

L'indice d'humidité se met à jour via un filtre IIR linéaire avec la pluie en entrée :

$$S_k \leftarrow S_{k-1} + \frac{P_k}{X_1} - \frac{S_{k-1}}{\exp(E_{l,k})}$$

De façon équivalente, $S_k = \alpha_k \cdot S_{k-1} + P_k / X_1$ avec $\alpha_k = 1 - 1/\exp(E_{l,k}) \in [0, 1]$.
Le filtre est strictement stable tant que $E_{l,k} > 0$; les bornes imposées sur $X_3$, $X_6$ et $X_7$ maintiennent la stabilité numérique des réservoirs de routage dans le rare cas où $E_{l,k}$ touche zéro.

### Pluie efficace

La pluie efficace est le point milieu de la règle du trapèze de l'indice d'humidité multiplié par la hauteur de pluie :

$$P_{r,k} = \frac{1}{2} \left(S_{k-1} + S_k\right) \cdot P_k$$

Quand $S$ est proche de zéro (bassin versant sec), presque toute la pluie est perdue.
Quand $S$ est grand (bassin versant saturé), presque toute la pluie atteint le module de routage.

### Réservoir de routage rapide

Le réservoir rapide reçoit une fraction $X_2$ de la pluie efficace et se draine linéairement avec la constante de temps $X_3$ :

$$R_k \leftarrow R_{k-1} + X_2 \cdot P_{r,k}$$

$$Q_{r,k} = \frac{R_k}{X_3}$$

$$R_k \leftarrow R_k - Q_{r,k}$$

### Réservoir de routage lent

Le réservoir lent reçoit la fraction complémentaire $1 - X_2$ et se draine avec la constante de temps plus longue $X_3 \cdot X_4$ :

$$T_k \leftarrow T_{k-1} + (1 - X_2) \cdot P_{r,k}$$

$$Q_{t,k} = \frac{T_k}{X_3 \cdot X_4}$$

$$T_k \leftarrow T_k - Q_{t,k}$$

### Routage du délai et débit total

Le débit sortant combiné rapide plus lent $Q_{r,k} + Q_{t,k}$ est convolué avec le vecteur de délai statique en décalant le tampon en chenal d'une cellule vers l'avant et en déposant la nouvelle impulsion aux cellules de queue :

$$h_i \leftarrow h_{i+1} + d_i \cdot (Q_{r,k} + Q_{t,k}) \quad \text{for } i = 0, \ldots, n-2$$

$$h_{n-1} \leftarrow d_{n-1} \cdot (Q_{r,k} + Q_{t,k})$$

Le débit simulé à l'exutoire du bassin versant est la cellule de tête, bornée à zéro :

$$Q_{\text{sim},k} = \max(h_0, 0)$$

## Références

Jakeman, A. J., Littlewood, I. G., & Whitehead, P. G. (1990).
Computation of the instantaneous unit hydrograph and identifiable component flows with application to two small upland catchments.
*Journal of Hydrology*, 117(1–4), 275–300.

Littlewood, I. G., Down, K., Parker, J. R., & Post, D. A. (1997).
*The PC version of IHACRES for catchment-scale rainfall-streamflow modelling. Version 1.0. User Guide*.
Institute of Hydrology, Wallingford, UK, 89 pp.

Jakeman, A. J., & Hornberger, G. M. (1993).
How much complexity is warranted in a rainfall-runoff model?
*Water Resources Research*, 29(8), 2637–2649.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis).
INPG, Grenoble. Annexe 1, fiche analytique n°17.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
