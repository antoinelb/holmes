# Modèle SMAR

## Aperçu

SMAR (Soil Moisture Accounting and Routing) est un modèle pluie-débit global journalier à huit paramètres développé à l'origine par O'Connell, Nash et Farrell au University College Galway, en Irlande (O'Connell et al., 1970).
Il a été conçu comme un modèle conceptuel généraliste pour la prévision opérationnelle des débits et a été largement appliqué à des bassins versants irlandais, tropicaux et semi-arides.

La variante implémentée dans HOLMES est la **version retenue** décrite dans l'Annexe 1 de Perrin (2000), correspondant à HOOPLA HM16.
Elle représente le bassin versant comme une **colonne de sol discrétisée en 16 couches** (chaque couche de 25 mm d'épaisseur, profondeur totale $Z = 400$ mm) alimentant deux réservoirs de routage parallèles — un linéaire (eau souterraine) et un quadratique (surface) — avec un hydrogramme unitaire de délai fractionnaire à l'exutoire.

Ce qui distingue SMAR parmi les modèles de HOLMES est sa **discrétisation verticale explicite du sol**.
Alors que la plupart des modèles représentent l'humidité du sol comme un seul réservoir global (GR4J, HYMOD, Bucket) ou comme quelques réservoirs discrets (SACRAMENTO, NAM), SMAR divise le sol en 16 couches physiques et applique l'évapotranspiration à chaque couche avec une **intensité décroissant exponentiellement** ($C^i$, où $C < 1$ et $i$ est l'indice de la couche).
Cela signifie que les couches supérieures s'assèchent en premier et plus intensément, tandis que les couches plus profondes retiennent l'humidité plus longtemps — une représentation réaliste de la façon dont les racines des plantes extraient l'eau préférentiellement près de la surface.
Le modèle est un bon choix pédagogique quand les étudiants doivent comprendre comment la structure verticale du sol affecte la génération du ruissellement et le comportement en récession.

## Concepts clés

- **Colonne de sol à 16 couches** : le sol est discrétisé en 16 couches de 25 mm chacune (total $Z = 400$ mm).
L'eau s'infiltre de la couche supérieure vers le bas; chaque couche se remplit jusqu'à sa capacité avant de déborder vers la suivante.
Le drainage de la couche inférieure constitue l'écoulement hypodermique.

- **Évapotranspiration décroissant exponentiellement** : chaque couche de sol $i$ est soumise à une évapotranspiration au taux $C^i \cdot E_n$, où $C = X_3 < 1$ est un coefficient à caler et $E_n$ la demande atmosphérique restante.
La couche supérieure reçoit l'ET la plus forte, et chaque couche suivante en reçoit exponentiellement moins — imitant la diminution avec la profondeur du prélèvement d'eau par la zone racinaire.

- **Ruissellement direct dépendant de l'humidité** : une fraction $H' = X_1 \cdot S / S_{\max}$ de la précipitation nette ruisselle directement sans entrer dans le sol, où $S$ est le contenu en eau des cinq couches supérieures.
À mesure que le sol s'humidifie, le ruissellement direct augmente — un mécanisme simple d'excès de saturation.

- **Capacité d'infiltration exponentielle** : le taux d'infiltration maximal décroît exponentiellement avec l'humidité du sol : $F_r = Y_m \cdot \exp(-X_2 \cdot S / S_{\max})$, où $Y_m = 200$ mm/j est un maximum fixe.
Un sol sec absorbe la pluie facilement; un sol proche de la saturation limite sévèrement l'infiltration.

- **Deux réservoirs de routage** : l'écoulement hypodermique issu de la colonne de sol est réparti entre un réservoir souterrain linéaire (fraction $1 - X_8$) et un réservoir de surface quadratique (fraction $X_8$).
Le réservoir linéaire produit un débit de base lisse et soutenu; le réservoir quadratique génère un écoulement plus pointu, à décroissance rapide, qui domine pendant les tempêtes.

- **Routage quadratique** : le réservoir de routage de surface se vide selon $Q_t = T^2 / (T + X_4)$, la même loi non linéaire que celle utilisée par GARDENIA.
Cela produit une récession rapide à fort stockage et une récession lente à faible stockage.

- **Coefficient de correction de l'ETP** : l'ETP en entrée est mise à l'échelle par un facteur à caler $X_7$ avant utilisation, ce qui permet au modèle de compenser des biais systématiques dans l'estimation de l'ETP (semblable au $X_5$ de GARDENIA).

- **Routage par délai fractionnaire** : un court délai pur $X_6$ (typiquement 0.5 à 5 jours) décale l'hydrogramme pour tenir compte du temps de parcours en chenal, par une interpolation fractionnaire à deux éléments entre les délais entiers adjacents.

## Fonctionnement

Le modèle SMAR traite les précipitations et l'évapotranspiration chaque jour selon les étapes suivantes :

**Étape 1 : correction de l'ETP et entrées nettes**.
L'ETP en entrée est mise à l'échelle par le coefficient de correction : $E_{\text{corr}} = X_7 \cdot E$.
La précipitation nette et l'évapotranspiration nette sont calculées comme des résidus complémentaires : $P_n = \max(0, P - E_{\text{corr}})$ et $E_n = \max(0, E_{\text{corr}} - P)$.
Une seule des deux est non nulle un jour donné — les jours humides $P_n > 0$ et $E_n = 0$; les jours secs $E_n > 0$ et $P_n = 0$.

**Étape 2 : ruissellement direct**.
Une fraction de la précipitation nette, dépendant de l'humidité, ruisselle directement : $P_{r1} = H' \cdot P_n$, où $H' = X_1 \cdot S / S_{\max}$.
Ici $S$ est la somme d'humidité des cinq couches supérieures (capacité $S_{\max} = 125$ mm).
Quand le sol est humide ($S \approx S_{\max}$), $H'$ approche $X_1$ et une part substantielle de la pluie contourne entièrement la colonne de sol; quand le sol est sec, presque toute la pluie s'infiltre.

**Étape 3 : infiltration et excès de surface**.
La capacité d'infiltration $F_r = 200 \cdot \exp(-X_2 \cdot S / S_{\max})$ limite la part de la pluie restante ($P_n - P_{r1}$) qui peut entrer dans le sol.
L'infiltration réelle est $P_s = \min(F_r, P_n - P_{r1})$, et tout surplus au-delà de la capacité d'infiltration devient l'excès de surface $P_{r2}$.

**Étape 4 : suivi de l'humidité du sol sur 16 couches**.
L'eau infiltrée $P_s$ descend en cascade les 16 couches séquentiellement : chaque couche absorbe l'eau jusqu'à sa capacité de 25 mm, et tout débordement passe à la couche suivante.
À chaque couche, l'évapotranspiration retire de l'eau à un taux décroissant exponentiellement $C^{i+1} \cdot E_n$ (où $i$ est l'indice de couche à partir de zéro), réduisant d'autant la demande atmosphérique restante $E_n$.
L'eau qui déborde de la couche inférieure (couche 16) constitue l'**écoulement hypodermique**.

**Étape 5 : routage souterrain linéaire**.
Une fraction $1 - X_8$ de l'écoulement hypodermique entre dans le réservoir souterrain linéaire : $L \leftarrow L + (1 - X_8) \cdot I$.
Le réservoir se vide linéairement : $Q_l = L / X_5$, produisant un débit de base lisse.

**Étape 6 : routage de surface quadratique**.
La fraction restante $X_8$ de l'écoulement hypodermique, plus l'éventuel excès de surface $P_{r2}$ de l'Étape 3, entre dans le réservoir de routage quadratique : $T \leftarrow T + X_8 \cdot I + P_{r2}$.
Le réservoir se vide selon la loi quadratique : $Q_t = T^2 / (T + X_4)$, produisant un écoulement pointu à décroissance rapide.

**Étape 7 : débit total et délai**.
Le débit total $Q = Q_l + Q_t + P_{r1}$ (débit de base + routage de surface + ruissellement direct) est injecté dans le registre de délai fractionnaire de taille $\lceil X_6 \rceil + 1$.
Le registre se décale d'un pas chaque jour, et le premier élément — borné à zéro — est retourné comme débit simulé.

## Paramètres

Le modèle SMAR possède huit paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ | Coefficient d'écoulement direct ($H$) | 0.01–1.0 | - | Fraction maximale de la précipitation nette qui ruisselle directement quand le sol superficiel est complètement saturé. Des valeurs plus élevées augmentent la nervosité des pics de crue. |
| $X_2$ | Paramètre d'infiltration ($Y_c$) | 0.01–10.0 | - | Contrôle la vitesse à laquelle la capacité d'infiltration décroît quand l'humidité du sol augmente. Des valeurs plus élevées signifient que le sol se « scelle » plus vite en s'humidifiant. |
| $X_3$ | Coefficient de réduction de l'ETP ($C$) | 0.01–0.99 | - | Base de la décroissance exponentielle de l'ET avec la profondeur : la couche $i$ reçoit $C^{i+1}$ de la demande atmosphérique restante. Des valeurs faibles concentrent l'ET dans les couches de surface; des valeurs proches de 1 répartissent l'ET uniformément dans la colonne de sol. |
| $X_4$ | Capacité du réservoir de routage quadratique | 1–500 | mm | Stockage caractéristique du réservoir de routage de surface quadratique. Des valeurs plus grandes ralentissent la récession de surface et étalent les pics de crue; des valeurs plus petites produisent des pics plus aigus. |
| $X_5$ | Constante de vidange du réservoir de routage linéaire | 1–200 | jours | Temps de résidence du réservoir souterrain linéaire ($Q_l = L / X_5$). Des valeurs grandes produisent des récessions de débit de base longues et soutenues; des valeurs petites donnent une réponse souterraine plus nerveuse. |
| $X_6$ | Délai | 0.5–5.0 | jours | Délai pur de routage en chenal appliqué à l'exutoire. Décale l'hydrogramme dans le temps sans changer sa forme. |
| $X_7$ | Coefficient de correction de l'ETP | 0.1–2.0 | - | Facteur multiplicatif appliqué à la série d'ETP en entrée. Des valeurs au-dessus de 1 augmentent l'évapotranspiration (utile quand l'ETP d'Oudin sous-estime pour un climat donné); en dessous de 1, elles la réduisent. |
| $X_8$ | Coefficient de répartition des écoulements ($G$) | 0.01–0.99 | - | Fraction de l'écoulement hypodermique routée vers le réservoir de surface quadratique. Le complément $(1 - X_8)$ va au réservoir souterrain linéaire. Contrôle l'équilibre entre écoulement rapide pointu et débit de base lent et soutenu. |

**Comprendre les paramètres :**

- **$X_1$** est le coefficient de ruissellement par excès de saturation.
À $X_1 = 1.0$, un sol complètement saturé envoie toute la précipitation nette directement au cours d'eau; à $X_1 = 0.01$, presque rien.
Attendez-vous à des valeurs calées entre 0.1 et 0.6 pour la plupart des bassins humides.
- **$X_2$ et $X_3$ ensemble** contrôlent la façon dont le sol traite l'eau.
$X_2$ gouverne la capacité d'infiltration (la vitesse à laquelle la pluie peut entrer dans la colonne de sol), tandis que $X_3$ gouverne le profil d'extraction de l'ET (la vitesse à laquelle le sol s'assèche depuis la surface).
Un $X_3$ faible (0.1–0.3) crée un sol s'asséchant nettement en surface; un $X_3$ élevé (0.7–0.9) distribue l'ET uniformément.
- **$X_4$ et $X_5$** sont les paramètres de routage.
$X_4$ contrôle la réponse rapide (quadratique), tandis que $X_5$ contrôle le débit de base lent (linéaire).
Quand $X_5 \gg X_4$, l'hydrogramme montre des pics rapides distincts sur une base lente — typique des bassins à aquifères profonds.
- **$X_8$** est un bouton de répartition des écoulements semblable au $X_5$ de MARTINE ou à la répartition fixe 90/10 de GR4J.
Des valeurs proches de 1 envoient la majeure partie de l'écoulement hypodermique par la voie quadratique rapide; des valeurs proches de 0 l'envoient vers l'eau souterraine.
Pour des bassins à fort débit de base, attendez-vous à $X_8 < 0.5$.

## Formulation mathématique

### Initialisation

États fixes des réservoirs à $t = 0$ :

$$W_i = 2 \text{ mm for } i = 1, \ldots, 16$$

$$S_0 = 100 \text{ mm}, \quad L_0 = 50 \text{ mm}, \quad T_0 = 20 \text{ mm}$$

où $W_i$ sont les stockages des couches de sol individuelles, $S$ est la somme d'humidité des cinq couches supérieures (recalculée à chaque pas), $L$ est le réservoir de routage linéaire et $T$ le réservoir de routage quadratique.

Le registre de délai fractionnaire $\{H_k\}$ a $n = \lceil X_6 \rceil + 1$ éléments, initialisés à zéro, avec les poids :

$$d_{n-2} = \frac{1}{X_6 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### Correction de l'ETP et entrées nettes

$$E_{\text{corr}} = X_7 \cdot E$$

$$P_n = \max(0, P - E_{\text{corr}})$$

$$E_n = \max(0, E_{\text{corr}} - P)$$

### Ruissellement direct

La somme d'humidité des cinq couches supérieures est :

$$S = \sum_{i=1}^{5} W_i, \quad S_{\max} = 125 \text{ mm}$$

La fraction de ruissellement direct dépendant de l'humidité :

$$H' = X_1 \cdot \frac{S}{S_{\max}}$$

$$P_{r1} = H' \cdot P_n$$

### Infiltration

La capacité d'infiltration décroît exponentiellement avec la saturation du sol :

$$F_r = Y_m \cdot \exp\!\left(-X_2 \cdot \frac{S}{S_{\max}}\right), \quad Y_m = 200 \text{ mm/d}$$

Infiltration réelle et excès de surface :

$$P_s = \min\!\bigl(F_r,\; \max(0, P_n - P_{r1})\bigr)$$

$$P_{r2} = \max\!\bigl(0,\; P_n - P_{r1} - P_s\bigr)$$

### Suivi de l'humidité du sol sur 16 couches

Pour chaque couche $i = 1, 2, \ldots, 16$ :

$$W_i \leftarrow W_i + P_s$$

$$P_s \leftarrow \max(0, W_i - 25)$$

$$W_i \leftarrow W_i - P_s$$

$$E_i = \min\!\bigl(W_i,\; X_3^{\,i} \cdot E_n\bigr)$$

$$W_i \leftarrow W_i - E_i$$

$$E_n \leftarrow E_n - E_i$$

Le $P_s$ restant après la couche inférieure est l'**écoulement hypodermique** :

$$I = P_s \big|_{i=16}$$

La somme d'humidité des cinq couches supérieures $S$ est ensuite recalculée pour le pas de temps suivant :

$$S \leftarrow \sum_{i=1}^{5} W_i$$

### Routage souterrain linéaire

Le réservoir linéaire reçoit une fraction $(1 - X_8)$ de l'écoulement hypodermique :

$$L \leftarrow L + (1 - X_8) \cdot I$$

$$Q_l = \frac{L}{X_5}$$

$$L \leftarrow L - Q_l$$

### Routage de surface quadratique

Le réservoir quadratique reçoit le reste de l'écoulement hypodermique plus l'excès de surface :

$$T \leftarrow T + X_8 \cdot I + P_{r2}$$

$$Q_t = \frac{T^2}{T + X_4}$$

$$T \leftarrow T - Q_t$$

### Routage par délai

Le débit total avant routage :

$$Q = Q_l + Q_t + P_{r1}$$

Le registre $\{H_k\}$ est mis à jour avec la règle décalage-et-addition :

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

Le débit simulé est :

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## Références

O'Connell, P. E., Nash, J. E., & Farrell, J. P. (1970).
River flow forecasting through conceptual models, Part II: The Brosna catchment at Ferbane.
*Journal of Hydrology*, 10(4), 317–329.

Kachroo, R. K. (1992).
River flow forecasting. Part 5. Applications of a conceptual model.
*Journal of Hydrology*, 133(1-2), 141–178.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°30 (SMAR), pp. 438–441.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
