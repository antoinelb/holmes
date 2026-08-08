# HOLMES

**HydrOLogical Modeling Educational Software**

HOLMES est un outil web de modélisation hydrologique conçu pour l'enseignement de l'hydrologie opérationnelle.
Développé à l'Université Laval, Québec, Canada.

---

## Fonctionnalités

- **Pipeline de modélisation guidé** : stations → météo → modèle → calage → simulation → projection, avec une carte interactive des stations — chaque étape est documentée dans le [guide d'utilisation](guide/index.md)
- **Vingt modèles hydrologiques** : de GR4J à SACRAMENTO, tous documentés dans la section [concepts](concepts/index.md)
- **Modélisation de la neige** : modèle degré-jour CemaNeige avec bandes d'altitude multiples
- **Calage automatique** : algorithmes d'optimisation SCE-UA et DDS
- **Projections climatiques** : scénarios ClimEx et ESPO-G6-R2 téléchargés par station
- **Haute performance** : moteur de calcul en Rust intégré à Python

---

## Démarrage rapide

Installer HOLMES (Python ≥ 3.12) :

```bash
pip install holmes-hydro
```

Lancer le tableau de bord :

```bash
holmes run
```

Ouvrir le navigateur à [http://127.0.0.1:8000](http://127.0.0.1:8000).

La ligne de commande fournit aussi `holmes download` pour reconstruire les jeux de données publiés depuis leurs sources et `holmes experiment` pour lancer des expériences de calage en lot.

[:material-compass: Guide d'utilisation](guide/index.md){ .md-button .md-button--primary }
[:material-water: Concepts](concepts/index.md){ .md-button }
[:material-file-document: Journal des modifications](reference/changelog.md){ .md-button }

---

## Aperçu de l'architecture

HOLMES repose sur une architecture à trois niveaux :

| Niveau | Technologie | Rôle |
|--------|-------------|------|
| **Frontend** | JavaScript vanilla, D3.js, Leaflet | Interface web interactive |
| **Backend** | Python, Starlette, Uvicorn | Routage de l'API, chargement des données, orchestration |
| **Calcul** | Rust (holmes-rs), PyO3 | Modèles numériques haute performance |

La communication entre le frontend et le backend passe par des WebSockets pour des mises à jour en temps réel pendant le calage.

---

## Licence

HOLMES est publié sous la [licence MIT](reference/license.md).

## Liens

- [:fontawesome-brands-github: Dépôt GitHub](https://github.com/antoinelb/holmes)
- [:fontawesome-brands-python: Paquet PyPI](https://pypi.org/project/holmes-hydro/)
