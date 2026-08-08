# Modèles d'évapotranspiration potentielle

## Modèle d'Oudin

### Aperçu

L'évapotranspiration potentielle (ETP) représente la quantité maximale d'eau qui s'évaporerait d'une surface bien alimentée en eau si l'approvisionnement était illimité.
Elle quantifie la demande atmosphérique en eau — combien l'atmosphère « veut » extraire de la surface terrestre selon l'énergie disponible et le déficit de pression de vapeur.

L'ETP est une entrée critique des modèles pluie-débit parce qu'elle détermine la part des précipitations qui retourne à l'atmosphère par rapport à celle qui devient du débit.
Sans prise en compte de l'évapotranspiration, un modèle de bilan hydrique surestimerait systématiquement le ruissellement.

La méthode d'Oudin est une approche parcimonieuse d'estimation de l'ETP qui ne requiert que la température et la latitude.
Développée spécifiquement pour les modèles pluie-débit globaux comme GR4J, elle échange de la complexité physique contre de l'applicabilité pratique.
Alors que des méthodes plus sophistiquées (comme Penman-Monteith) exigent des mesures de vent, d'humidité et de rayonnement souvent indisponibles, la méthode d'Oudin s'applique partout où des relevés de température existent.

### Concepts clés

- **Évapotranspiration** : le processus combiné d'évaporation depuis les surfaces (lacs, sol, végétation mouillée) et de transpiration des plantes.
  Ensemble, ces processus renvoient l'eau à l'atmosphère.

- **Évapotranspiration potentielle vs réelle** : l'ETP suppose une disponibilité en eau illimitée.
  L'évapotranspiration réelle (ETR) peut être inférieure à l'ETP quand l'eau est limitante (sol sec, plantes en stress).
  Le modèle hydrologique calcule l'ETR selon la disponibilité de l'humidité du sol.

- **Rayonnement extraterrestre** : le rayonnement solaire au sommet de l'atmosphère, avant toute absorption par les nuages ou l'atmosphère.
  Il ne dépend que de la latitude et du jour de l'année, ce qui le rend prévisible par des calculs astronomiques.

- **Relation énergie-température** : la température sert de substitut à l'énergie disponible pour l'évaporation.
  Un air plus chaud indique généralement plus de rayonnement solaire incident et une plus grande demande évaporatoire.

### Fonctionnement

La méthode d'Oudin calcule l'ETP en deux étapes :

**Étape 1 : calculer le rayonnement extraterrestre**.
À partir de la latitude et du jour de l'année, calculer le rayonnement solaire qui atteindrait le bassin versant s'il n'y avait pas d'atmosphère.
Cela capture la variation saisonnière et latitudinale de l'énergie disponible.

**Étape 2 : convertir en ETP**.
Mettre à l'échelle le rayonnement extraterrestre par un facteur dépendant de la température.
Au-dessus d'une température seuil, des températures plus élevées produisent plus d'ETP.
Sous le seuil, l'ETP est nulle (aucune demande évaporatoire).

La méthode suppose que la température capture l'information pertinente du bilan d'énergie, évitant le besoin de mesures directes de rayonnement.

### Formulation mathématique

#### Géométrie solaire

Le calcul commence par les relations astronomiques qui déterminent la quantité d'énergie solaire atteignant le sommet de l'atmosphère.

**Déclinaison solaire** (l'angle entre le Soleil et le plan équatorial) :

$$\delta = 0.409 \sin\left(\frac{2\pi \cdot DOY}{365} - 1.39\right)$$

où $DOY$ est le jour de l'année (1–365).

**Inverse de la distance relative Terre-Soleil** (tient compte de l'orbite elliptique de la Terre) :

$$d_r = 1 + 0.033 \cos\left(\frac{2\pi \cdot DOY}{365}\right)$$

**Angle horaire au coucher du soleil** (détermine la durée du jour) :

$$\omega_s = \arccos\left(-\tan(\phi) \cdot \tan(\delta)\right)$$

où $\phi$ est la latitude en radians.
L'argument est borné à $[-1, 1]$ pour gérer les latitudes polaires où le soleil ne se couche pas (soleil de minuit) ou ne se lève pas (nuit polaire).

#### Rayonnement extraterrestre

Le rayonnement extraterrestre journalier (l'énergie par unité de surface au sommet de l'atmosphère) :

$$R_e = \frac{24 \cdot 60}{\pi} G_{sc} \cdot d_r \left[\omega_s \sin(\phi) \sin(\delta) + \cos(\phi) \cos(\delta) \sin(\omega_s)\right]$$

où :

- $G_{sc} = 0.082$ MJ m⁻² min⁻¹ est la constante solaire
- Le résultat est en MJ m⁻² jour⁻¹

#### Chaleur latente de vaporisation

L'énergie requise pour évaporer l'eau diminue légèrement avec la température :

$$\lambda = 2.501 - 0.002361 \cdot T$$

où $\lambda$ est en MJ kg⁻¹ et $T$ est la température en °C.

#### Évapotranspiration potentielle

La formule d'Oudin pour l'ETP :

$$PET = \begin{cases}
\frac{R_e}{\lambda \cdot \rho} \cdot \frac{T + 5}{100} \cdot 1000 & T > -5°C \\
0 & T \leq -5°C
\end{cases}$$

où :

- $\rho = 1000$ kg m⁻³ est la masse volumique de l'eau
- Le résultat est en mm jour⁻¹
- Le facteur $(T + 5)/100$ est un terme de calage empirique

**Comprendre la formule :**

L'expression $R_e / (\lambda \cdot \rho)$ convertit l'énergie de rayonnement en hauteur d'eau équivalente (la quantité d'eau que cette énergie pourrait évaporer).
Le facteur $(T + 5)/100$ la met à l'échelle selon la température, le décalage de +5 garantissant que l'ETP reste positive même à des températures légèrement négatives (quand la sublimation peut encore se produire).

### Constantes et paramètres

La méthode d'Oudin utilise des constantes fixes — il n'y a aucun paramètre à caler :

| Constante | Valeur | Unités | Description |
|-----------|--------|--------|-------------|
| $G_{sc}$ | 0.082 | MJ m⁻² min⁻¹ | Constante solaire |
| $\rho$ | 1000 | kg m⁻³ | Masse volumique de l'eau |
| $T_{offset}$ | 5 | °C | Décalage de température empirique |
| $T_{threshold}$ | -5 | °C | Température minimale pour l'ETP |

Le seul paramètre d'entrée est la **latitude**, que HOLMES obtient des données du bassin versant.

### Considérations pratiques

#### Avantages de la méthode d'Oudin

1. **Besoins en données minimaux** : ne requiert que la température et la position (latitude).
   Aucune mesure de vent, d'humidité ou de rayonnement nécessaire.

2. **Robuste pour la modélisation pluie-débit** : conçue et testée spécifiquement pour les modèles globaux comme GR4J.
   Le calage empirique tient compte du fait que le modèle hydrologique ajustera encore l'évapotranspiration réelle.

3. **Physiquement raisonnable** : malgré sa simplicité, elle capture les principaux moteurs de la demande évaporatoire — la disponibilité en énergie (rayonnement) et la température.

4. **Cohérente** : aucun choix subjectif de coefficients culturaux, d'albédo ou d'autres paramètres pouvant introduire de l'incertitude.

#### Limites

1. **Aucun effet de la végétation** : ne distingue pas forêt, prairie ou sol nu.
   En réalité, le type de végétation affecte les taux d'évapotranspiration.

2. **Ni vent ni humidité** : ignore les conditions atmosphériques qui influencent le taux d'évaporation.
   Peut sous-performer par conditions très venteuses ou très humides.

3. **Pas de temps journalier** : la formulation suppose une moyenne journalière.
   Inadaptée aux calculs infra-journaliers sans modification.

4. **Calage empirique** : le facteur $(T + 5)/100$ a été calé contre des méthodes d'ETP plus complexes et peut ne pas être optimal partout.

#### Comparaison avec d'autres méthodes

| Méthode | Besoins en données | Complexité | Idéale pour |
|---------|--------------------|------------|-------------|
| **Oudin** | Température, latitude | Faible | Modèles pluie-débit globaux |
| **Hargreaves** | Température, latitude | Faible | Régions arides |
| **Penman-Monteith** | Température, humidité, vent, rayonnement | Élevée | Planification de l'irrigation, études détaillées |
| **Priestley-Taylor** | Température, rayonnement | Moyenne | Environnements limités par l'énergie |

Pour les besoins de la modélisation pluie-débit pédagogique dans HOLMES, la méthode d'Oudin offre un juste équilibre entre simplicité et précision.

#### Valeurs typiques d'ETP

Pour aider à interpréter les sorties du modèle, voici des plages journalières typiques d'ETP :

| Climat | Été | Hiver |
|--------|-----|-------|
| Tropical | 4–6 mm/jour | 3–5 mm/jour |
| Méditerranéen | 6–8 mm/jour | 1–2 mm/jour |
| Tempéré | 3–5 mm/jour | 0.5–1.5 mm/jour |
| Continental | 4–6 mm/jour | 0–1 mm/jour |
| Subarctique | 2–4 mm/jour | 0 mm/jour |

Si vos valeurs d'ETP calculées sortent de ces plages, vérifiez vos données d'entrée (surtout la latitude et les unités de température).

### Références

Oudin, L., Hervieu, F., Michel, C., Perrin, C., Andréassian, V., Anctil, F., & Loumagne, C. (2005). Which potential evapotranspiration input for a lumped rainfall–runoff model?: Part 2—Towards a simple and efficient potential evapotranspiration model for rainfall–runoff modelling. *Journal of Hydrology*, 303(1-4), 290-306. [https://doi.org/10.1016/j.jhydrol.2004.08.026](https://doi.org/10.1016/j.jhydrol.2004.08.026)

Cet article présente la méthode d'Oudin, la comparant à 27 autres formulations d'ETP sur 308 bassins versants et montrant que des méthodes simples fondées sur la température fonctionnent aussi bien que des méthodes complexes pour la modélisation pluie-débit.

Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). Crop evapotranspiration: Guidelines for computing crop water requirements. *FAO Irrigation and Drainage Paper 56*. Food and Agriculture Organization of the United Nations.

La référence incontournable pour l'équation de Penman-Monteith et les calculs d'évapotranspiration.
Plus détaillée que nécessaire pour HOLMES, elle fournit néanmoins un arrière-plan essentiel sur la physique de l'évapotranspiration.
