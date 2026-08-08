# Modèles de neige

## Modèle CemaNeige

### Aperçu

Dans de nombreux bassins versants à travers le monde, la neige joue un rôle fondamental dans le cycle hydrologique.
Les précipitations tombent en neige pendant les périodes froides, s'accumulent dans un manteau neigeux et libèrent de l'eau à la fonte printanière — modifiant fondamentalement la chronologie et l'amplitude du débit par rapport aux bassins alimentés par la pluie.
Comprendre et modéliser ces processus est essentiel pour la gestion des ressources en eau en région de montagne.

CemaNeige est un modèle de suivi du manteau neigeux de type degré-jour développé aux côtés de GR4J par les chercheurs de l'IRSTEA (anciennement Cemagref) en France.
Comme GR4J, CemaNeige privilégie la parcimonie : il capture la dynamique essentielle de l'accumulation et de la fonte de la neige avec seulement trois paramètres, ce qui le rend pratique pour les bassins versants où des observations détaillées de la neige ne sont pas disponibles.

CemaNeige fonctionne comme un préprocesseur du modèle hydrologique.
Il reçoit précipitations et température, suit l'évolution du manteau neigeux par bande d'altitude et produit la précipitation efficace (pluie plus fonte) qui alimente GR4J ou le modèle Bucket.

### Concepts clés

- **Méthode degré-jour** : une approche simple reliant la fonte à la température de l'air.
  Chaque degré au-dessus du point de congélation produit une certaine quantité de fonte.
  Bien que physiquement simpliste, elle fonctionne remarquablement bien en pratique parce que la température est corrélée aux composantes du bilan d'énergie qui pilotent la fonte.

- **Équivalent en eau de la neige (SWE)** : la quantité d'eau contenue dans le manteau neigeux, mesurée comme la hauteur d'eau qui résulterait d'une fonte instantanée de la neige.
  Plus significatif que la hauteur de neige parce qu'il tient compte de la densité de la neige.

- **État thermique** : la « température » interne du manteau neigeux.
  Un manteau froid (état thermique négatif) doit se réchauffer avant que la fonte puisse commencer, créant un délai entre les températures douces et le début de la fonte.

- **Bandes d'altitude** : les bassins versants de montagne couvrent de larges gammes d'altitude aux températures très différentes.
  CemaNeige divise le bassin versant en couches d'altitude, chacune avec sa propre température et son propre manteau neigeux, pour mieux représenter la variabilité spatiale.

- **Partage pluie-neige** : la transition entre pluie et neige n'est pas nette — près de 0 °C, la précipitation peut être un mélange.
  CemaNeige utilise une transition linéaire sur une plage de température de 4 °C.

### Fonctionnement

CemaNeige traite la précipitation par une séquence d'étapes pour chaque bande d'altitude :

**Étape 1 : ajustement de la température**.
La température mesurée (habituellement à une station de vallée) est ajustée pour chaque bande d'altitude à l'aide d'un gradient thermique altitudinal qui varie selon le jour de l'année.

**Étape 2 : partage pluie-neige**.
La précipitation se divise entre pluie (qui passe immédiatement) et neige (qui s'accumule dans le manteau neigeux) selon la température de l'air.

**Étape 3 : mise à jour de l'état thermique**.
L'état thermique du manteau évolue vers la température de l'air courante.
Un manteau froid « se souvient » des périodes froides précédentes et doit se réchauffer avant de fondre.

**Étape 4 : calcul de la fonte**.
Quand l'état thermique atteint le point de congélation et que la température de l'air le dépasse, la fonte se produit.
Le taux de fonte dépend de la température (facteur degré-jour) et de la taille du manteau (les petits manteaux fondent plus vite par unité de masse).

**Étape 5 : agrégation**.
La pluie et la fonte de toutes les bandes d'altitude s'additionnent pour donner la précipitation efficace totale du modèle hydrologique.

### Paramètres

CemaNeige possède trois paramètres :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|-------|--------|-------------------------|
| $C_{TG}$ | Coefficient d'état thermique | 0–1 | - | Contrôle la vitesse à laquelle la température du manteau répond à celle de l'air. Valeurs élevées = plus de « mémoire » des conditions passées. |
| $K_f$ | Facteur de fonte degré-jour | 0–20 | mm/°C/jour | Taux de fonte par degré au-dessus du point de congélation. Valeurs élevées = fonte plus rapide. |
| $Q_{NBV}$ | Seuil du manteau neigeux | 50–800 | mm | Taille du manteau pour une efficacité de fonte complète. En dessous, la fonte est plus lente. |

**Comprendre les paramètres :**

- **$C_{TG}$** agit comme une inertie thermique.
  À $C_{TG} = 0$, le manteau adopte instantanément la température de l'air.
  À $C_{TG} = 1$, le manteau ne répond jamais (irréaliste).
  Les valeurs typiques sont 0.2–0.5.

- **$K_f$** varie selon le climat et le terrain.
  Des valeurs autour de 3–5 mm/°C/jour sont typiques des bassins versants de montagne des latitudes moyennes.
  Les zones forestières tendent vers des valeurs plus faibles à cause de l'ombrage.

- **$Q_{NBV}$** contrôle la transition d'un couvert neigeux discontinu à un couvert continu.
  Un petit manteau fond avec une efficacité réduite (le couvert discontinu ne laisse qu'une partie du sol contribuer à la fonte), tandis qu'un manteau épais fond au taux plein.

### Formulation mathématique

#### Gradient thermique altitudinal

Pour chaque bande d'altitude $i$ d'altitude $z_i$, avec l'altitude médiane du bassin versant $z_{median}$ :

$$\Delta z_i = \frac{z_i - z_{median}}{100}$$

La température de chaque bande est ajustée par un gradient $\theta_{doy}$ dépendant du jour de l'année :

$$T_i = T_{measured} + \theta_{doy} \cdot \Delta z_i$$

Le gradient varie selon la saison, typiquement entre -0.4 et -0.5 °C par 100 m d'altitude.

#### Partage pluie-neige

La fraction de la précipitation tombant en neige dépend de la température :

$$f_{solid} = \begin{cases}
1 & T_i < -1°C \\
1 - \frac{T_i + 1}{4} & -1°C \leq T_i \leq 3°C \\
0 & T_i > 3°C
\end{cases}$$

La précipitation se partage comme :

$$P_{snow,i} = f_{solid} \cdot P_i$$

$$P_{rain,i} = (1 - f_{solid}) \cdot P_i$$

Le manteau neigeux s'accumule :

$$SWE_i \leftarrow SWE_i + P_{snow,i}$$

#### Évolution de l'état thermique

L'état thermique $U_i$ évolue comme un filtre exponentiel :

$$U_i \leftarrow \min\left(C_{TG} \cdot U_i + (1 - C_{TG}) \cdot T_i, \, 0\right)$$

L'état thermique est borné à 0 °C (une fois que le manteau atteint la température de fonte, il ne peut pas se réchauffer davantage sans fondre).

#### Calcul de la fonte

La fonte ne se produit que lorsque l'état thermique atteint le point de congélation ($U_i \geq 0$) et que la température de l'air dépasse le seuil ($T_i > 0$) :

**Fonte potentielle :**

$$M_{pot,i} = K_f \cdot (T_i - 0)$$

**Facteur d'efficacité de fonte :**

$$f_{NTS,i} = \min\left(\frac{SWE_i}{0.9 \cdot Q_{NBV}}, 1\right)$$

$$f_{melt,i} = 0.9 \cdot f_{NTS,i} + 0.1$$

Cela garantit une efficacité de fonte allant de 0.1 (sol presque nu) à 1.0 (manteau complet).

**Fonte réelle :**

$$M_i = \min(M_{pot,i} \cdot f_{melt,i}, \, SWE_i)$$

$$SWE_i \leftarrow SWE_i - M_i$$

#### Précipitation efficace

Précipitation efficace totale pour le modèle hydrologique :

$$P_{eff} = \sum_i \left(P_{rain,i} + M_i\right)$$

### Couches d'altitude

CemaNeige utilise des couches d'altitude pour représenter le gradient de température au sein d'un bassin versant.
Chaque couche reçoit la même précipitation mais a une température différente selon son altitude.

**Pourquoi les couches d'altitude comptent :**

1. **La température varie avec l'altitude**.
   À un gradient typique de -0.5 °C/100 m, un bassin versant couvrant 1000 m de dénivelé présente un gradient de température de 5 °C.

2. **La neige s'accumule en altitude pendant que la pluie tombe plus bas**.
   Une seule température moyenne de bassin manquerait ce motif spatial critique.

3. **La chronologie de la fonte diffère selon l'altitude**.
   La neige de basse altitude fond en premier, suivie progressivement des altitudes supérieures, ce qui étale la saison de fonte dans le temps.

**Implémentation dans HOLMES** : le nombre de couches d'altitude et leurs propriétés sont définis dans le fichier de données du bassin versant (CemaNeigeInfo.csv), qui précise la fraction de la superficie du bassin à chaque altitude et l'altitude médiane de chaque bande.

### Considérations pratiques

#### Quand activer CemaNeige

Activez CemaNeige quand :

- Le bassin versant reçoit des chutes de neige importantes (>10 % des précipitations annuelles)
- Vous observez une crue printanière pilotée par la fonte
- Le bassin versant contient des zones de haute altitude où les précipitations hivernales s'accumulent

Omettez CemaNeige quand :

- Le bassin versant reçoit rarement de la neige
- Les températures descendent rarement sous le point de congélation
- Vous travaillez en climat tropical ou subtropical

#### Interpréter les valeurs des paramètres

- **$C_{TG}$ faible (0.1–0.3)** : le manteau répond vite aux changements de température.
  Approprié pour les manteaux peu épais ou les climats maritimes.
- **$C_{TG}$ élevé (0.4–0.6)** : le manteau répond lentement.
  Approprié pour les manteaux épais et continentaux.
- **$K_f$ faible (1–3)** : fonte lente.
  Bassins versants forestiers, hautes latitudes ou terrain ombragé.
- **$K_f$ élevé (5–10)** : fonte rapide.
  Terrain ouvert, fort rayonnement solaire.

#### Problèmes courants

1. **Fonte trop précoce** : si le débit simulé culmine avant l'observé, essayez d'augmenter $C_{TG}$ (plus d'inertie thermique) ou de diminuer $K_f$ (fonte plus lente).

2. **Fonte trop tardive** : si le débit simulé culmine après l'observé, essayez de diminuer $C_{TG}$ ou d'augmenter $K_f$.

3. **Mauvaise durée de fonte** : si la fonte est trop concentrée ou trop étalée, ajustez $Q_{NBV}$.
   Des valeurs plus élevées étalent la fonte sur une période plus longue.

4. **Données d'altitude** : assurez-vous que les bandes d'altitude représentent bien l'hypsométrie du bassin versant (la distribution de la superficie selon l'altitude).

### Références

Valéry, A., Andréassian, V., & Perrin, C. (2014). 'As simple as possible but not simpler': What is useful in a temperature-based snow-accounting routine? Part 2 – Sensitivity analysis of the Cemaneige snow accounting routine on 380 catchments. *Journal of Hydrology*, 517, 1176-1187. [https://doi.org/10.1016/j.jhydrol.2014.04.058](https://doi.org/10.1016/j.jhydrol.2014.04.058)

Cet article présente l'analyse de sensibilité de CemaNeige sur des centaines de bassins versants, fournissant des repères sur les plages de paramètres et le comportement du modèle.

Valéry, A., Andréassian, V., & Perrin, C. (2014). 'As simple as possible but not simpler': What is useful in a temperature-based snow-accounting routine? Part 1 – Comparison of six snow accounting routines on 380 catchments. *Journal of Hydrology*, 517, 1166-1175. [https://doi.org/10.1016/j.jhydrol.2014.04.059](https://doi.org/10.1016/j.jhydrol.2014.04.059)

L'article compagnon comparant CemaNeige à d'autres modèles de neige, démontrant son efficacité malgré sa simplicité.
