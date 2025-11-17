# -----------------------------------------------------------------------------
# Version 1.1 PhotoMapon
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (annotations_utils.py) Fonctions utilitaires pour le traitement des annotations
# -----------------------------------------------------------------------------

import uuid
import pandas as pd
import math
import json


def to_pannellum_yaw(angle):
    """Convertit un angle 0–360° en [-180, 180] pour Pannellum."""
    return ((angle + 180) % 360) - 180

def to_pannellum_pitch(angle):
    """Convertit un angle vertical 0–360° en [-90, 90] pour Pannellum."""
    if angle > 180:
        angle -= 360
    return max(min(angle, 90), -90)  # Sécurité

def normalize_0_360(angle):
    """Ramène un angle quelconque dans [0, 360)."""
    return (angle % 360)


def prepare_hotspots_for_pannellum(annotations_dict, image_name):
    print(f"Annotations raw for {image_name}:", annotations_dict.get(image_name, []))
    hotspots = []
    for ann in annotations_dict.get(image_name, []):
        print("Processing annotation:", ann)
        hotspots.append({
            "id": ann.get("uuid", ""),
            "pitch": ann.get("angle_vertical", 0),
            "yaw": ann.get("yaw_origine", 0),
            "modeAnnotation": ann.get("mode_annotation", ""),
            "typeObjet": ann.get("type_objet", ""),
            "fonctionObjet": ann.get("fonction_objet", ""),
            "x": ann.get("x"),
            "y": ann.get("y")
        })
    print(f"Hotspots prepared: {hotspots}")
    return hotspots

def pannellum_to_metier(hs, direction):
    """Convertit un hotspot Pannellum en annotation métier."""
    pitch = hs.get("pitch", 0)
    yaw = hs.get("yaw", 0)

    # Conversion yaw relatif → angle monde
    angle_ajuste = normalize_0_360(yaw + direction)
    return {
        "uuid": hs.get("id",generate_uuid()),  # UUID stable venant du front, sinon nouveau
        "mode_annotation": hs.get("modeAnnotation", ""),
        "type_objet": hs.get("typeObjet", ""),
        "fonction_objet": hs.get("fonctionObjet", ""),
        "yaw_origine" : hs.get("yaw"),
        "angle_ajuste": angle_ajuste,
        "angle_vertical": pitch,
        "x": hs.get("x", None),
        "y": hs.get("y", None) 
    }


def generate_uuid():
    return str(uuid.uuid4())

def calculer_fov_vertical(fov_user, full_width, full_height):
    """
    Calcule le FOV vertical en degrés à partir du FOV horizontal et des dimensions de l'image.
    """
    fov_rad = math.radians(fov_user / 2)
    ratio = full_height / full_width
    fov_vert_rad = 2 * math.atan(ratio * math.tan(fov_rad))
    return math.degrees(fov_vert_rad)

def calculer_angle_elevation(y_pixel, image_height, fov_vertical, offset_deg=0):
    """
    Calcule l'angle d'élévation (vertical) en degrés.
    0° = horizon, négatif = vers le bas, positif = vers le haut.
    """
    center_y = image_height / 2
    relative_position = (y_pixel - center_y) / center_y
    elevation_angle = -relative_position * (fov_vertical / 2) + offset_deg
    return elevation_angle

# Fonction de calcul de l'angle ajusté de l'objet annoté
def calculer_angle_objet(x_orig, full_width, direction, fov):
    # Calculer l'angle de l'objet' en fonction de sa position
    center_x = full_width / 2
    relative_position = (x_orig - center_x) / center_x  # Normalisation
    object_angle = relative_position * (fov / 2)
    angle_ajuste = (direction + object_angle) % 360
    return angle_ajuste

# Fonction d'ajout d'annotation photo classique
def ajouter_annotation(annotations_dict, image_name, x, y, type_objet, fonction_objet, mode_annotation, angle_ajuste, angle_vertical, last_click):
    """
    Ajoute une annotation si elle n'existe pas encore à ces coordonnées et si ce n'est pas un doublon immédiat.
    Retourne un booléen indiquant si une annotation a été ajoutée.
    """
    current_click = (x, y)

    if current_click == last_click:
        return False  # Doublon de clic

    if current_click in [(a["x"], a["y"]) for a in annotations_dict[image_name]]:
        return False  # Déjà annoté à ces coordonnées

    annotations_dict[image_name].append({
        "uuid": generate_uuid(),
        "x": x, "y": y,
        "type_objet": type_objet,
        "fonction_objet": fonction_objet,
        "mode_annotation": mode_annotation,
        "angle_ajuste": angle_ajuste,
        "angle_vertical": angle_vertical
    })

    return True


# Fonction de modification de l'annotation
def modifier_annotation(annotations_dict, image_name, uuid_cible, new_type, new_fonction, new_mode):
    """
    Modifie une annotation à partir de son UUID. Retourne True si modifié.
    """
    for ann in annotations_dict[image_name]:
        if ann["uuid"] == uuid_cible:
            ann.update({
                "type_objet": new_type,
                "fonction_objet": new_fonction,
                "mode_annotation": new_mode
            })
            return True
    return False

# Fonction de suppression de l'annotation
def supprimer_annotation(annotations_dict, image_name, uuid_cible):
    """
    Supprime une annotation à partir de son UUID. Retourne True si supprimée.
    """
    for i, ann in enumerate(annotations_dict[image_name]):
        if ann["uuid"] == uuid_cible:
            del annotations_dict[image_name][i]
            return True
    return False

# Selection d'annotation
def get_annotation_by_uuid(annotations_dict, image_name, uuid_cible):
    """
    Renvoie l’annotation correspondant à l’UUID, ou None si non trouvée.
    """
    return next((ann for ann in annotations_dict[image_name] if ann["uuid"] == uuid_cible), None)

# Supprime l'ensemble des annotations d'une image donnée
def reinitialiser_annotations_image(image_name: str, annotations_file: str, session_state):
    """
    Supprime toutes les annotations associées à une image donnée   
    Paramètres :
        image_name (str) : nom de l'image dont on réinitialise les annotations
        annotations_file (str) : chemin vers le fichier annotations.json
        session_state : st.session_state (ou son équivalent passé depuis main)
    """
    session_state.annotations[image_name] = []

# Création du Dataframe des annotations pour affichage dans l'interface
def creer_dataframe_annotations(annotations):
    df = pd.DataFrame(annotations)
    if not df.empty:
        df.reset_index(drop=True, inplace=True)
        df['index'] = df.index + 1
        ordered_columns = ['index', 'uuid', 'type_objet', 'fonction_objet', 'mode_annotation', 'x', 'y', 'angle_ajuste']
        df = df[ordered_columns]
    return df


def creer_dataframe_annotations_360(annotations):
    """
    Crée un DataFrame à partir des annotations photos 360°
    avec ajout de la colonne angle_vertical.
    """
    df = pd.DataFrame(annotations)
    if not df.empty:
        df.reset_index(drop=True, inplace=True)
        df['index'] = df.index + 1
        # Colonnes ordonnées, sans x et y, mais avec angle_vertical
        ordered_columns = [
            'index', 'uuid', 'type_objet', 'fonction_objet',
            'mode_annotation','x', 'y', 'angle_ajuste', 'angle_vertical'
        ]
        # Pour éviter erreur si certaines colonnes manquent
        columns_present = [col for col in ordered_columns if col in df.columns]
        df = df[columns_present]
    return df
