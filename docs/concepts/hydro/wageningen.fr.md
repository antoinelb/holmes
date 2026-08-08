# Modèle WAGENINGEN

## Aperçu

WAGENINGEN est un modèle pluie-débit global journalier à huit paramètres développé par Warmerdam, Kole et Chormanski (1997) à la Wageningen Agricultural University aux Pays-Bas.
Il a été conçu comme un modèle conceptuel parcimonieux adapté aux bassins versants tempérés humides et à la prévision opérationnelle.

La variante implémentée dans HOLMES est le portage HOOPLA HM19 décrit dans l'Annexe 1 de Perrin (2000).
Le modèle représente le bassin versant comme **trois réservoirs dans une chaîne production–routage** : un réservoir de sol $S$ qui contrôle l'évapotranspiration et la percolation, un réservoir lent sous-intermédiaire $T$ qui peut renvoyer de l'eau vers $S$ par remontée capillaire, et un réservoir de surface rapide $R$ — les deux réservoirs de routage se vidant à travers un hydrogramme unitaire de délai fractionnaire commun.

Le trait distinctif de WAGENINGEN est la **séparation à seuil** au niveau d'humidité du sol $X_1$.
Quand $S \geq X_1$, le sol est assez humide pour se vider vers le système de routage et évapotranspire à la pleine demande atmosphérique; quand $S < X_1$, la percolation s'arrête, la remontée capillaire transfère de l'eau vers le haut depuis $T$, et l'évapotranspiration suit une enveloppe en cosinus qui s'atténue en douceur vers zéro à mesure que le sol s'assèche.
Cela fournit une illustration pédagogiquement utile de la façon dont un seul seuil d'humidité peut engendrer quatre régimes de processus couplés (drainage, remontée capillaire, ET pleine, ET réduite) sans introduire de paramètres de calage supplémentaires.

## Concepts clés

- **Seuil d'humidité du sol $X_1$** : le niveau d'humidité unique qui fait basculer le modèle entre un régime humide (percolation active, ET sans restriction) et un régime sec (percolation coupée, remontée capillaire de $T$ vers $S$ active, ET amortie).

- **Évapotranspiration à enveloppe en cosinus** : sous le seuil, l'ET réelle est mise à l'échelle par $\cos\!\bigl((\pi/2)\cdot(X_1 - S)/X_1\bigr)$.
Cela produit une atténuation lisse et concave depuis la pleine demande atmosphérique à $S = X_1$ jusqu'à zéro à $S = 0$ — plus douce qu'une réduction linéaire et numériquement stable.

- **Remontée capillaire $I_t$** : quand $S < X_1$, l'eau monte du réservoir lent $T$ vers $S$ à un taux proportionnel à la fois au stockage dans $T$ et au déficit d'humidité du sol $(X_1 - S)$.
C'est le seul modèle de HOLMES qui représente explicitement la remontée capillaire.

- **Dissociation des écoulements via $\mathrm{DIV} = \min(1, T/X_5)$** : le rapport entre le stockage dans $T$ et le seuil de dissociation $X_5$ décide de la répartition de la percolation $I_s$ entre routage rapide et lent — quand $T$ est plein, la voie lente sature et tout part en rapide; quand $T$ est vide, toute la percolation part en lent pour le remplir.

- **Réservoir rapide $R$** : réservoir de routage linéaire de constante de temps $X_6$, produisant les pics d'événements de tempête.

- **Réservoir lent $T$** : réservoir de routage linéaire de constante de temps $X_6 \cdot X_7$ (avec $X_7 \geq 1$), produisant un débit de base soutenu.
Le même réservoir alimente la remontée capillaire vers $S$.

- **Routage par délai fractionnaire** : un délai de chenal pur $X_8$ (en jours) décale l'hydrogramme combiné, en interpolant entre les deux délais entiers adjacents.

## Fonctionnement

**Étape 1 : mise à jour de l'humidité du sol**.
La précipitation $P$ est ajoutée au réservoir de sol : $S \leftarrow S + P$.
La valeur courante de $S$ par rapport au seuil $X_1$ détermine lequel des deux régimes s'applique pour le reste du pas.

**Étape 2 : percolation ou remontée capillaire**.
Si $S \geq X_1$, la percolation vide le sol : $I_s = (S/X_2) \cdot (S - X_1)/X_3$, et aucune remontée capillaire ne se produit.
Si $S < X_1$, la percolation s'arrête et la remontée capillaire fait monter l'eau de $T$ vers $S$ : $I_t = (T/X_4) \cdot (X_1 - S)$.
Le réservoir de sol est ensuite mis à jour : $S \leftarrow S + I_t - I_s$.

**Étape 3 : évapotranspiration**.
Au-dessus du seuil, l'ET réelle égale la demande : $E_s = E$.
Sous le seuil, l'ET est amortie par une enveloppe en cosinus : $E_s = E \cdot \cos\!\bigl((\pi/2)\cdot(X_1 - S)/X_1\bigr)$.
Le stockage du sol est mis à jour et borné à zéro : $S \leftarrow \max(0, S - E_s)$.

**Étape 4 : dissociation des écoulements**.
L'eau percolée $I_s$ est répartie entre les deux réservoirs de routage par le rapport de dissociation $\mathrm{DIV} = \min(1, T/X_5)$.
Une fraction $\mathrm{DIV} \cdot I_s$ va au réservoir rapide $R$ et le reste $(1 - \mathrm{DIV}) \cdot I_s$ va au réservoir lent $T$.
Quand $T$ est presque vide, la voie lente absorbe la majeure partie du flux; quand $T$ est bien rempli, la voie rapide domine.

**Étape 5 : routage linéaire**.
Les deux réservoirs de routage se vident selon des lois de réservoir linéaire.
Le réservoir rapide se vide avec la constante de temps $X_6$ : $Q_r = R/X_6$.
Le réservoir lent se vide avec la constante de temps $X_6 \cdot X_7$ : $Q_t = T/(X_6 \cdot X_7)$.
Comme $X_7 \geq 1$, le réservoir lent est toujours au moins aussi lent que le rapide.

**Étape 6 : routage par délai**.
Le débit sortant combiné $Q_r + Q_t$ est injecté dans le registre de délai fractionnaire de taille $\lceil X_8 \rceil + 1$.
Le registre se décale d'un pas chaque jour, et le premier élément, borné à zéro, est retourné comme débit simulé.

## Paramètres

Le modèle WAGENINGEN possède huit paramètres à caler :

| Paramètre | Description | Plage | Unités | Interprétation physique |
|-----------|-------------|:-----:|--------|-------------------------|
| $X_1$ | Seuil de percolation/ET | 1–500 | mm | Niveau d'humidité du sol au-dessus duquel la percolation s'active et l'ET fonctionne sans restriction. Agit comme la « capacité au champ » du modèle — plus il est haut, plus le bassin doit constituer de stockage avant de générer du ruissellement. |
| $X_2$ | Capacité caractéristique du réservoir de sol | 10–2000 | mm | Apparaît au dénominateur du taux de percolation. Des valeurs plus grandes ralentissent le drainage du réservoir de sol et favorisent une humidité soutenue. |
| $X_3$ | Constante de vidange d'infiltration | 0.1–1000 | mm | Second dénominateur du taux de percolation. Avec $X_2$, elle contrôle la vitesse de drainage du sol au-dessus du seuil. |
| $X_4$ | Constante de remontée capillaire | 1–1000 | j | Analogue d'une constante de temps pour le flux ascendant de $T$ vers $S$. Des valeurs plus petites produisent une récupération capillaire plus rapide après la sécheresse. |
| $X_5$ | Seuil de dissociation des écoulements | 0.1–500 | mm | Niveau de stockage dans $T$ auquel la voie lente sature et toute la percolation part en rapide. De petites valeurs rendent le modèle nerveux; de grandes valeurs favorisent le stockage souterrain. |
| $X_6$ | Constante de temps du réservoir rapide | 0.5–50 | j | Temps de résidence de $R$. Contrôle la vitesse de récession des tempêtes. |
| $X_7$ | Rapport des constantes de temps lente/rapide | 1–50 | - | Facteur multiplicatif : la constante de temps du réservoir lent est $X_6 \cdot X_7$. Contraint $\geq 1$ pour que la voie lente soit véritablement plus lente que la rapide. |
| $X_8$ | Délai de routage | 0.5–5 | j | Décalage pur de temps de parcours en chenal appliqué à l'exutoire. |

**Comprendre les paramètres :**

- **$X_1$ est de loin le paramètre le plus sensible.**
Il fixe la frontière entre régimes humide et sec : trop bas, le modèle percole et évapore presque toujours à plein taux (comportement de réservoir linéaire); trop haut, le sol ne se vide jamais (toutes les précipitations perdues en ET).
Attendez-vous à des valeurs calées entre 50 et 200 mm sur les bassins humides.
- **$X_2$ et $X_3$ mettent conjointement à l'échelle le taux de percolation** via $(S/X_2) \cdot (S - X_1)/X_3$.
Comme ils apparaissent multiplicativement dans un dénominateur, ils sont fortement équifinaux — augmenter l'un et diminuer l'autre donne le même drainage, si bien que le calage fixe typiquement leur rapport plutôt que chacun individuellement.
- **$X_5$ contrôle la nervosité**.
Si $T$ oscille autour de $X_5$, de petits changements de $T$ peuvent faire basculer $\mathrm{DIV}$ de 0 à 1 et amener le modèle à déverser soudainement la percolation dans le réservoir rapide.
Des valeurs bien au-dessus du stockage typique de $T$ produisent une réponse surtout lente; des valeurs bien en dessous donnent une réponse surtout rapide.
- **$X_6$ et $X_7$** sont les boutons de routage.
$X_6$ fixe l'échelle de temps de la récession rapide (les récessions de tempête typiques d'un bassin durent 2–10 jours) et $X_7$ allonge la voie lente (une récession du débit de base sur des semaines à des mois implique $X_7 \approx 10$–$30$).
- **La remontée capillaire $X_4$** n'est active qu'en régime sec.
Sur des bassins au sol durablement humide ($S \geq X_1$ la plupart du temps), $X_4$ fait à peine bouger la fonction objectif — attendez-vous à une identifiabilité faible.

## Formulation mathématique

### Initialisation

États fixes des réservoirs à $t = 0$ (depuis HOOPLA `ini_HydroMod19.m`) :

$$S_0 = 30 \text{ mm}, \quad R_0 = 0 \text{ mm}, \quad T_0 = 200 \text{ mm}$$

Le registre de délai fractionnaire $\{H_k\}$ a $n = \lceil X_8 \rceil + 1$ éléments, initialisés à zéro, avec les poids :

$$d_{n-2} = \frac{1}{X_8 - n + 3}, \quad d_{n-1} = 1 - d_{n-2}$$

### Mise à jour de l'humidité du sol

$$S \leftarrow S + P$$

### Percolation et remontée capillaire

Flux mutuellement exclusifs selon le seuil $X_1$ :

$$
I_s =
\begin{cases}
\dfrac{S}{X_2} \cdot \dfrac{S - X_1}{X_3} & \text{if } S \geq X_1 \\
0 & \text{if } S < X_1
\end{cases}
$$

$$
I_t =
\begin{cases}
0 & \text{if } S \geq X_1 \\
\dfrac{T}{X_4} \cdot (X_1 - S) & \text{if } S < X_1
\end{cases}
$$

$$S \leftarrow S + I_t - I_s$$

### Évapotranspiration

$$
E_s =
\begin{cases}
E & \text{if } S \geq X_1 \\
E \cdot \cos\!\left(\dfrac{\pi}{2} \cdot \dfrac{X_1 - S}{X_1}\right) & \text{if } S < X_1
\end{cases}
$$

$$S \leftarrow \max(0,\; S - E_s)$$

### Dissociation des écoulements

$$\mathrm{DIV} = \min\!\left(1,\; \frac{T}{X_5}\right)$$

$$T \leftarrow T + (1 - \mathrm{DIV}) \cdot I_s$$

$$R \leftarrow R + \mathrm{DIV} \cdot I_s$$

### Routage linéaire

$$Q_r = \frac{R}{X_6}, \quad R \leftarrow R - Q_r$$

$$Q_t = \frac{T}{X_6 \cdot X_7}, \quad T \leftarrow T - Q_t$$

### Routage par délai

$$Q = Q_r + Q_t$$

$$H_k \leftarrow H_{k+1} + d_k \cdot Q \quad \text{for } k = 0, 1, \ldots, n - 2$$

$$H_{n-1} \leftarrow d_{n-1} \cdot Q$$

$$Q_{\text{sim}} = \max(0,\; H_0)$$

## Références

Warmerdam, P. M. M., Kole, J., & Chormanski, J. (1997).
Modelling rainfall-runoff processes in the Hupselse Beek research basin.
*IHP-V Technical Documents in Hydrology*, 14, 155–160. UNESCO, Paris.

Perrin, C. (2000).
*Vers une amélioration d'un modèle global pluie-débit au travers d'une approche comparative*.
PhD dissertation, Institut National Polytechnique de Grenoble, France.
Annex 1, Fiche n°34 (WAGE), pp. 461–464.

Thiboult, A., Seiller, G., Poncelet, C., & Anctil, F. (2020).
The HOOPLA toolbox: a HydrOlOgical Prediction LAboratory.
*Hydrology and Earth System Sciences Discussions*.
