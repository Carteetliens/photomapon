# -----------------------------------------------------------------------------
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (annotations_utils.py) Fonctions utilitaires pour le traitement des annotations
# -----------------------------------------------------------------------------

import uuid
import pandas as pd


# Fonction de calcul de l'angle ajusté de l'objet annoté
def calculer_angle_porte(x_orig, full_width, direction, fov):
    # Calculer l'angle de l'objet' en fonction de sa position
    center_x = full_width / 2
    relative_position = (x_orig - center_x) / center_x  # Normalisation
    object_angle = relative_position * (fov / 2)
    angle_ajuste = (direction + object_angle) % 360
    return angle_ajuste


# Fonction d'ajout d'annotation
def ajouter_annotation(annotations_dict, image_name, x, y, type_objet, fonction_objet, mode_annotation, angle_ajuste, last_click):
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
        "uuid": str(uuid.uuid4()),
        "x": x, "y": y,
        "type_objet": type_objet,
        "fonction_objet": fonction_objet,
        "mode_annotation": mode_annotation,
        "angle_ajuste": angle_ajuste
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