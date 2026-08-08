# Modèle GARDENIA

## Aperçu

GARDENIA est un modèle pluie-débit global journalier à six paramètres développé au Bureau de Recherches Géologiques et Minières (BRGM) à Orléans, en France, par Thiery (1982).
Il a été conçu à l'origine non pas comme un modèle de débit mais comme un modèle **pluie → niveau piézométrique** pour des applications hydrogéologiques : la version originale calait ses paramètres sur des niveaux d'eau souterraine observés plutôt que sur des débits, et GARDENIA est encore largement utilisé aujourd'hui dans l'hydrogéologie opérationnelle française pour le suivi des aquifères et la prévision des sécheresses.

La variante implémentée dans HOLMES est la version **GARD** à six paramètres décrite dans l'annexe 1 de Perrin (2000).
Elle utilise trois réservoirs en série : un **réservoir de surface** qui capture la couche superficielle d'interception/ruissellement, un **réservoir de sol** qui produit le débit par un débit sortant quadratique non linéaire tout en percolant simultanément l'eau vers le bas, et un **réservoir d'eau souterraine** qui se draine linéairement et représente la composante d'écoulement profond / débit de base.
Un court délai pur est appliqué à l'exutoire pour tenir compte du temps de parcours en chenal.

Ce qui distingue GARDENIA des autres modèles à six paramètres de HOLMES est la **vidange quadratique du sol** $Q_r = R^2 / (R + X_2 X_3)$.
Il s'agit d'une loi de réservoir non linéaire qui produit des courbes de récession plus douces que les réservoirs purement linéaires quand $R$ est grand, et revient à un comportement linéaire quand $R$ est petit — une propriété appréciable pour les bassins versants qui oscillent entre conditions saturées et sèches.
Le modèle expose aussi un **coefficient de correction de l'ETP** $X_5$, qui permet au calage de compenser les biais systématiques de la série d'ETP en entrée (p. ex. quand l'ETP d'Oudin est connue pour sur- ou sous-estimer l'ET d'un bassin versant particulier).

## Concepts clés

- **Réservoir de surface à débordement** : le réservoir supérieur $S$ a une capacité fixe $X_1$.
Toute pluie qui fait dépasser $X_1$ à $S$ est acheminée vers le bas comme $P_r$; le reste demeure dans $S$ et est disponible pour l'évaporation.
Ce simple seuil capture l'interception et le stockage superficiel du sol, et se réinitialise chaque jour si $S$ retombe sous la capacité à cause de l'évaporation.

- **Coefficient de correction de l'ETP** : l'évapotranspiration réelle est calculée comme $E_s = X_5 \cdot E$, où $E$ est l'ETP en entrée et $X_5$ un multiplicateur à caler.
C'est une façon grossière mais efficace d'absorber les biais systématiques de l'ETP pendant le calage : si Oudin sous-estime l'ET pour un bassin versant semi-aride, $X_5$ se cale à une valeur au-dessus de 1; s'il la surestime, $X_5$ se cale en dessous de 1.
Contrairement à la plupart des autres modèles de HOLMES, GARDENIA ne met **pas** $E_s$ à l'échelle selon le contenu en humidité du sol — le réservoir de surface est simplement borné à zéro quand il s'assèche.

- **Débit sortant quadratique du sol** : le réservoir de sol $R$ se draine via $Q_r = R^2 / (R + X_2 X_3)$, une loi non linéaire lisse.
Pour $R \gg X_2 X_3$, la réponse est quasi linéaire avec une pente de 1 (décharge complète par unité de stockage); pour $R \ll X_2 X_3$, elle devient quadratique avec une pente $R/(X_2 X_3)$.
Cela correspond au comportement empirique où les grandes crues se drainent presque proportionnellement tandis que la récession en étiage est beaucoup plus lente.

- **Percolation linéaire vers l'eau souterraine** : en plus du débit sortant quadratique, le réservoir de sol percole linéairement au taux $I_r = R/X_2$, représentant le drainage profond vers le réservoir d'eau souterraine $T$.
Les deux sorties de $R$ sont déduites en séquence, donc la percolation est calculée sur le stockage du sol après soustraction de $Q_r$.

- **Débit de base souterrain linéaire** : le réservoir d'eau souterraine $T$ se draine linéairement au taux $Q_t = T/X_4$, produisant un débit de base soutenu.
Un long temps de résidence ($X_4$ grand) donne une récession lente qui se prolonge dans les saisons sèches; un temps court donne une réponse plus vive.

- **Routage à délai fractionnaire** : comme le paramètre de délai $X_6$ est un nombre réel (typiquement entre 0.5 et 5 jours), GARDENIA utilise un **délai fractionnaire à deux éléments** plutôt qu'un hydrogramme unitaire.
Un registre de taille $\lceil X_6 \rceil + 1$ répartit le débit total entre deux pas de temps adjacents avec des poids qui interpolent linéairement entre délais entiers — p. ex. $X_6 = 2.3$ place 70 % du débit au jour 2 et 30 % au jour 3 après la génération.

## Fonctionnement

Le modèle GARDENIA traite les précipitations et l'évapotranspiration selon les étapes suivantes chaque jour :

**Étape 1 : entrée et débordement du réservoir de surface**.
La pluie est ajoutée au réservoir de surface : $S \leftarrow S + P$.
Toute quantité au-dessus de la capacité $X_1$ déborde comme $P_r = \max(0, S - X_1)$ et le réservoir est ramené à sa capacité : $S \leftarrow S - P_r$.
$P_r$ est le ruissellement qui entre dans le réservoir de sol.

**Étape 2 : évaporation de surface**.
L'ETP est corrigée par le coefficient $X_5$ et déduite du réservoir de surface : $E_s = X_5 \cdot E$, $S \leftarrow \max(0, S - E_s)$.
La borne à zéro gère le cas où l'ETP corrigée dépasse ce que contient actuellement le réservoir de surface (une situation normale en période sèche).
GARDENIA ne transfère pas l'ETP inutilisée au réservoir de sol, donc l'évaporation est purement superficielle.

**Étape 3 : entrée du réservoir de sol et débit sortant quadratique**.
Le réservoir de sol reçoit le débordement de la surface : $R \leftarrow R + P_r$.
La génération de débit $Q_r$ suit la loi quadratique $Q_r = R^2 / (R + X_2 X_3)$ et le réservoir est décrémenté : $R \leftarrow R - Q_r$.
Cette forme non linéaire signifie qu'un réservoir de sol plein génère un fort écoulement (le numérateur quadratique domine), tandis qu'un réservoir presque vide n'en génère presque pas.

**Étape 4 : percolation linéaire**.
Une fraction linéaire $I_r = R / X_2$ de l'eau restante du sol percole vers le réservoir d'eau souterraine.
Le sol est mis à jour : $R \leftarrow R - I_r$.
Notez que puisque $Q_r$ a été soustrait d'abord, la percolation opère sur le sol appauvri plutôt que sur l'original.

**Étape 5 : réservoir d'eau souterraine**.
Le réservoir d'eau souterraine reçoit la percolation : $T \leftarrow T + I_r$, puis se draine linéairement : $Q_t = T / X_4$, $T \leftarrow T - Q_t$.
$X_4$ est le temps de résidence linéaire, typiquement long par rapport à $X_2$ et $X_3$ pour générer un débit de base soutenu.

**Étape 6 : registre de délai**.
La sortie instantanée totale $Q_r + Q_t$ est ajoutée à un registre de délai de taille $\lceil X_6 \rceil + 1$.
Seules les deux dernières positions du registre reçoivent des poids non nuls — celle à l'indice $\lceil X_6 \rceil - 1$ reçoit $1/(X_6 - \lceil X_6 \rceil + 3)$ et celle à l'indice $\lceil X_6 \rceil$ reçoit le complément.
Le registre est ensuite décalé d'une position et son premier élément est retourné comme débit simulé, borné à zéro.

## Paramètres

Le modèle GARDENIA possède six paramètres à caler.

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ (RUMAX) | Capacité du réservoir de surface | 1–1000 | mm | Stockage maximal du réservoir superficiel (interception + sol de surface). Des valeurs élevées absorbent plus de pluie avant de déborder vers le sol. |
| $X_2$ (THG) | Constante de percolation linéaire | 1–1000 | jours | Temps de résidence contrôlant le taux auquel l'eau du sol percole vers le réservoir d'eau souterraine ($I_r = R / X_2$). Apparaît aussi au dénominateur du débit sortant quadratique du sol. |
| $X_3$ (RUIPER) | Paramètre de vidange latérale du réservoir de sol | 0.01–1000 | - | Avec $X_2$, fixe le seuil de stockage caractéristique au-dessus duquel le débit sortant du sol $Q_r$ passe d'un comportement quadratique à linéaire. Cale le volume global de la réponse rapide de ruissellement. |
| $X_4$ (K1) | Constante de vidange linéaire du réservoir d'eau souterraine | 1–500 | jours | Temps de résidence du réservoir souterrain linéaire. Des valeurs élevées produisent des récessions de débit de base plus longues et plus douces; des valeurs faibles rendent le débit de base plus réactif. |
| $X_5$ (PETC) | Coefficient de correction de l'ETP | 0.1–2.0 | - | Facteur multiplicatif appliqué à la série d'ETP en entrée. Utilisé pendant le calage pour absorber les biais systématiques de l'estimateur d'ETP (p. ex. Oudin sur- ou sous-estimant l'ET pour un climat donné). |
| $X_6$ (délai) | Délai de routage | 0.5–5 | jours | Délai pur appliqué à l'exutoire, implémenté comme une interpolation fractionnaire à deux éléments. Décale l'hydrogramme sans changer sa forme ni son amplitude. |

**Comprendre les paramètres :**

- **$X_1$** est le seuil d'interception de la pluie / du sol de surface.
Voyez-le comme la quantité de pluie que le bassin versant peut « absorber en surface » avant qu'aucun ruissellement ne soit généré.
Il n'a pas d'équivalent physique explicite dans les modèles opérationnels typiques HBV ou GR4J, mais joue un rôle similaire à $C_{\max}$ dans HYMOD ou $X_4$ dans GR4J.
- **$X_2$ et $X_3$ ensemble** définissent le débit sortant quadratique du sol.
Le stockage caractéristique effectif du sol est $X_2 \cdot X_3$; les écoulements deviennent limités en volume quand $R$ s'approche de cette valeur.
En même temps, $X_2$ seul contrôle le taux de percolation profonde — augmenter $X_2$ ralentit donc à la fois le débit sortant du sol *et* la recharge du réservoir d'eau souterraine.
- **$X_4$** est le temps de résidence linéaire de l'eau souterraine.
Un long $X_4$ (des semaines à des mois) donne un aquifère profond et lent à longue mémoire; un court $X_4$ (des jours) donne un bassin versant vif avec peu de stockage souterrain.
- **$X_5$** est la correction de biais de l'ETP.
Calé avec le reste, il se stabilise typiquement entre 0.5 et 1.5, avec des valeurs plus élevées dans les bassins versants humides où Oudin sous-estime la consommation d'eau des plantes et des valeurs plus faibles dans les bassins versants semi-arides où il la surestime.
- **$X_6$** est un pur bouton de synchronisation : il ne change ni le volume de crue ni la forme de la récession, seulement le moment où l'hydrogramme apparaît à l'exutoire.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs :

$$S_0 = X_1, \quad R_0 = 10, \quad T_0 = 80$$

où $S$ est le réservoir de surface (initialisé à sa capacité), $R$ le réservoir de sol et $T$ le réservoir d'eau souterraine.
Ces valeurs initiales sont fixes et produisent un court transitoire de mise en route qui se dissipe typiquement en quelques semaines de simulation.

Le registre de délai est un tableau fractionnaire à deux poids de taille $n = \lceil X_6 \rceil + 1$ dont seules les deux dernières entrées sont non nulles :

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

Par exemple, avec $X_6 = 1.5$, $n = 3$ et les poids sont $d_1 = 1/1.5 \approx 0.667$ et $d_2 \approx 0.333$ — donc deux tiers du débit sont livrés avec un délai de 1 jour et un tiers avec un délai de 2 jours, exactement l'interpolation fractionnaire attendue pour un délai de 1.5 jour.
Pour $X_6 = 2.3$, $n = 4$ et les poids sont $d_2 = 1/1.3 \approx 0.769$ et $d_3 \approx 0.231$, plaçant la majeure partie du débit près de la marque des 2 jours.

### Réservoir de surface

La pluie entre dans le réservoir de surface; l'excès au-dessus de la capacité $X_1$ devient du ruissellement :

$$S \leftarrow S + P$$

$$P_r = \max(0, S - X_1)$$

$$S \leftarrow S - P_r$$

L'ETP corrigée est déduite du réservoir de surface, bornée à zéro :

$$E_s = X_5 \cdot E$$

$$S \leftarrow \max(0, S - E_s)$$

### Réservoir de sol

Le réservoir de sol reçoit le débordement et se draine via une loi de débit quadratique :

$$R \leftarrow R + P_r$$

$$Q_r = \frac{R^2}{R + X_2 X_3}$$

$$R \leftarrow R - Q_r$$

La forme quadratique est la non-linéarité clé de GARDENIA.
Intuitivement : quand $R \gg X_2 X_3$, le dénominateur est dominé par $R$ et la formule se réduit à $Q_r \approx R$ (toute l'eau sort); quand $R \ll X_2 X_3$, le dénominateur est dominé par $X_2 X_3$ et $Q_r \approx R^2 / (X_2 X_3)$ (le débit varie avec le carré du stockage, une récession beaucoup plus lente).

Percolation linéaire vers le réservoir d'eau souterraine :

$$I_r = \frac{R}{X_2}$$

$$R \leftarrow R - I_r$$

### Réservoir d'eau souterraine

Le réservoir d'eau souterraine reçoit la percolation et se draine linéairement :

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_4}$$

$$T \leftarrow T - Q_t$$

### Routage du délai

La sortie instantanée totale avant routage est :

$$Q = Q_t + Q_r$$

Le registre $\{H_k\}$ est mis à jour avec la règle de décalage-addition, le nouveau débit $Q$ étant injecté seulement dans les deux dernières positions via les poids de délai fractionnaire $\{d_k\}$ :

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

Le débit simulé est le premier élément du registre, borné à zéro :

$$Q_{\text{sim}} = \max(0, H_0)$$

## Références

Thiery, D. (1982).
Utilisation d'un modèle global pour identifier sur un niveau piézométrique des influences multiples dues à diverses activités humaines.
*IAHS Publication*, 136, 71–77.

Thiery, D. (1988).
Forecast of changes in piezometric levels by a lumped hydrological model.
*Journal of Hydrology*, 97, 129–148.

Filippi, C., Milville, F., & Thiery, D. (1990).
Evaluation de la recharge des aquifères en climat Soudano-Sahélien par modélisation hydrologique globale: application à dix sites au Burkina Faso.
*Hydrological Sciences Journal*, 35(1), 29–48.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°9 (GARDENIA), pp. 333–336.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
