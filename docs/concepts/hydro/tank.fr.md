# Modèle TANK

## Aperçu

TANK est un modèle pluie-débit conceptuel développé par Sugawara (1979) au National Research Center for Disaster Prevention au Japon et est depuis devenu l'un des modèles opérationnels les plus utilisés en Asie de l'Est.
La version implémentée dans HOLMES suit la « version retenue » à sept paramètres de Perrin (Perrin, 2000, fiche n°31), cataloguée HM17 dans le cadre HOOPLA.

Le modèle représente un bassin versant comme une cascade verticale de quatre réservoirs linéaires — surface ($S$), sol supérieur ($R$), sol inférieur ($T$) et eau souterraine ($L$) — chacun se vidant dans le suivant par un orifice de fond fixe.
Le réservoir de surface porte deux orifices latéraux supplémentaires qui ne s'activent que lorsque son stockage dépasse des seuils calés, ce qui permet au modèle de représenter une réponse abrupte de l'écoulement dès que le sol devient suffisamment humide.
Les débits sortants des quatre réservoirs sont agrégés et routés à travers un filtre de délai fractionnaire avant d'atteindre l'exutoire.

TANK est conceptuellement simple mais étonnamment expressif : la progression géométrique des constantes de temps de vidange ($x_3$, $x_3 x_4$, $x_3 x_4 x_7$, $x_3 x_4 x_7^2$) crée une séparation naturelle des composantes rapide, intermédiaire, lente et très lente de l'écoulement, sans aucune équation explicite de répartition.
Cela fait de TANK un bon contrepoint pédagogique à des modèles comme GR4J (qui répartit l'écoulement explicitement) ou HYMOD (qui distribue le ruissellement par une loi de Pareto) : dans TANK, la séparation des écoulements émerge de la seule dynamique des stockages.

## Concepts clés

- **Réservoir de surface ($S$)** : le réservoir le plus haut, qui reçoit toutes les précipitations.
Contrairement aux trois réservoirs en dessous, $S$ possède deux orifices latéraux qui ne s'activent que lorsque le stockage dépasse $x_1 + x_2$ (seuil supérieur) et $x_2$ (seuil inférieur), produisant un écoulement rapide pendant les épisodes humides.

- **Réservoir de sol supérieur ($R$)** : reçoit le drainage de fond de $S$.
Possède un orifice latéral au seuil $x_2$ et un orifice de fond; se vide sur une échelle de temps intermédiaire contrôlée par le produit $x_3 x_4$.

- **Réservoir de sol inférieur ($T$)** : reçoit le drainage de fond de $R$.
Possède un orifice latéral au seuil $x_2$ et un orifice de fond; se vide sur une échelle de temps lente contrôlée par $x_3 x_4 x_7$.

- **Réservoir d'eau souterraine ($L$)** : le réservoir le plus profond, sans orifice latéral.
Il se vide uniquement par un seul orifice de fond linéaire sur l'échelle de temps très lente $x_3 x_4 x_7^2$, produisant la plus longue récession du débit de base.

- **Orifices latéraux à double seuil** : le réservoir de surface est le seul à posséder deux orifices latéraux. L'orifice supérieur (seuil $x_1 + x_2$) produit des pics intenses pendant les tempêtes; l'orifice inférieur (seuil $x_2$) produit un écoulement rapide modéré pendant les périodes humides.

- **Progression géométrique des constantes de temps** : les quatre orifices de fond partagent la constante de base $x_3$, successivement multipliée par $x_4$, $x_7$, puis $x_7$ à nouveau. Cela produit une hiérarchie physiquement motivée d'échelles de temps de récession sans exiger le calage séparé de chacune.

- **Évapotranspiration en cascade** : la demande d'ETP (corrigée par $x_6$) est satisfaite de haut en bas — d'abord depuis $S$, puis toute demande non satisfaite passe à $R$, puis $T$, puis $L$. Les réservoirs plus profonds ne perdent de l'eau par ET qu'une fois tous les réservoirs moins profonds à sec.

- **Routage par délai fractionnaire** : la somme des cinq débits sortants (deux orifices latéraux sur $S$, trois orifices de fond sur $R$, $T$, $L$) passe par un filtre de délai fractionnaire de longueur $\lceil x_5 \rceil + 1$. Les valeurs non entières de $x_5$ répartissent la masse entre deux pas de temps adjacents.

## Fonctionnement

**Étape 1 : correction de l'ETP**.
L'ETP entrante $E$ est multipliée par le coefficient de correction $x_6$ pour obtenir la demande d'ETP effective $E_1 = E \cdot x_6$.
Des valeurs de $x_6 < 1$ réduisent la demande (courant quand l'ETP provient des formules d'Oudin ou de Penman, qui surestiment légèrement l'évaporation); des valeurs proches de 1 la laissent inchangée.

**Étape 2 : mise à jour du réservoir de surface et débits à seuil**.
Toutes les précipitations entrent dans $S$.
Si $S$ dépasse le seuil supérieur $x_1 + x_2$, l'excès se vide comme $Q_{s1}$ au taux $1/x_3$.
Si le $S$ restant dépasse encore le seuil inférieur $x_2$, un deuxième débit latéral $Q_{s2}$ se vide au même taux.
Enfin, un drainage de fond $I_s = S / x_3$ alimente le réservoir suivant.

**Étape 3 : satisfaction de l'ET depuis $S$ et cascade vers $R$**.
L'ET est prélevée dans $S$ à hauteur de l'eau disponible; toute demande non satisfaite $E_2 = E_1 - E_S$ est transmise à $R$.
L'eau s'infiltrant par le fond de $S$ ($I_s$) entre dans $R$.
$R$ possède un orifice latéral au seuil $x_2$ se vidant au taux $1/(x_3 x_4)$, un orifice de fond au même taux, et un terme d'ET satisfaisant la demande résiduelle.

**Étape 4 : cascade à travers $T$**.
Le drainage de fond de $R$ ($I_r$) entre dans $T$.
$T$ a la même structure que $R$ (un orifice latéral au seuil $x_2$, un orifice de fond) mais avec une constante de temps plus lente $1/(x_3 x_4 x_7)$.
Les résidus d'ET cascadent en $E_3 = E_2 - E_R$.

**Étape 5 : dynamique de l'eau souterraine dans $L$**.
Le drainage de fond de $T$ ($I_t$) entre dans $L$.
Contrairement aux trois réservoirs au-dessus, $L$ n'a pas d'orifice latéral — seulement un unique drain de fond linéaire au taux $1/(x_3 x_4 x_7^2)$.
L'ET résiduelle est ensuite prélevée dans $L$.

**Étape 6 : routage par délai fractionnaire**.
Les cinq débits sortants ($Q_{s1}$, $Q_{s2}$, $Q_r$, $Q_t$, $Q_l$) sont sommés et passés par un filtre de délai de longueur $\lceil x_5 \rceil + 1$.
Quand $x_5$ est non entier, le filtre répartit la masse d'écoulement entre deux pas de temps adjacents, permettant une résolution du délai plus fine que le jour.
Le premier élément du tampon de délai est le débit simulé, borné à zéro.

## Paramètres

Le modèle TANK possède 7 paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $x_1$ | Seuil de débit supérieur de $S$ | 1–1000 | mm | Niveau de stockage au-dessus duquel l'orifice latéral supérieur du réservoir de surface s'active. Contrôle le déclenchement de l'écoulement rapide et nerveux des pics de tempête. |
| $x_2$ | Seuil de débit inférieur | 1–1000 | mm | Niveau de stockage au-dessus duquel l'orifice latéral inférieur de $S$ (et les orifices latéraux de $R$, $T$) s'activent. Contrôle le déclenchement d'un écoulement rapide modéré. |
| $x_3$ | Constante de vidange rapide | 1–100 | jours | Constante de temps de base pour tous les orifices de fond. Des valeurs plus grandes ralentissent chaque réservoir proportionnellement. |
| $x_4$ | Multiplicateur de vidange intermédiaire | 1–100 | – | Multiplicateur appliqué à $x_3$ pour obtenir les constantes de temps de vidange de $R$ et $T$. Des valeurs plus grandes allongent la récession intermédiaire. |
| $x_5$ | Délai | 0.5–5 | jours | Longueur du filtre de délai fractionnaire; contrôle le décalage entre la pluie et le pic de débit. |
| $x_6$ | Coefficient de correction de l'ETP | 0.1–2 | – | Correction multiplicative appliquée à l'ETP de forçage. Compense un biais systématique de la formule d'ETP. |
| $x_7$ | Multiplicateur de vidange lente | 1–100 | – | Multiplicateur appliqué à $x_3 x_4$ pour obtenir la constante de temps de vidange de $T$, et élevé au carré pour celle de $L$. Des valeurs grandes produisent de longues récessions du débit de base. |

**Comprendre les paramètres :**

- **$x_1$ et $x_2$** contrôlent ensemble à quel point la réponse du bassin paraît « nerveuse ».
Un $x_2$ bas signifie que le bassin produit facilement de l'écoulement rapide (typique des bassins tempérés humides); un $x_1$ élevé signifie que seules les grandes tempêtes déclenchent l'orifice supérieur (typique des bassins secs ou à sols profonds).
Comme le seuil supérieur additionne les deux ($x_1 + x_2$), caler $x_2$ d'abord puis $x_1$ est généralement plus stable.
- **$x_3$, $x_4$, $x_7$** déterminent conjointement le comportement complet de récession, des jours aux mois.
Commencez avec $x_3 \approx 10$ (récession rapide typique d'un modèle journalier), ajustez $x_4$ pour reproduire les échelles de temps de mi-récession, et réglez $x_7$ en dernier pour ajuster le débit de base.
- **$x_5$** est presque toujours petit (0.5–2 jours) pour les modèles journaliers; un calage nettement plus élevé indique généralement un problème de routage amont ou un décalage des données plutôt qu'une véritable propriété du bassin.
- **$x_6$** devrait se caler près de 1.0 si l'ETP en entrée est raisonnable.
Des valeurs systématiquement éloignées de 1.0 (sous 0.5 ou au-dessus de 1.5) signalent souvent une formule d'ETP mal adaptée ou une entrée de température incorrecte.
- La progression quadratique de la vidange de $L$ via $x_7^2$ signifie que de petits changements de $x_7$ ont des effets disproportionnés sur le comportement des étiages.
Calez $x_7$ en dernier et surveillez attentivement les indices d'étiage.

## Formulation mathématique

### Initialisation

Les quatre réservoirs démarrent à 10 mm (convention HOOPLA HM17) :

$$S_0 = R_0 = T_0 = L_0 = 10 \text{ mm}$$

### Correction de l'ETP et réservoir de surface

$$S \leftarrow S + P, \qquad E_1 = E \cdot x_6$$

Débit latéral au seuil supérieur :

$$Q_{s1} = \max\!\left(0,\; \frac{S - (x_1 + x_2)}{x_3}\right), \qquad S \leftarrow S - Q_{s1}$$

Débit latéral au seuil inférieur :

$$Q_{s2} = \max\!\left(0,\; \frac{S - x_2}{x_3}\right), \qquad S \leftarrow S - Q_{s2}$$

Drainage de fond vers $R$ :

$$I_s = \frac{S}{x_3}, \qquad S \leftarrow S - I_s$$

ET depuis $S$ et demande résiduelle :

$$E_S = \min(E_1,\, S), \qquad S \leftarrow S - E_S, \qquad E_2 = E_1 - E_S$$

### Réservoir de sol supérieur ($R$)

$$R \leftarrow R + I_s$$

$$Q_r = \max\!\left(0,\; \frac{R - x_2}{x_3 x_4}\right), \qquad R \leftarrow R - Q_r$$

$$I_r = \frac{R}{x_3 x_4}, \qquad R \leftarrow R - I_r$$

$$E_R = \min(E_2,\, R), \qquad R \leftarrow R - E_R, \qquad E_3 = E_2 - E_R$$

### Réservoir de sol inférieur ($T$)

$$T \leftarrow T + I_r$$

$$Q_t = \max\!\left(0,\; \frac{T - x_2}{x_3 x_4 x_7}\right), \qquad T \leftarrow T - Q_t$$

$$I_t = \frac{T}{x_3 x_4 x_7}, \qquad T \leftarrow T - I_t$$

$$E_T = \min(E_3,\, T), \qquad T \leftarrow T - E_T, \qquad E_4 = E_3 - E_T$$

### Réservoir d'eau souterraine ($L$)

Le réservoir souterrain n'a pas d'orifice latéral — seulement un unique drain de fond linéaire avec la constante de temps la plus lente :

$$L \leftarrow L + I_t$$

$$Q_l = \frac{L}{x_3 x_4 x_7^2}, \qquad L \leftarrow L - Q_l$$

$$E_L = \min(E_4,\, L), \qquad L \leftarrow L - E_L$$

### Routage par délai fractionnaire

Soit $n = \lceil x_5 \rceil + 1$ et définissons les poids de délai $d \in \mathbb{R}^n$ par :

$$d_{n-2} = \frac{1}{x_5 - n + 3}, \qquad d_{n-1} = 1 - d_{n-2}, \qquad d_i = 0 \text{ for } i < n-2$$

Ces deux poids somment à 1 et répartissent la masse du débit sortant entre deux cases adjacentes du tampon de délai.
Le débit total à router est la somme des cinq orifices des réservoirs :

$$Q_{\text{tot}} = Q_{s1} + Q_{s2} + Q_r + Q_t + Q_l$$

Le tampon de délai $HY$ est mis à jour à chaque pas de temps par un décalage à gauche plus une injection pondérée :

$$HY_i \leftarrow HY_{i+1} + d_i \cdot Q_{\text{tot}}, \quad i = 0, \ldots, n-2$$

$$HY_{n-1} \leftarrow d_{n-1} \cdot Q_{\text{tot}}$$

### Débit total

$$Q(t) = \max(0,\, HY_0(t))$$

## Références

- Sugawara, M. (1979). Automatic calibration of the tank model. *Hydrological Sciences Bulletin*, 24(3), 375–388. [DOI](https://doi.org/10.1080/02626667909491876)
- Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative* (PhD thesis). INPG, Grenoble. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
- Sugawara, M. (1995). Tank model. In V. P. Singh (Ed.), *Computer Models of Watershed Hydrology* (pp. 165–214). Water Resources Publications, Colorado.
