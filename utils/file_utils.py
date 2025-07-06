# -----------------------------------------------------------------------------
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (file_utils.py) Fonctions utilitaires pour le traitement des fichiers
# -----------------------------------------------------------------------------

import json
import yaml
import os
import shutil
from datetime import datetime
import logging

# Configuration du logger global
def setup_logger(log_dir):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(log_dir, f"creation_gpkg_log_{date_str}.txt")

    # Crée un nom de logger unique par session
    logger_name = f"geo_utils_logger_{date_str}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Pas besoin de vérifier hasHandlers car le nom change à chaque fois
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Fonction chargement des annotations depuis le JSON
def charger_annotations(annotations_file):
    if os.path.exists(annotations_file):
        try:
            with open(annotations_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erreur de lecture JSON : {e}")
    return {}


# Chargement du fichier YAML pour les listes deroulantes
def charger_config_annotations(config_path):
    if not os.path.exists(config_path):
        raise FileNotFoundError("Fichier de configuration des annotations introuvable.")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# [Pas utilisé pour le moment] Creation d'un backup des annotations 
def creer_backup_annotations(annotations_file):
    """Crée une copie de sauvegarde du fichier annotations.json"""
    if os.path.exists(annotations_file):
        # Création du nom avec date/heure
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = annotations_file.replace('.json', f'_backup_{date_str}.json')
        try:
            shutil.copy2(annotations_file, backup_file)
            print(f"Backup créé : {backup_file}")
        except Exception as e:
            print(f"Erreur lors de la création du backup : {e}")

# Fonction sauvegarde annotations dans JSON
def sauvegarder_annotations(annotations_file, annotations):
    try:
        with open(annotations_file, "w", encoding="utf-8") as f:
            json.dump(annotations, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise IOError(f"Erreur lors de la sauvegarde des annotations : {e}")