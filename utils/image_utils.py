# -----------------------------------------------------------------------------
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (image_utils.py) Fonctions utilitaires pour le traitement des images
# -----------------------------------------------------------------------------

from PIL import Image, ImageDraw, ImageFont
import os
import json
import cv2
import numpy as np
import streamlit as st

# Catalogue de couleurs pour les annotations
def couleur_rgba(couleur_nom, alpha=255):
    couleurs = {
        "red": (255, 0, 0, alpha),
        "blue": (0, 0, 255, alpha),
        "yellow": (255, 255, 0, alpha),
        # ajoute d’autres couleurs si besoin
    }
    return couleurs.get(couleur_nom, (0, 0, 0, alpha)) 


# Liste des images pour défilement
def lister_images(image_folder):
    return [f for f in os.listdir(image_folder) if f.lower().endswith(('png', 'jpg', 'jpeg'))] if os.path.isdir(image_folder) else []

# Création des photos annotées (images avec annotations)
def dessiner_annotations_sur_images(image_folder):
    # Images + annotations
    chemin_annotations = os.path.join(image_folder, 'annotations.json')
    dossier_resultat = os.path.join(image_folder, 'resultat')
    os.makedirs(dossier_resultat, exist_ok=True)

    # Charger les annotations
    with open(chemin_annotations, 'r', encoding='utf-8') as f:
        annotations = json.load(f)

    # Itérer les images
    for image_name, ann_list in annotations.items():
        chemin_image = os.path.join(image_folder, image_name)
        if not os.path.exists(chemin_image):
            print(f"Image {image_name} non trouvée, on saute.")
            continue

        # Charger l'image
        img = Image.open(chemin_image).convert("RGB")
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()

        for ann in ann_list:
            x, y = ann['x'], ann['y']
            type_objet = ann.get('type_objet', '')
            mode_annotation = ann.get('mode_annotation', '')
            type_util = ann.get('fonction_objet', '')

            # Texte combiné
            texte = f"{type_objet} - {type_util}" if type_util else type_objet

            couleur = "red" if mode_annotation == "cartographie" else "blue"
            try:
                font = ImageFont.truetype("bahnschrift.ttf", 40)
            except:
                font = ImageFont.load_default()
            draw.ellipse([(x - 20, y - 20), (x + 20, y + 20)], fill=couleur, outline=couleur)
            draw.text((x + 50, y - 50), texte, fill=couleur, font=font)

        # Sauvegarder l’image annotée
        nom_base, ext = os.path.splitext(image_name)
        image_annot_name = f"{nom_base}_annot{ext}"
        sortie_path = os.path.join(dossier_resultat, image_annot_name)        
        
        # Si l'image existe déjà dans le dossier résultat, la supprimer
        if os.path.exists(sortie_path):
            os.remove(sortie_path)
            print(f"Suppression de l'ancienne version : {sortie_path}")
        img.save(sortie_path)
        print(f"Image annotée enregistrée : {sortie_path}")

# Redimenssionnement de l'image
def redimens_image(img, max_width=800):
    full_width, full_height = img.size
    ratio = min(1, max_width / full_width)
    return img.resize((int(full_width * ratio), int(full_height * ratio))), ratio

# Overlay + annotations
def dessiner_overlay(display_img, annotations, df_annotations, ratio, selected_uuid, fov_user):
    from PIL import ImageDraw, ImageFont, Image
    overlay = Image.new("RGBA", display_img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    try:
        font = ImageFont.truetype("bahnschrift.ttf", 13)
    except:
        font = ImageFont.load_default()
    # Bande noire sur les côtés
    total_fov = fov_user
    target_fov = 70
    margin_ratio = (total_fov - target_fov) / (2 * total_fov)
    mask_width = int(margin_ratio * display_img.width)
    draw.rectangle([(0, 0), (mask_width, display_img.height)], fill=(0, 0, 0, 100))
    draw.rectangle([(display_img.width - mask_width, 0), (display_img.width, display_img.height)], fill=(0, 0, 0, 100))
    # Annotations
    for a in annotations:
        x_disp = int(a["x"] * ratio)
        y_disp = int(a["y"] * ratio)
        idx = df_annotations[df_annotations['uuid'] == a['uuid']].index[0] + 1
        text = f"{idx} {a['type_objet']} {a['fonction_objet']}"
        mode_annotation = a.get('mode_annotation', '')
        color = (255, 0, 0, 100) if mode_annotation == "cartographie" else (0, 0, 255, 100)
        text_color = (255, 0, 0, 100) if mode_annotation == "cartographie" else (0, 0, 255, 100)
        if a["uuid"] == selected_uuid:
            color = (255, 255, 0, 255)
            text_color = (255, 255, 0, 255)
            draw.text((x_disp + 10, y_disp - 10), text, fill=text_color, font=font)
            draw.ellipse((x_disp - 3, y_disp - 3, x_disp + 3, y_disp + 3), fill=color)
        else:
            draw.ellipse((x_disp - 3, y_disp - 3, x_disp + 3, y_disp + 3), fill=color)
            draw.text((x_disp + 10, y_disp - 10), text, fill=text_color, font=font,stroke_width=1.1,stroke_fill="white")
    return overlay

# Fonction test, en cours de développement
@st.cache_data
def redresser_image_hero9_cached(image_path):
    """
    Redresse une image GoPro HERO9 (cached).
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Image introuvable : {image_path}")
    h, w = img.shape[:2]
    fx = 2176
    fy = 2176
    cx = w / 2
    cy = h / 2
    K = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1]], dtype=np.float32)
    D = np.array([-0.34, 0.15, 0, 0], dtype=np.float32)
    new_K, _ = cv2.getOptimalNewCameraMatrix(K, D, (w, h), 1, (w, h))
    undistorted = cv2.undistort(img, K, D, None, new_K)
    undistorted_rgb = cv2.cvtColor(undistorted, cv2.COLOR_BGR2RGB)
    return Image.fromarray(undistorted_rgb).convert("RGBA")