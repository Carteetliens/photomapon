# -----------------------------------------------------------------------------
# Version 1.1 PhotoMapon
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (main.py) Application Streamlit pour l’annotation d’images et cartographie
# -----------------------------------------------------------------------------

# --- IMPORTS ET FONCTIONS UTILES ---
# Import des modules nécessaires (traitements, UI, utilitaires, etc.)
import os
from datetime import datetime
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import json
import fiona
from utils.file_utils import charger_config_annotations, get_mapping_yaml_if_exists, sauvegarder_annotations, charger_annotations 
from utils.geo_utils import creer_gpkg_complet, prepare_temp_gpkg
from utils.exif_utils import charger_exif_depuis_json, extraire_et_sauvegarder_exif 
from utils.image_utils import dessiner_annotations_sur_images, lister_images, redimens_image, dessiner_overlay, redresser_image_hero9_cached, is_360_photo
from utils.annotation_utils import ajouter_annotation, modifier_annotation, supprimer_annotation, reinitialiser_annotations_image, pannellum_to_metier, prepare_hotspots_for_pannellum, creer_dataframe_annotations_360,  calculer_angle_objet, calculer_fov_vertical,calculer_angle_elevation, creer_dataframe_annotations
from PIL import Image
from visu360.visu360 import pannellum_viewer

def safe_index(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0

# Streamlit — Photomapon INTERFACE (main.py)

# Responsabilités :
# - Chargement d'un dossier d'images et des métadonnées EXIF (exif_data.json)
# - Interface d'annotation (photos 360° via Pannellum et photos standards via streamlit_image_coordinate)
# - Sauvegarde des annotations dans un fichier JSON (annotations.json)
# - Export cartographique vers un GPKG

# Formats clés :
# - annotations.json : { "<image_name>": [ { "uuid": str, "x": int, "y": int, "yaw": float, "pitch": float,
#    "type_objet": str, "fonction_objet": str, "mode_annotation": str, "date": ISO8601, ... }, ... ], ... }
# - exif_data.json : mapping image_name -> { "lat": float, "lon": float, "direction": float, "format": str, "date_time": str }

# Attention :
# - st.session_state est utilisé pour stocker l'état UI et commandes JS (cmd_action/cmd_data).
# - Voir le bloc "SESSION_STATE KEYS" ci‑dessous pour la sémantique de chaque clé.


# SESSION_STATE KEYS (documentation rapide)
# - selected_annotation: str|None -> UUID de l'annotation sélectionnée dans l'UI (tableau / Pannellum).
# - last_click: tuple[int,int]|None -> Coordonnées du dernier clic traité (empêche doublons).
# - cmd_action: str|None -> Commande envoyée au viewer 360 (ex: "update", "delete", "clear_all").
# - cmd_data: dict|None -> Données associées à cmd_action (ex: {"uuid": "...", "yaw":..., "pitch":..., "hfov":...}).
# - selected_uuid: str|None -> Clé historique / potentiellement redondante avec selected_annotation.
# - last_image_folder: str|None -> Dossier chargé précédemment (servir à détecter changement de dossier).
# - annotations: dict -> Mapping image_name -> list[annotation dict] (in memory, sauvegardé dans annotations.json).
# - current_image_index: int -> Index de l'image affichée.
# - fov_input: float -> Valeur FOV saisie par l'utilisateur (key du number_input).
# - mode_annotation_selectbox / mode_annotation_selectbox_edit: str -> Valeurs des selectbox (création / édition).
# - type_objet_selectbox_create / type_objet_selectbox_edit: str
# - fonction_objet_selectbox_create / fonction_objet_edit: str
# - decalage_orientation: int ->  Décalage d'orientation utilisateur (key du number_input).
# - gpkg: UploadedFile (key du file_uploader)
# - tmp_gpkg_path: str -> Chemin du gpkg temporaire créé par prepare_temp_gpkg (à nettoyer après usage).
# - pannellum_yaw / pannellum_pitch / pannellum_hfov: float -> État du viewer 360 maintenu entre rerun.
# - _rerun_once: bool -> Flag temporaire pour éviter boucle rerun lors de MAJ venant du JS.
# - reset_search_field: bool -> Flag pour réinitialiser proprement le champ de recherche après rerun.

# Notes :
# - Documenter chaque nouvelle clé, qui l'initialise et quand la supprimer.

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(layout="wide")

# --- INITIALISATION DES VARIABLES DE SESSION ---
# Initialisation du session_state pour selected_annotation
if "selected_annotation" not in st.session_state:
    st.session_state.selected_annotation = None
# Initialisation du session_state pour le clic dans l'image
if "last_click" not in st.session_state:
    st.session_state["last_click"] = None
# Initialisation du session_state pour l'action à affectuer par le JS
if "cmd_action" not in st.session_state:
    st.session_state.cmd_action = None
# Initialisation du session_state des données pour le JS
if "cmd_data" not in st.session_state:
    st.session_state.cmd_data = None

# --- SAISIE DU CHEMIN DU DOSSIER IMAGES ---
image_folder = st.text_input(
    "Copiez le chemin du dossier contenant les images")

# --- CHEMIN DU FICHIER D'ANNOTATIONS ---
annotations_file = os.path.join(image_folder, "annotations.json")

# --- GESTION DU RECHARGEMENT DES ANNOTATIONS SI CHANGEMENT DE DOSSIER ---
if "last_image_folder" not in st.session_state:
    st.session_state.last_image_folder = None

if image_folder and os.path.exists(image_folder):
    if image_folder != st.session_state.last_image_folder:
        # Nouveau dossier : on recharge les annotations
        if os.path.exists(annotations_file):
            try:
                st.session_state.annotations = charger_annotations(annotations_file)
            except Exception as e:
                st.warning(f"⚠️ Erreur lors du chargement des annotations : {e}")
                st.session_state.annotations = {}
        else:
            st.session_state.annotations = {}
        st.session_state.last_image_folder = image_folder
    elif "annotations" not in st.session_state:
        # Premier chargement des annotations si elles n'existent pas encore en session
        if os.path.exists(annotations_file):
            try:
                st.session_state.annotations = charger_annotations(annotations_file)
            except Exception as e:
                st.warning(f"⚠️ Erreur lors du chargement des annotations : {e}")
                st.session_state.annotations = {}
        else:
            st.session_state.annotations = {}
else:
    # Si le dossier n'existe pas, on réinitialise les annotations
    st.session_state.annotations = {}
    st.session_state.last_image_folder = None

if "annotations" not in st.session_state:
    st.session_state.annotations = {}

# --- LISTE DES FICHIERS IMAGE DU DOSSIER ---
image_files = lister_images(image_folder)

# --- GÉNÉRATION AUTOMATIQUE DU FICHIER EXIF SI ABSENT ---
exif_output_file = os.path.join(image_folder, "exif_data.json")
if image_folder and image_files and not os.path.exists(exif_output_file):
    extraire_et_sauvegarder_exif(image_folder, exif_output_file)

exif_data = {}
if os.path.exists(exif_output_file):
    with open(exif_output_file, "r", encoding="utf-8") as f:
        exif_data = json.load(f)

#if "backup_created" not in st.session_state:
#    creer_backup_annotations(annotations_file)
#    st.session_state.backup_created = True

# --- INITIALISATION DE L'INDEX DE L'IMAGE COURANTE ---
if "current_image_index" not in st.session_state:
    st.session_state.current_image_index = 0

# --- CHARGEMENT DE LA CONFIGURATION YAML DES ANNOTATIONS ---
config_file = os.path.join(image_folder, "annotations_config.yaml")
try:
    config = charger_config_annotations(config_file)
except Exception:
    config = {}

# --- SIDEBAR STREAMLIT : PARAMÈTRES, NAVIGATION, OUTILS ---
with st.sidebar:
    # Affichage du logo
    st.image("assets/Logo_photomapon_horizontal_VF_02.svg", width='stretch')
    st.sidebar.markdown("_Ce logiciel est libre, vous pouvez le modifier et le redistribuer dans les conditions définies par la licence._ [GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html)")
    st.sidebar.markdown("[Documentation du projet](https://carteetliens.github.io/photomapon/)")
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Pour les photos standards")
    # Saisie du FOV utilisateur
    fov_user = st.number_input("Champ de vision (FOV en degrés)", min_value=30.0, max_value=180.0,
                                 value=104.6, step=0.1, key="fov_input")
    # Saisie du décalage vertical de la photo par l'utilisateur
    #offset_vertical_deg = st.number_input("Décalage vertical (+/-30°)", min_value=-30.0, max_value=30.0, value=0.0, step=0.5, key="offset_vertical")

    st.sidebar.markdown("---")
    # Sélection des paramètres d'annotation si config chargée
    if "annotations" in config:
        mode_annotations = list({c for details in config["annotations"].values() for c in details["mode_annotation"]})
        mode_annotation = st.selectbox("Mode d'annotation", mode_annotations, key="mode_annotation_selectbox")
        filtered_type_objets = [lbl for lbl, d in config["annotations"].items() if mode_annotation in d["mode_annotation"]]
        type_objet = st.selectbox("Type d'objet", filtered_type_objets, key="type_objet_selectbox_create")
        fonction_objet = st.selectbox(
            "Type d'utilisation",
            config["annotations"][type_objet].get("fonction_objet", []),
            key="fonction_objet_selectbox_create"
        )
    else:
        st.warning("⚠️ La configuration des annotations n’a pas été chargée. Assurez-vous qu'il soit dans votre dossier photo")
    
    mode_annotation = st.session_state.get("mode_annotation_selectbox")
    type_objet = st.session_state.get("type_objet_selectbox_create")
    fonction_objet = st.session_state.get("fonction_objet_selectbox_create")

    # Raccourcis pour recharger la config ou réinitialiser les annotations de l'image courante
    if st.button("🔄 Recharger la configuration YAML", width='stretch'):
        st.rerun()
    
        # --- Bouton pour forcer la régénération
    if st.button("💾 Recalculer les EXIF des images", width='stretch'):
        with st.spinner("Extraction des données EXIF..."):
            exif_data = extraire_et_sauvegarder_exif(image_folder, exif_output_file, reset=True)
        st.success("EXIF recalculées et sauvegardées.")
        st.cache_data.clear()  # important pour forcer le rechargement
        st.rerun()
    
    
    st.sidebar.markdown("---")
    st.markdown("### Traitement final")

    # Initialisation des variables
    #hauteur_cam = None
    decalage_orientation = None
    # Definie la valeur du décalage de l'orientation de la photo (parfois 0° = Est donc 90 parfois 0° = Nord donc 0)
    decalage_orientation = st.number_input("**Objectif** : _Appliquer un décalage pour un référentiel 0° = Nord (0 = pas de décalage nécessaire - 90 = passage à 0° au Nord si référentiel à l'Est)_", min_value=0, max_value=180,
                                value=0, step=1, key="decalage_orientation")
    ancien_gpkg_file = st.file_uploader("Sélectionner le GeoPackage source (.gpkg, EPSG:2154)", type=["gpkg"], key="gpkg")
    selected_layer = None
    gdf = None

    if ancien_gpkg_file:
        # Prépare le temporaire via le module utilitaire
        ancien_gpkg_path = prepare_temp_gpkg(ancien_gpkg_file, st.session_state)
        # Lister les couches
        layers = fiona.listlayers(ancien_gpkg_path)
        selected_layer = st.selectbox("Choisissez la couche à utiliser", layers)

    st.sidebar.markdown("---")
    # Bouton de lancement du traitement cartographique
    if st.button("🗺️ Cartographier les éléments 🗺️", width='stretch'):
        if ancien_gpkg_file:
            with st.spinner("Traitement en cours..."):
                try:
                    # Construction des chemins et lancement des traitements
                    # Récupérer la date actuelle pour le nom du fichier
                    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    # Définir les chemins nécessaires
                    annotations_json = os.path.join(image_folder, "annotations.json")
                    exif_json = os.path.join(image_folder, "exif_data.json")
                    dossier_resultat = os.path.join(image_folder, 'resultat')
                    nom_base = os.path.splitext(os.path.basename(ancien_gpkg_file.name))[0]
                    gpkg_output = os.path.join(dossier_resultat, f"{nom_base}_{date_str}.gpkg")

                    # Appel des fonctions
                    dessiner_annotations_sur_images(image_folder)
                    creer_gpkg_complet(annotations_json, exif_json, st.session_state["tmp_gpkg_path"], gpkg_output, image_folder, selected_layer, decalage_orientation)
                    st.success("Traitement terminé avec succès.")

                except Exception as e:
                    st.error("Une erreur est survenue pendant l'exécution du script.")
                    st.code(str(e))

                finally:
                    # Nettoyage du fichier temporaire
                    tmp_path = st.session_state.pop("tmp_gpkg_path", None)
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
        else:
            st.warning("Veuillez sélectionner tous les fichiers requis ci-dessus.")
    # Infos de contact
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Contact**")
    st.sidebar.markdown("""Joseph JACQUET""") 
    st.sidebar.markdown("""contact@carteetliens.fr""")
    st.sidebar.markdown("""www.carteetliens.fr""")

# --- AFFICHAGE PRINCIPAL : IMAGE, ANNOTATIONS, TABLEAU ---
if image_files:
    current_img_idx = st.session_state.get("current_image_index", 0)
    image_name = image_files[st.session_state.current_image_index]
    total_images = len(image_files)
    current_idx = st.session_state.current_image_index + 1  # pour un affichage humain (1 au lieu de 0)

    img_path = os.path.join(image_folder, image_name)
    img_fullres = Image.open(img_path).convert("RGBA")
    full_width, full_height = img_fullres.size


    # Redimensionnement de l'image pour affichage (max 800px de large)
    display_img, ratio = redimens_image(img_fullres, max_width=800)
    # Initialisation de la liste d'annotations pour l'image si besoin
    if image_name not in st.session_state.annotations:
        st.session_state.annotations[image_name] = []
    
    # --- Barre de recherche directe vers une image ---
    col_a1, col_a2 = st.columns([2, 4], vertical_alignment="bottom")
    with col_a1:
        # Zone de recherche par nom de photo + nom de la photo + n°x/x photos dans le dossier
        search_term = st.text_input(
            f"**{image_name} ( {current_idx} / {total_images} )**",
            key="image_search_input",
            placeholder=f"Recherche par nom de photo - Exemple : IMG_0150 ou façade_nord"
        )
    with col_a2:
        go_button = st.button("🔍")

    # Recherche déclenchée uniquement si bouton pressé
    if go_button and search_term:
        term = search_term.strip().lower()
        matching = [img for img in image_files if term in img.lower()]

        if len(matching) == 1:
            # une seule correspondance : on met à jour l'image courante
            target_image = matching[0]
            st.session_state.current_image_index = image_files.index(target_image)
            st.session_state["reset_search_field"] = True
            st.rerun()
        elif len(matching) > 1:
            st.info(f"🔎 {len(matching)} images correspondent, précisez davantage.")
        else:
            st.warning("❌ Aucune image correspondante trouvée.")

    # Réinitialisation propre du champ après le rerun
    if "reset_search_field" in st.session_state:
        del st.session_state["reset_search_field"]

    # --- CHARGEMENT ET AFFICHAGE DES MÉTADONNÉES EXIF ---
    if image_folder:
        exif_output_file = os.path.join(image_folder, "exif_data.json")

        # Vérifie la présence du fichier EXIF JSON et charge les métadonnées
        if os.path.exists(exif_output_file):
            image_name = image_files[st.session_state.current_image_index]
            lat, lon, direction, image_format, date_time = charger_exif_depuis_json(image_name, exif_output_file)
            if lat is None:
                st.warning(f"Les EXIF pour {image_name} ne sont pas disponibles dans le fichier JSON.")
        else:
            st.error(f"Le fichier {exif_output_file} n'existe pas.")
            
    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        
        # Condition d'affichage auto si photo 360° ou photo standard
        # VISIONNEUSE PHOTO 360°
        if is_360_photo(full_width, full_height):
            # Dataframe annotations
            df_annotations = creer_dataframe_annotations_360(st.session_state.annotations[image_name])
            # Préparer la liste des hotspots au format attendu par le composant
            yaw = st.session_state.get("pannellum_yaw", 0)
            pitch = st.session_state.get("pannellum_pitch", 0)
            hfov = st.session_state.get("pannellum_hfov", 110)
            hotspots_for_image = prepare_hotspots_for_pannellum(st.session_state.annotations, image_name)

            # Définission du viewer Pannelum
            updated_hotspots = pannellum_viewer(
                image_path=img_path,
                pitch=pitch,
                yaw=yaw,
                hfov=hfov,
                height=600,
                mode_annotation=mode_annotation,
                type_objet=type_objet,
                fonction_objet=fonction_objet,
                hotspots=hotspots_for_image,
                img_width=full_width,
                img_height=full_height,
                selected_uuid=st.session_state.get("selected_annotation"),
                cmd_action=st.session_state.get("cmd_action"),
                cmd_data=st.session_state.get("cmd_data"),
                direction=locals().get("direction", 0),
                key=f"pannellum_{image_name}",
            )

            # --- Mise à jour des annotations si changements ---
            if direction is not None:
                if updated_hotspots and 'hotspots' in updated_hotspots:
                    new_annotations = [pannellum_to_metier(hs, direction) for hs in updated_hotspots['hotspots']]
                    current_annotations = st.session_state.annotations.get(image_name, [])

                    # On écrase uniquement si les annotations ont vraiment changé
                    if new_annotations != current_annotations:
                        st.session_state.annotations[image_name] = new_annotations
                        sauvegarder_annotations(annotations_file, st.session_state.annotations)

                        # Mettre à jour la vue Pannellum
                        st.session_state.pannellum_yaw = updated_hotspots.get('yaw', 0)
                        st.session_state.pannellum_pitch = updated_hotspots.get('pitch', 0)
                        st.session_state.pannellum_hfov = updated_hotspots.get('hfov', 110)

                        # Réinitialiser les commandes inutiles
                        st.session_state.cmd_action = None
                        st.session_state.cmd_data = None

                        # Flag pour ne rerun qu'une seule fois
                        st.session_state._rerun_once = True
                        st.rerun()
            
            # Reset du flag si présent
            if st.session_state.get("_rerun_once"):
                st.session_state._rerun_once = False
            elif direction is None:
                st.warning(f"La direction n'est pas présente dans les EXIF pour {image_name}. Aucune annotation ne sera enregistrée dans le JSON.")
        else:
            # VISIONNEUSE PHOTO STANDARD
            # Dataframe annotations
            df_annotations = creer_dataframe_annotations(st.session_state.annotations[image_name])
            # Overlay sur les images
            overlay = dessiner_overlay(display_img, st.session_state.annotations[image_name], df_annotations, ratio, st.session_state.get("selected_annotation"), fov_user)
            # Affichage de l'image annotée et récupération du clic utilisateur
            merged_img = Image.alpha_composite(display_img, overlay)
            # Visionneuse photo standard
            coords = streamlit_image_coordinates(merged_img, key="click_key", width=800)
            # Ajout d'une annotation si clic utilisateur
            if direction is not None:
                if coords:
                    x_orig = int(coords["x"] / ratio)
                    y_orig = int(coords["y"] / ratio)
                    current_click = (x_orig, y_orig)
                    angle_ajuste = calculer_angle_objet(x_orig, full_width, direction, fov=fov_user)
                    fov_vertical = calculer_fov_vertical(fov_user, full_width, full_height)
                    angle_vertical = calculer_angle_elevation(y_orig, full_height, fov_vertical)
                    # Ajoute l'annotation si ce n'est pas un doublon, puis sauvegarde et rafraîchit
                    if ajouter_annotation(st.session_state.annotations, image_name,x_orig, y_orig, st.session_state.get("type_objet_selectbox_create"), st.session_state.get("fonction_objet_selectbox_create"), st.session_state.get("mode_annotation_selectbox"), angle_ajuste, angle_vertical ,st.session_state["last_click"]):
                            # Sauvegarder dans le fichier JSON
                            sauvegarder_annotations(annotations_file, st.session_state.annotations)
                            # Mémoriser ce dernier clic comme déjà traité
                            st.session_state["last_click"] = current_click
                            st.rerun()
            elif direction is None:
                st.warning(f"La direction n'est pas présente dans les EXIF pour {image_name}. Aucune annotation ne sera enregistrée dans le JSON.")
        # Navigation entre les images
        col_nav1, col_nav2 = st.columns(2)
        with col_nav1:
            if st.button("◀️ Précédente", width='stretch') and image_files:
                st.session_state.current_image_index = (st.session_state.current_image_index - 1) % len(image_files)
                st.rerun()
        with col_nav2:
            if st.button("Suivante ▶️", width='stretch') and image_files:
                st.session_state.current_image_index = (st.session_state.current_image_index + 1) % len(image_files)
                st.rerun()
            
    # Affichage des informations EXIF si disponibles
    if lat is not None and lon is not None:
        if "data_test" in image_folder:
            st.markdown("© Panoramax / StephaneP / CC-BY-SA")
        st.markdown("### Informations EXIF :")
        st.markdown(f"📅 **Date :** {date_time if date_time else 'Non disponible'}")
        st.markdown(f"🌍 **Latitude :** {lat} | **Longitude :** {lon}")
        st.markdown(f"🧭 **Orientation :** {round(float(direction), 4)}°" if direction is not None else "🧭 **Orientation :** Non disponible")
        st.markdown(f"🖼️ **Format :** {image_format}")
    else:
        st.write("Les métadonnées EXIF ne sont pas disponibles pour cette image.")  
  
    with col_b2:
        # --- AFFICHAGE DU TABLEAU DES ANNOTATIONS ---
        st.markdown("### Tableau des annotations")
        if not df_annotations.empty:
            st.dataframe(df_annotations, width='stretch', hide_index=True)
            # Liste des index avec None pour "aucune sélection"
            index_options = [None] + list(df_annotations['index'])

            # Fonction de formatage pour l'affichage du selectbox
            def format_option(idx):
                if idx is None:
                    return "Sélectionnez une annotation"
                row = df_annotations[df_annotations['index'] == idx].iloc[0]
                return f"{idx} - {row['type_objet']} - {row['fonction_objet']}"
            
            # Réinitialiser les annotations sur l'image
            if st.button("🗑️ Réinitialiser l'image actuelle", key=f"clearall_{st.session_state.selected_annotation}", width='stretch') and image_files:
                if is_360_photo(full_width, full_height):
                    st.session_state.cmd_action = "clear_all"
                    st.rerun()
                else:
                    current_img = image_files[st.session_state.current_image_index]
                    reinitialiser_annotations_image(current_img, annotations_file, st.session_state)        
                    sauvegarder_annotations(annotations_file, st.session_state.annotations)
                    st.rerun()
            # Sélecteur d'annotation à modifier/supprimer
            selected_index = st.selectbox(
                "Sélectionner une annotation",
                options=index_options,
                format_func=lambda x: "Sélectionnez une annotation" if x is None else f"{x} - {df_annotations[df_annotations['index'] == x].iloc[0]['type_objet']}",
                key="selectbox_index"
            )
            # Mise à jour de selected_annotation dans le session_state
            if selected_index is not None:
                selected_uuid = df_annotations[df_annotations['index'] == selected_index].iloc[0]['uuid']
                if st.session_state.get("selected_annotation") != selected_uuid:
                    st.session_state.selected_annotation = selected_uuid
                    st.rerun()
            else:
                if st.session_state.get("selected_annotation") is not None:
                    st.session_state.selected_annotation = None
                    st.rerun()
       
        # --- MODIFICATION / SUPPRESSION D'UNE ANNOTATION SÉLECTIONNÉE ---
        if st.session_state.selected_annotation is not None:
            # Récupération de l'annotation sélectionnée à partir de son UUID
            ann_to_edit = next(
                (ann for ann in st.session_state.annotations[image_name]
                if ann["uuid"] == st.session_state.selected_annotation),
                None
            )
            if ann_to_edit:
                st.markdown("### Modifier l'annotation")
                # Sélection des nouveaux paramètres pour l'annotation
                mode_annotations = list({c for d in config["annotations"].values() for c in d["mode_annotation"]})
                idx = safe_index(mode_annotations, ann_to_edit["mode_annotation"])
                mode_annotation_edit = st.selectbox("Mode d'annotation", mode_annotations, index=idx, key="mode_annotation_selectbox_edit")

                # Type_objetS filtrés selon mode_annotation_edit
                filtered_type_objets = [
                    lbl for lbl, d in config["annotations"].items()
                    if mode_annotation_edit in d["mode_annotation"]
                ]
                idx = safe_index(filtered_type_objets, ann_to_edit["type_objet"])
                type_objet_edit = st.selectbox("Type d'objet", filtered_type_objets, index=idx, key="type_objet_selectbox_edit")

                # Types filtrés selon type_objet_edit
                types = config["annotations"][type_objet_edit]["fonction_objet"]
                idx = safe_index(types, ann_to_edit["fonction_objet"])
                fonction_objet_edit = st.selectbox(
                    "Type d'utilisation", types, index=idx, key="fonction_objet_edit"
                )

            # Boutons pour modifier ou supprimer l'annotation sélectionnée conditionner suivant le type de photo (360° ou standard)
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("📝 Modifier", key=f"modify_{st.session_state.selected_annotation}", width='stretch'):
                    # PHOTO 360°
                    if is_360_photo(full_width, full_height):
                        # Envoi de la commande "update" au composant JS
                        st.session_state.cmd_action = "update"
                        st.session_state.cmd_data = {
                            "uuid": st.session_state.selected_annotation,
                            "type_objet": type_objet_edit,
                            "fonction_objet": fonction_objet_edit,
                            "mode_annotation": mode_annotation_edit
                        }
                        st.success("Modifications appliquées")
                        st.rerun()
                    # PHOTO STANDARD
                    else:
                        modifier_annotation(
                            st.session_state.annotations,
                            image_name,
                            st.session_state.selected_annotation,
                            type_objet_edit,
                            fonction_objet_edit,
                            mode_annotation_edit
                        )
                        sauvegarder_annotations(annotations_file, st.session_state.annotations)
                        st.success("Modifications appliquées")
                        st.rerun()

            with col_c2:
                if st.button("🗑️ Supprimer", key=f"delete_{st.session_state.selected_annotation}", width='stretch'):
                    # PHOTO 360°
                    if is_360_photo(full_width, full_height):
                        st.session_state.cmd_action = "delete"
                        st.session_state.cmd_data = {
                            "uuid": st.session_state.selected_annotation,
                            "yaw": st.session_state.pannellum_yaw,      
                            "pitch": st.session_state.pannellum_pitch,    
                            "hfov": st.session_state.pannellum_hfov       
                        }
                        st.success("Annotation supprimée")
                        st.session_state.selected_annotation = None
                        st.rerun()
                    # PHOTO STANDARD
                    else:
                        supprimer_annotation(
                                st.session_state.annotations,
                                image_name,
                                st.session_state.selected_annotation
                            )
                        sauvegarder_annotations(annotations_file, st.session_state.annotations)
                        st.success("Annotation supprimée")
                        st.session_state.selected_annotation = None
                        st.rerun()
    st.markdown("---")