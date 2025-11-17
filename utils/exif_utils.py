# -----------------------------------------------------------------------------
# Version 1.1 PhotoMapon
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (exif_utils.py) Fonctions utilitaires pour l'extraction et le traitement des EXIF
# -----------------------------------------------------------------------------

from PIL import Image
import json
import os
import streamlit as st

# Traduction en float des fraction si besoin
def convertir_fraction(val):
    """Convertit une valeur EXIF fractionnaire ou simple en float."""
    # Cas tuple fractionnaire (num, den)
    if isinstance(val, tuple) and len(val) == 2:
        num, den = val
        return float(num) / float(den) if den else 0.0
    # Cas float/int ou IFDRational
    try:
        return float(val)
    except Exception:
        return 0.0

# Fonction de conversion DMS en degrés décimaux
def convertir_degres(dms):
    """Convertit un tuple/list de DMS EXIF en degrés décimaux, gère les fractions."""
    if isinstance(dms, (list, tuple)) and len(dms) == 3:
        deg = convertir_fraction(dms[0])
        min = convertir_fraction(dms[1])
        sec = convertir_fraction(dms[2])
        return deg + min / 60 + sec / 3600
    return None

# Fonction d'extraction des métadonnées EXIF utiles
def extraire_metadonnees(chemin_image):
    try:
        img = Image.open(chemin_image)
        exif_data = img._getexif()

        if not exif_data:
            return None, None, None, None, None

        gps_data = exif_data.get(34853, {})
        if not gps_data:
            return None, None, None, None, None

        lat = convertir_degres(gps_data[2]) if 2 in gps_data else None
        lon = convertir_degres(gps_data[4]) if 4 in gps_data else None
        if gps_data.get(1) == 'S' and lat is not None:
            lat = -lat
        if gps_data.get(3) == 'W' and lon is not None:
            lon = -lon

        direction = gps_data.get(17)
        if direction is not None:
            direction = convertir_fraction(direction)
        else:
            direction = None

        image_format = img.format
        date_time = exif_data.get(306)  # Date de prise de vue (Tag EXIF : 306)

        return lat, lon, direction, image_format, date_time

    except Exception as e:
        print(f"Erreur d'extraction EXIF: {e}")
        return None, None, None, None, None

# Fonction d'extraction des EXIF et sauvegarde dans un fichier JSON
def extraire_et_sauvegarder_exif(image_folder, exif_output_file, reset=False):
    # Vérifier si le fichier JSON existe déjà
    if os.path.exists(exif_output_file) and not reset:
        print(f"Le fichier {exif_output_file} existe déjà. Les EXIF seront chargées à partir du fichier JSON.")
        return {}  # Charger directement le fichier JSON
    else:
        # Si le fichier n'existe pas, extraire les EXIF depuis les images et les sauvegarder
        image_files = [f for f in os.listdir(image_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))]
        exif_data = {}

        for image_name in image_files:
            img_path = os.path.join(image_folder, image_name)

            lat, lon, direction, image_format, date_time  = extraire_metadonnees(img_path)

            # Forcer la conversion en float si nécessaire
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
            direction = float(direction) if direction is not None else None

            exif_data[image_name] = {
                "latitude": lat,
                "longitude": lon,
                "direction": direction,
                "image_format": image_format,
                "date_time": str(date_time) if date_time is not None else None
            }
        # Écriture des éléments dans le JSON
        with open(exif_output_file, "w", encoding="utf-8") as f:
            json.dump(exif_data, f, ensure_ascii=False, indent=2)

        print(f"Les données EXIF ont été sauvegardées dans le fichier {exif_output_file}.")
        return exif_data

@st.cache_data
# Fonction pour charger les EXIF depuis le fichier JSON
def charger_exif_depuis_json(image_name, exif_output_file):
    try:
        with open(exif_output_file, "r", encoding="utf-8") as f:
            exif_data = json.load(f)
        # Retourner les données EXIF pour l'image spécifiée
        if image_name in exif_data:
            return exif_data[image_name]["latitude"], exif_data[image_name]["longitude"], exif_data[image_name]["direction"], exif_data[image_name]["image_format"], exif_data[image_name]["date_time"]
        else:
            return None, None, None, None, None
    except Exception as e:
        print(f"Erreur de chargement des données EXIF : {e}")
        return None, None, None, None, None