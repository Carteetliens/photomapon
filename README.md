# Photo'Mapon | Carte et Liens – Application d’annotations de photos et de cartographie automatisée

## Description rapide

Cette application développée par Joseph Jacquet | [Carte et Liens](www.carteetliens.fr) permet :
- d’annoter des photos (objets),
- de générer automatiquement un GeoPackage contenant les éléments annotés soit par cartographie, soit par une mise à jour des géométries de la table du GPKG de référence (fourni par l'utilisateur)

L’outil a été conçu pour un traitement 100 % Python, sans base de données, compatible avec une utilisation locale.

---
## Licences des bibliothèques tierces

Ce projet utilise les bibliothèques suivantes :

| Bibliothèque                 | Licence            | Remarques |
|-----------------------------|--------------------|-----------|
| streamlit                   | Apache 2.0         | Compatible avec GPL |
| streamlit_image_coordinates | MIT                | Compatible avec GPL |
| pandas                      | BSD 3-Clause       | Compatible avec GPL |
| geopandas                   | BSD 3-Clause       | Compatible avec GPL |
| shapely                     | BSD 3-Clause       | Compatible avec GPL |
| pyproj                      | MIT                | Compatible avec GPL |
| pillow (PIL)                | MIT-CMU            | Compatible avec GPL |
| scipy                       | BSD                | Compatible avec GPL |
| fiona                       | BSD 3-Clause       | Compatible avec GPL |


La liste complète des dépendances figure dans le fichier `requirements.txt`.

## Installation des dépendances

Assurez-vous d’utiliser Python 3.10+

---

```bash
pip install -r requirements.txt
```
---

## Lancer l’interface

Depuis le dossier du projet :
```bash
streamlit run main.py
```

Optionnel : vous pouvez également excuter launch.bat (racine du dossier) pour automatiser le lancement

@echo off
streamlit run [cheminvers-main.py]/main.py
pause

[Voir la documentation](https://carteetliens.github.io/photomapon/) pour commencer à utiliser l'interface

## Données testes

📸 **Images de test** : voir le fichier [CREDITS.md](./CREDITS.md)


## Licence

Ce projet est publié sous la licence GNU GPL v3.
Cela signifie que toute personne réutilisant ou modifiant ce code doit publier ses modifications sous la même licence, garantissant ainsi un partage équitable et ouvert.
Pour plus de détails, consultez le fichier LICENSE.


## Contribuer

Vous pouvez contribuer au projet en :
    proposant des pull requests (corrections, améliorations, nouvelles fonctionnalités),
    signalant des bugs ou des demandes via les issues GitHub,
    proposant des optimisations du pipeline géospatial.

Avant de contribuer, merci de respecter les bonnes pratiques de style et de nommage déjà en place dans le projet.


## Contact

Projet développé par Joseph Jacquet - Carte et Liens - 2025

Pour toute question, suggestion ou demande professionnelle :
contact@carteetliens.fr |
[Carte et Liens](www.carteetliens.fr)