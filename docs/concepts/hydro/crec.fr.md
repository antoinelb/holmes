# Modèle CREC

## Aperçu

CREC (Centre de Recherche en Eau de Chatou) est un modèle pluie-débit global journalier à six paramètres développé au Centre de Recherche en Eau de Chatou, qui fait partie d'Électricité de France (EDF).
Le modèle porte le nom de son institution d'origine, reflétant ses racines dans l'hydrologie opérationnelle française pour la production hydroélectrique.

CREC utilise une fonction sigmoïde pour répartir la pluie entre ruissellement direct et infiltration dans le sol en fonction de l'humidité du sol courante.
Cette répartition dépendante de l'humidité est le trait distinctif du modèle : plutôt que d'utiliser des ratios fixes ou des courbes de saturation, la répartition évolue de façon continue à mesure que le bassin versant s'humidifie.
Avec six paramètres, un réservoir de routage de surface non linéaire et une fonction de délai simple, CREC occupe une position intermédiaire entre la parcimonie de GR4J et la séparation explicite des voies d'écoulement du modèle bucket.

La structure du modèle se compose de trois réservoirs interconnectés : un réservoir d'humidité du sol qui contrôle la répartition de la pluie et l'évapotranspiration, un réservoir de routage de surface au drainage non linéaire (quadratique), et un réservoir d'eau souterraine qui reçoit la percolation et produit le débit de base par drainage linéaire.

## Concepts clés

- **Fonction de répartition sigmoïde** : une fonction logistique qui répartit de façon continue les précipitations entrantes entre ruissellement direct et infiltration dans le sol.
La répartition dépend de l'humidité du sol courante relativement au paramètre $X_3$ : quand le sol est humide ($S \gg X_3$), la majeure partie de la pluie devient du ruissellement; quand il est sec ($S \ll X_3$), la majeure partie s'infiltre.

- **Routage non linéaire (quadratique)** : le réservoir de surface se vide selon une relation quadratique $Q = R^2 / (R + X_1)$, ce qui signifie que le débit sortant croît plus vite que le stockage.
Cela produit des pointes de crue plus marquées que les réservoirs linéaires et représente mieux la dynamique de l'écoulement de surface.

- **Percolation linéaire** : l'eau passe du réservoir de surface au réservoir d'eau souterraine à un taux proportionnel au contenu du réservoir de surface ($R / X_5$), représentant le drainage lent à travers la colonne de sol.

- **Débit de base souterrain** : le réservoir profond se draine linéairement au taux $T / X_2$, produisant la composante soutenue d'étiage de l'hydrogramme.

- **Délai de routage** : une simple translation de l'hydrogramme combiné de $X_6$ jours par interpolation linéaire, représentant le temps de parcours en chenal.

## Fonctionnement

Le modèle CREC traite les précipitations et l'évapotranspiration selon les étapes suivantes :

**Étape 1 : répartition sigmoïde de la pluie**.
Les précipitations entrantes $P$ sont divisées entre le ruissellement direct ($P_r$) entrant dans le réservoir de surface et l'infiltration ($P_s$) entrant dans le réservoir de sol.
La répartition utilise une fonction logistique centrée sur le niveau d'humidité du sol : $P_r = P / (1 + \exp((X_3 - S) / X_4))$.
Quand le sol est saturé, le terme exponentiel s'annule et la majeure partie de la pluie devient du ruissellement.
Quand le sol est sec, le terme exponentiel domine et la majeure partie de la pluie s'infiltre.

**Étape 2 : suivi de l'humidité du sol**.
La portion infiltrée $P_s$ est ajoutée au réservoir de sol $S$.
L'évapotranspiration est ensuite extraite comme $E_s = E \cdot (1 - \exp(-S / X_F))$, où $X_F = 245$ mm est une constante fixe.
Cette formulation garantit que l'évapotranspiration réelle s'approche du taux potentiel quand le sol est humide et diminue exponentiellement à mesure que le sol s'assèche.

**Étape 3 : routage de surface avec drainage non linéaire**.
Le ruissellement direct $P_r$ entre dans le réservoir de surface $R$.
Le réservoir se vide par deux mécanismes : un débit sortant quadratique $Q_r = R^2 / (R + X_1)$ qui produit la composante rapide du débit, et une percolation linéaire $I_r = R / X_5$ qui alimente le réservoir d'eau souterraine.

**Étape 4 : stockage souterrain et débit de base**.
La percolation $I_r$ entre dans le réservoir d'eau souterraine $T$, qui se draine linéairement au taux $Q_t = T / X_2$ pour produire le débit de base.

**Étape 5 : délai de routage**.
Le débit sortant total ($Q_r + Q_t$) est retardé de $X_6$ jours par interpolation linéaire entre pas de temps adjacents, pour tenir compte du routage en chenal.

## Paramètres

Le modèle CREC possède six paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $X_1$ | Constante de vidange du réservoir de surface | 1–1000 | jours | Contrôle la vitesse de vidange du réservoir de surface par drainage non linéaire. Des valeurs élevées produisent des pointes de crue plus lentes et plus amorties. |
| $X_2$ | Paramètre de percolation linéaire | 1–1000 | - | Constante de temps du drainage de l'eau souterraine. Des valeurs élevées produisent un débit de base plus lent et plus soutenu. |
| $X_3$ | Paramètre de répartition de la pluie brute | 0–1000 | mm | Seuil d'humidité du sol pour la répartition sigmoïde. Quand $S = X_3$, les précipitations sont réparties également entre ruissellement et infiltration. |
| $X_4$ | Paramètre de répartition pour la production d'ETP | 1–500 | mm | Contrôle la netteté de la transition sigmoïde. Des valeurs faibles produisent un basculement plus net entre infiltration et ruissellement. |
| $X_5$ | Paramètre de vidange linéaire du réservoir de sol | 1–1000 | - | Contrôle le taux de percolation du réservoir de surface vers le réservoir d'eau souterraine. Des valeurs élevées signifient une percolation plus lente. |
| $X_6$ | Paramètre de délai | 0.5–5 | jours | Temps de translation de l'écoulement jusqu'à l'exutoire. Reflète la longueur et la vitesse du chenal. |

**Comprendre les paramètres :**

- **$X_1$** gouverne le comportement de routage non linéaire.
Pour de faibles niveaux de stockage, le débit sortant s'approche de $R^2 / X_1$ (quadratique), rendant la réponse lente.
Pour des niveaux de stockage élevés, le débit sortant s'approche de $R$ (presque toute l'eau sort), rendant la réponse rapide.
- **$X_2$ et $X_5$** contrôlent ensemble le régime de débit de base.
L'eau doit d'abord percoler du réservoir de surface (taux $1/X_5$) puis se drainer du réservoir d'eau souterraine (taux $1/X_2$), créant un délai en deux étapes.
- **$X_3$ et $X_4$** définissent la courbe de répartition sigmoïde.
$X_3$ fixe *où* la transition se produit (le niveau d'humidité du sol au point d'inflexion), tandis que $X_4$ fixe *avec quelle netteté* elle se produit.
Un petit $X_4$ crée un comportement quasi à seuil; un grand $X_4$ crée une transition graduelle.
- **$X_6$** est un paramètre purement temporel qui décale l'hydrogramme sans changer sa forme.

## Formulation mathématique

### Initialisation

Niveaux initiaux des réservoirs et constante fixe :

$$S_0 = 250, \quad R_0 = 10, \quad T_0 = 100, \quad X_F = 245$$

où $S$ est l'humidité du sol, $R$ le réservoir de routage de surface, $T$ le réservoir d'eau souterraine et $X_F$ une constante fixe de mise à l'échelle de l'évapotranspiration.

### Répartition sigmoïde de la pluie

Les précipitations $P$ sont réparties à l'aide d'une fonction logistique (sigmoïde) :

$$P_r = \frac{P}{1 + \exp\left(\frac{X_3 - S}{X_4}\right)}$$

$$P_s = P - P_r$$

où $P_r$ est le ruissellement direct entrant dans le réservoir de surface et $P_s$ la portion entrant dans le réservoir de sol.

La fonction sigmoïde $\sigma(S) = 1 / (1 + \exp((X_3 - S) / X_4))$ a les propriétés suivantes :

- Quand $S = X_3$ : $\sigma = 0.5$, donc les précipitations se répartissent également
- Quand $S \gg X_3$ : $\sigma \to 1$, donc presque toutes les précipitations deviennent du ruissellement
- Quand $S \ll X_3$ : $\sigma \to 0$, donc presque toutes les précipitations s'infiltrent
- $X_4$ contrôle la pente au point d'inflexion

### Dynamique de l'humidité du sol

Le réservoir de sol gagne de l'eau par infiltration et en perd par évapotranspiration :

$$S \leftarrow S + P_s$$

$$E_s = E \cdot \left(1 - \exp\left(\frac{-S}{X_F}\right)\right)$$

$$S \leftarrow \max(S - E_s, 0)$$

La formulation exponentielle de l'évapotranspiration garantit que l'ET réelle s'approche de l'ET potentielle quand le sol est humide ($S \gg X_F$) et diminue à mesure que le sol s'assèche.

### Réservoir de routage de surface

Le réservoir de surface reçoit le ruissellement direct et produit un débit sortant par deux mécanismes :

$$R \leftarrow R + P_r$$

**Débit sortant non linéaire (quadratique) :**

$$Q_r = \frac{R^2}{R + X_1}$$

$$R \leftarrow R - Q_r$$

**Percolation linéaire vers l'eau souterraine :**

$$I_r = \frac{R}{X_5}$$

$$R \leftarrow R - I_r$$

La formule de débit quadratique $R^2 / (R + X_1)$ se comporte comme suit :

- Pour un petit $R$ : $Q_r \approx R^2 / X_1$ (réponse lente, quadratique)
- Pour un grand $R$ : $Q_r \approx R - X_1$ (réponse rapide, presque linéaire)

### Réservoir d'eau souterraine

Le réservoir d'eau souterraine reçoit la percolation et se draine linéairement :

$$T \leftarrow T + I_r$$

$$Q_t = \frac{T}{X_2}$$

$$T \leftarrow T - Q_t$$

### Débit total du système

$$Q_{sys} = Q_r + Q_t$$

### Délai de routage

Le délai de routage est implémenté par interpolation linéaire.
Pour un délai de $X_6$ jours, le modèle maintient un tableau de délai de taille $\lceil X_6 \rceil + 1$ avec les poids :

$$d_{\lceil X_6 \rceil - 1} = \frac{1}{X_6 - \lceil X_6 \rceil + 3}, \quad d_{\lceil X_6 \rceil} = 1 - d_{\lceil X_6 \rceil - 1}$$

L'écoulement retardé est calculé en convoluant le débit du système avec ce tableau de délai :

$$Q(t) = \text{delayed}(Q_{sys}, X_6)$$

## Références

Cormary, Y., & Guilbot, A. (1973). Étude des relations pluie-débit sur trois bassins versants d'investigation. *IAHS Publication*, 108, 265-279.

Perrin, C. (2000). *Vers une amélioration d'un modèle global pluie-débit*.  PhD Thesis, INPG Grenoble, Appendix 1, pp. 313-316. [https://tel.archives-ouvertes.fr/tel-00006216](https://tel.archives-ouvertes.fr/tel-00006216)
