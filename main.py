# -----------------------------------------------------------------------------
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
from utils.file_utils import charger_config_annotations, creer_backup_annotations, sauvegarder_annotations, charger_annotations 
from utils.geo_utils import creer_gpkg_complet, prepare_temp_gpkg
from utils.exif_utils import charger_exif_depuis_json, extraire_et_sauvegarder_exif 
from utils.image_utils import dessiner_annotations_sur_images, lister_images, redimens_image, dessiner_overlay, redresser_image_hero9_cached
from utils.annotation_utils import ajouter_annotation, modifier_annotation, supprimer_annotation, reinitialiser_annotations_image, calculer_angle_porte, creer_dataframe_annotations
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates
import fiona


def safe_index(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0

# --- CONFIGURATION DE LA PAGE STREAMLIT ---
st.set_page_config(layout="wide")

# --- INITIALISATION DES VARIABLES DE SESSION ---
# Initialisation du session_state pour selected_annotation
if "selected_annotation" not in st.session_state:
    st.session_state.selected_annotation = None
# Initialisation du session_state pour le clic dans l'image
if "last_click" not in st.session_state:
    st.session_state["last_click"] = None

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
    st.image("assets/Logo_photomapon_horizontal_VF_02.svg", use_container_width=True)
    st.sidebar.markdown("_Ce logiciel est libre, vous pouvez le modifier et le redistribuer dans les conditions définies par la licence._ [GPL v3.0](https://www.gnu.org/licenses/gpl-3.0.html)")
    st.sidebar.markdown("[Documentation du projet](https://carteetliens.github.io/photomapon/)")
    st.sidebar.markdown("---")
    # Saisie du FOV utilisateur
    fov_user = st.number_input("Champ de vision (FOV en degrés)", min_value=70.0, max_value=180.0,
                                 value=104.6, step=0.1, key="fov_input")
    
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
    if st.button("🔄 Recharger la configuration YAML", use_container_width=True):
        st.rerun()
    
        # --- Bouton pour forcer la régénération
    if st.button("💾 Recalculer les EXIF des images", use_container_width=True):
        with st.spinner("Extraction des données EXIF..."):
            exif_data = extraire_et_sauvegarder_exif(image_folder, exif_output_file, reset=True)
        st.success("EXIF recalculées et sauvegardées.")
        st.cache_data.clear()  # important pour forcer le rechargement
        st.rerun()

    # Réinitialiser les annotations sur l'image
    if st.button("🗑️ Réinitialiser l'image actuelle", use_container_width=True) and image_files:
        current_img = image_files[st.session_state.current_image_index]
        reinitialiser_annotations_image(current_img, annotations_file, st.session_state)        
        sauvegarder_annotations(annotations_file, st.session_state.annotations)
        st.rerun()
    
    # Navigation entre les images
    st.markdown("### Navigation")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("◀️ Précédente", use_container_width=True) and image_files:
            st.session_state.current_image_index = (st.session_state.current_image_index - 1) % len(image_files)
            st.rerun()
    with col_nav2:
        if st.button("Suivante ▶️", use_container_width=True) and image_files:
            st.session_state.current_image_index = (st.session_state.current_image_index + 1) % len(image_files)
            st.rerun()

    st.markdown("### Traitement final")
    # Import d'un GeoPackage existant et sélection de la couche
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
    if st.button("🗺️ Cartographier les éléments 🗺️", use_container_width=True):
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
                    creer_gpkg_complet(annotations_json, exif_json, st.session_state["tmp_gpkg_path"], gpkg_output, image_folder, selected_layer)
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
    # Chargement de l'image courante et de ses dimensions
    current_img_idx = st.session_state.get("current_image_index", 0)
    image_name = image_files[current_img_idx]
    img_path = os.path.join(image_folder, image_name)
    img_fullres = Image.open(img_path).convert("RGBA")
    full_width, full_height = img_fullres.size
    # Redimensionnement de l'image pour affichage (max 800px de large)
    display_img, ratio = redimens_image(img_fullres, max_width=800)
    # Initialisation de la liste d'annotations pour l'image si besoin
    if image_name not in st.session_state.annotations:
        st.session_state.annotations[image_name] = []
    # Dataframe annotations
    df_annotations = creer_dataframe_annotations(st.session_state.annotations[image_name])
    # Overlay sur les images
    overlay = dessiner_overlay(display_img, st.session_state.annotations[image_name], df_annotations, ratio, st.session_state.get("selected_annotation"), fov_user)
    # Affichage de l'image annotée et récupération du clic utilisateur
    col1, col2 = st.columns([2, 1])
    with col1:
        click_key = f"main_image_{st.session_state.get('click_count', 0)}"
        merged_img = Image.alpha_composite(display_img, overlay)
        coords = streamlit_image_coordinates(merged_img, key="click_key", width=800)
        st.text(image_name)

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
    
    # --- AJOUT D'UNE ANNOTATION SI CLIC UTILISATEUR ---
    if coords:
        x_orig = int(coords["x"] / ratio)
        y_orig = int(coords["y"] / ratio)
        current_click = (x_orig, y_orig)
        angle_ajuste = calculer_angle_porte(x_orig, full_width, direction, fov=fov_user)
        # Ajoute l'annotation si ce n'est pas un doublon, puis sauvegarde et rafraîchit
        if ajouter_annotation(st.session_state.annotations, image_name,x_orig, y_orig, st.session_state.get("type_objet_selectbox_create"), st.session_state.get("fonction_objet_selectbox_create"), st.session_state.get("mode_annotation_selectbox"), angle_ajuste,st.session_state["last_click"]):
                # Sauvegarder dans le fichier JSON
                sauvegarder_annotations(annotations_file, st.session_state.annotations)
                # Mémoriser ce dernier clic comme déjà traité
                st.session_state["last_click"] = current_click
                st.rerun()
    
    with col2:
        # --- AFFICHAGE DU TABLEAU DES ANNOTATIONS ---
        st.markdown("### Tableau des annotations")
        if not df_annotations.empty:
            st.dataframe(df_annotations, use_container_width=True, hide_index=True)
            # Liste des index avec None pour "aucune sélection"
            index_options = [None] + list(df_annotations['index'])

            # Fonction de formatage pour l'affichage du selectbox
            def format_option(idx):
                if idx is None:
                    return "Sélectionnez une annotation"
                row = df_annotations[df_annotations['index'] == idx].iloc[0]
                return f"{idx} - {row['type_objet']} - {row['fonction_objet']}"
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

            # Boutons pour modifier ou supprimer l'annotation sélectionnée
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📝 Modifier", key=f"modify_{st.session_state.selected_annotation}", use_container_width=True):
                    if modifier_annotation(
                        st.session_state.annotations,
                        image_name,
                        st.session_state.selected_annotation,
                        type_objet_edit,
                        fonction_objet_edit,
                        mode_annotation_edit
                    ):
                        sauvegarder_annotations(annotations_file, st.session_state.annotations)
                        st.success("Modifications appliquées")
                        st.rerun()

            with col2:
                if st.button("🗑️ Supprimer", key=f"delete_{st.session_state.selected_annotation}", use_container_width=True):
                    if supprimer_annotation(
                            st.session_state.annotations,
                            image_name,
                            st.session_state.selected_annotation
                        ):
                        sauvegarder_annotations(annotations_file, st.session_state.annotations)
                        st.success("Annotation supprimée")
                        st.session_state.selected_annotation = None
                        st.rerun()
else:
    st.markdown("---")