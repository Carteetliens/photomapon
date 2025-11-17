# -----------------------------------------------------------------------------
# Version 1.1 PhotoMapon
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (geo_utils.py) Fonctions utilitaires pour les traitements géomatiques
# -----------------------------------------------------------------------------

import json
import tempfile
import math
import pyproj
from shapely.geometry import LineString, Point
import os
import geopandas as gpd
import numpy as np
import fiona
from scipy.spatial.distance import pdist, squareform
from shapely.geometry import LineString, Point
from utils.file_utils import setup_logger


# Fonction de conversion WGS84 → Lambert-93
def convertir_wgs84_vers_lambert93(lat, lon):
    wgs84 = pyproj.CRS('EPSG:4326')
    lambert93 = pyproj.CRS('EPSG:2154')
    transformer = pyproj.Transformer.from_crs(wgs84, lambert93, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return x, y

# Création de la ligne de vue (segment) à partir d’un point, d’un angle et d’une longueur
def creer_ligne_de_vue(x, y, angle_deg, decalage_orientation, longueur=150):
    """
    Création de la ligne de vue (segment) à partir d’un point, d’un angle et d’une longueur.
    
    :param x: Coordonnée x du point de départ
    :param y: Coordonnée y du point de départ
    :param angle_deg: Angle de la ligne de vue
    :param decalage_orientation: Décalage d'orientation à appliquer
    :param longueur: Longueur de la ligne de vue
    :return: LineString représentant la ligne de vue
    """
    # Appliquer le décalage d'orientation uniquement si nécessaire
    angle_rad = math.radians(decalage_orientation - angle_deg) if decalage_orientation > 0 else math.radians(-angle_deg)
    
    dx = math.cos(angle_rad) * longueur
    dy = math.sin(angle_rad) * longueur
    return LineString([(x, y), (x + dx, y + dy)])

# Préparation du fichier temporaire avant traitement
def prepare_temp_gpkg(uploaded_file, session_state, session_key="tmp_gpkg_path"):
    """
    Crée un fichier temporaire pour le GeoPackage uploadé, seulement s’il n’existe pas encore.
    """
    if session_key in session_state and os.path.exists(session_state[session_key]):
        # Le fichier temporaire existe déjà, on ne le recrée pas
        return session_state[session_key]
    # Création du nouveau fichier temporaire
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".gpkg")
    tmp.write(uploaded_file.read())
    tmp.close()
    # Enregistre dans le session_state Streamlit
    session_state["tmp_gpkg_path"] = tmp.name
    return tmp.name

# Préparer les colonnes du GeoDataFrame (gdf) pour le GPKG de sortie lors d'une maj_objet
def preparer_colonnes_maj_objet(gdf_geom, points_maj_objet):
    """Prépare les colonnes du GeoDataFrame de la table mise à jour selon les "type_objet" trouvés"""
    # Extraire tous les type_objet uniques des points de mise à jour
    type_objet_uniques = points_maj_objet['type_objet'].unique()
    
    # Pour chaque type_objet, créer une colonne si elle n'existe pas
    for type_objet in type_objet_uniques:
        if type_objet not in gdf_geom.columns:
            gdf_geom[type_objet] = None
    return gdf_geom

# Fonction principale
def creer_gpkg_complet(annotations_json, exif_json, ancien_gpkg, gpkg_output, image_folder, selected_layer, decalage_orientation):
    """
    Fonction principale de traitement géomatique :
    - Prend en entrée des annotations d'images, des données EXIF, un GeoPackage source et un dossier d'images.
    - Produit un GeoPackage complet avec plusieurs couches géographiques enrichies.
    """
    # --- 1. Chargement des données d'entrée ---
    with open(annotations_json, encoding='utf-8') as f:
        annotations = json.load(f)
    with open(exif_json, encoding='utf-8') as f:
        exif_data = json.load(f)
    log_dir = os.path.join(image_folder, 'resultat')
    logger = setup_logger(log_dir)

    # Listes pour stocker les données intermédiaires
    points_data = [] # Points annotés (tous types)
    points_carto = [] # Points pour la cartographie (mode cartographie)
    photos_records = [] # Infos sur chaque photo

    # --- 2. Extraction des points et informations depuis les annotations ---
    for img, annots in annotations.items():
        exif = exif_data.get(img, {})
        lat = exif.get('latitude'); lon = exif.get('longitude')
        direction = exif.get('direction')
        if lat is None or lon is None:
            continue # Ignore les images sans géolocalisation
        x, y = convertir_wgs84_vers_lambert93(lat, lon)
        pt_geom = Point(x, y)

        # Chemins des photos (originale et annotée)
        photo_originale = os.path.join(image_folder, img)
        photo_annotee = os.path.join(image_folder, 'resultat', img)

        # Enregistrement pour la table "photo"  
        photos_records.append({
            'image_name': img,
            'photo_original': photo_originale,
            'photo_annotee': photo_annotee,
            'latitude': lat,
            'longitude': lon,
            'x_lambert93': x,
            'y_lambert93': y,
            'direction': exif.get('direction'),
            'geometry': pt_geom
        })

        # Enregistrements pour la couche "point_geom"
        for ann in annots:
            points_data.append({
                'image_name': img,
                'latitude': lat,
                'longitude': lon,
                'x_lambert93': x,
                'y_lambert93': y,
                'direction': direction,
                'angle_ajuste': ann.get('angle_ajuste'),
                'type_objet': ann.get('type_objet'),
                'fonction_objet': ann.get('fonction_objet'),
                'mode_annotation': ann.get('mode_annotation'),
                'ID': ann.get('ID'),
                'geometry': pt_geom
            })
            
    # --- 3. Création des GeoDataFrames principaux ---
    gdf_photos = gpd.GeoDataFrame(photos_records, geometry='geometry', crs='EPSG:2154')
    gdf_points = gpd.GeoDataFrame(points_data, geometry='geometry', crs='EPSG:2154')

    # --- 4. Lecture et préparation de la couche utilisateur ---
    gdf_geom = gpd.read_file(ancien_gpkg, layer=selected_layer).copy()

    # Ajout dynamique des colonnes selon les types d'objets annotés (pour la mise à jour)
    points_maj_objet = gdf_points[gdf_points['mode_annotation'] == 'maj_objet']
    gdf_geom = preparer_colonnes_maj_objet(gdf_geom, points_maj_objet)

    # Nettoyage des géométries (explosion des multipolygones, suppression des invalides)
    gdf_geom_clean = gdf_geom.copy().explode(ignore_index=True)
    gdf_geom_clean = gdf_geom_clean[gdf_geom_clean.is_valid]

    # --- 5. Extraction des contours de bâtiments (pour les intersections) ---
    lignes_records = []
    for idx, geom in gdf_geom_clean.geometry.items():
        if geom is None or geom.is_empty:
            continue
        boundary = geom.boundary
        if boundary.geom_type == 'LineString':
            lignes_records.append({'geometry': boundary, 'bat_id': idx})
        elif boundary.geom_type == 'MultiLineString':
            for part in boundary.geoms:
                lignes_records.append({'geometry': part, 'bat_id': idx})

    lignes_bat = gpd.GeoDataFrame(lignes_records, geometry='geometry', crs=gdf_geom.crs)

    # --- 6. Mise à jour des objets (mode "maj_objet") ---
    modifs = set()
    for _, pt in gdf_points[gdf_points['mode_annotation'] == 'maj_objet'].iterrows():
        ang = pt['angle_ajuste']
        if ang is None:
            continue
        lv = creer_ligne_de_vue(pt.geometry.x, pt.geometry.y, ang, decalage_orientation)
        inters = gdf_geom[gdf_geom.geometry.intersects(lv)].copy()
        if inters.empty:
            continue
        inters['pt_int'] = inters.geometry.intersection(lv)
        inters['dist'] = inters['pt_int'].distance(pt.geometry)
        closest = inters.sort_values('dist').iloc[0]
        gdf_geom.loc[closest.name, pt.get('type_objet')] = pt.get('fonction_objet')
        modifs.add(closest.name)
    
    # On garde une copie des objets modifiés pour l'écriture finale
    gdf_geom_modif = gdf_geom.copy()

    # --- 7. Traitement des points cartographiques (mode "cartographie") ---
    points_carto = []
    for _, pt in gdf_points[gdf_points['mode_annotation'] == 'cartographie'].iterrows():
        ang = pt['angle_ajuste']
        if ang is None:
            continue
        lv = creer_ligne_de_vue(pt.geometry.x, pt.geometry.y, ang, decalage_orientation)
        inters = lignes_bat[lignes_bat.geometry.intersects(lv)]
        if inters.empty:
            continue

        # Recherche des intersections entre la ligne de vue et les bâtiments
        pts = []
        for _, br in inters.iterrows():
            inter = lv.intersection(br.geometry)
            if inter.is_empty:
                continue
            if inter.geom_type == 'Point':
                pts.append(inter)
            elif inter.geom_type == 'MultiPoint':
                pts.extend(inter.geoms)

        if not pts:
            continue

        # Sélectionner le point d'intersection le plus proche
        dists = [pt.geometry.distance(p) for p in pts]
        pf = pts[dists.index(min(dists))]

        # Recherche du bâtiment associé (par buffer autour du point d'intersection)
        buffer = pf.buffer(0.1)  # Utilise une tolérance de 0.1 unité
        objet_contenant = gdf_geom[
            gdf_geom.geometry.intersects(buffer)
        ]
        if not objet_contenant.empty:
            # Priorités : 'id' (minuscule), 'ID' (majuscules), sinon index (fid)
            if 'id' in objet_contenant.columns:
                objet_id = objet_contenant['id'].iloc[0]
            elif 'ID' in objet_contenant.columns:
                objet_id = objet_contenant['ID'].iloc[0]
            else:
                # fallback : retourne le premier index (feature id) pour garder une référence
                try:
                    objet_id = objet_contenant.index[0]
                except Exception:
                    objet_id = None
        else:
            objet_id = None

        # Ajouter le point ajusté à la liste des points cartographiques
        points_carto.append({
            'image_name': pt['image_name'],
            'x_lambert93': pf.x,
            'y_lambert93': pf.y,
            'angle_ajuste': ang,
            'type_objet': pt.get('type_objet'),
            'fonction_objet': pt.get('fonction_objet'),
            'ID': pt.get('ID'),
            'objet_id': objet_id,
            'geometry': pf
        })

    # --- 8. Création du GeoDataFrame des points cartographiques et regroupement spatial ---
    if points_carto:
        gdf_carto = gpd.GeoDataFrame(points_carto, geometry='geometry', crs='EPSG:2154')

        # Création d'un identifiant de groupe d'attributs (objet_id/type_objet/fonction_objet)
        gdf_carto['group_attr'] = (
            gdf_carto
            .groupby(['objet_id', 'type_objet', 'fonction_objet'])
            .ngroup()
        )

        # Initialisation de la colonne pour les sous-groupes spatiaux
        gdf_carto['subgroup_id'] = -1
        group_counter = 0

        # Pour chaque groupe d'attributs, on cherche les sous-groupes spatiaux (points proches < 2m)
        for attr_val, group_df in gdf_carto.groupby('group_attr'):
            idxs = group_df.index.to_numpy()
            coords = np.array([(pt.x, pt.y) for pt in group_df.geometry])
            dist_matrix = squareform(pdist(coords))
            
            n = len(coords)
            visited = np.zeros(n, dtype=bool)
            
            for i in range(n):
                if visited[i]:
                    continue
                # BFS pour composer la composante connexe à partir de i
                to_visit = [i]
                component = []
                while to_visit:
                    j = to_visit.pop()
                    if visited[j]:
                        continue
                    # Parcours en largeur pour trouver les composantes connexes (sous-groupes)
                    visited[j] = True
                    component.append(j)
                    # voisins à < 2 m
                    neighbors = np.where(dist_matrix[j] < 2.0)[0]
                    to_visit.extend([k for k in neighbors if not visited[k]])
                
                # Attribution d'un ID unique à chaque sous-groupe spatial
                for j in component:
                    gdf_carto.at[idxs[j], 'subgroup_id'] = group_counter
                group_counter += 1

        # À ce stade :
        # - gdf_carto['group_attr'] indique le groupe d’attributs
        # - gdf_carto['subgroup_id'] indique le sous-groupe spatial global
        # Log des regroupements pour vérification
        logger.info(gdf_carto[['objet_id','type_objet','fonction_objet','group_attr','subgroup_id']])
        # --- 9. Calcul des points de référence enrichis pour chaque sous-groupe ---
        reference_records = []

        for sub_id, sub_df in gdf_carto.groupby('subgroup_id'):
            # Prend le premier point du sous-groupe comme référence
            ref_objet = sub_df.iloc[0]
            angle_ajuste_ref = ref_objet['angle_ajuste']
            image_ref = ref_objet['image_name']
            base = decalage_orientation
            # Récupère le point photo associé
            pt_photo = gdf_points[gdf_points['image_name'] == image_ref]
            if pt_photo.empty:
                logger.info(f"[WARN] pas de point_photo pour {image_ref}")
                continue
            pt_photo_geom = pt_photo.iloc[0].geometry
            x0, y0 = pt_photo_geom.x, pt_photo_geom.y

            # Calcule les azimuts vers les autres objets du sous-groupe
            raw_ref = math.radians(90 - angle_ajuste_ref)  # base Est, sens trigonométrique
            raws = [raw_ref]
            # 2) Ajoute les autres angles bruts
            for _, row in sub_df.iterrows():
                if row['image_name'] == image_ref:
                    continue
                dx = row.geometry.x - x0
                dy = row.geometry.y - y0
                raws.append(math.atan2(dy, dx))

            # Moyenne circulaire des angles
            if raws:
                sin_sum = sum(math.sin(r) for r in raws)
                cos_sum = sum(math.cos(r) for r in raws)
                mean_raw = math.atan2(sin_sum, cos_sum) # reste en radians, base Est
                # conversion unique vers Nord=0°, sens horaire
                orientation_moyenne = (90 - math.degrees(mean_raw)) % 360
            else:
                orientation_moyenne = angle_ajuste_ref

            # Enregistrement du point de référence enrichi
            reference_records.append({
                'geometry': pt_photo_geom,
                'objet_id': ref_objet['objet_id'],
                'type_objet': ref_objet['type_objet'],
                'fonction_objet': ref_objet['fonction_objet'],
                'group_attr': ref_objet['group_attr'],
                'subgroup_id': sub_id,
                'angle_ajuste_ref': angle_ajuste_ref,
                'orientation_moyenne': orientation_moyenne
            })

        # Construction du GeoDataFrame des points de référence
        gdf_reference_points = gpd.GeoDataFrame(reference_records, crs=gdf_carto.crs)
        mode = 'a'
    else:
        gdf_carto = gpd.GeoDataFrame(
            {
                'image_name': [], 'x_lambert93': [], 'y_lambert93': [],
                'angle_ajuste': [], 'fonction_objet': [], 'ID': []
            },
            geometry=gpd.GeoSeries([], crs='EPSG:2154'), crs='EPSG:2154'
        )
        
        gdf_reference_points = gpd.GeoDataFrame(
            {
                'geometry': [],
                'objet_id': [],
                'type_objet': [],
                'fonction_objet': [],
                'group_attr': [],
                'subgroup_id': [],
                'angle_ajuste_ref': [],
                'orientation_moyenne': []
            },
            geometry='geometry',
            crs='EPSG:2154'
        )

        gdf_lignes_vue = gpd.GeoDataFrame(
            {
                'geometry': [],
                'objet_id': [],
                'subgroup_id': [],
                'angle_utilise': []
            },
            geometry='geometry',
            crs='EPSG:2154'
        )

        mode = 'w'

    # --- 10. Tracé des lignes de vue depuis les points de référence ---
    lines_records = []
    for _, ref in gdf_reference_points.iterrows():
        x_ref, y_ref = ref.geometry.x, ref.geometry.y
        # On utilise l'orientation moyenne comme angle de vue
        angle = ref['orientation_moyenne']
        # Génération de la ligne de vue
        lv = creer_ligne_de_vue(x_ref, y_ref, angle, decalage_orientation, longueur=150)
        lines_records.append({
            'geometry': lv,
            'objet_id': ref['objet_id'],
            'subgroup_id': ref['subgroup_id'],
            'angle_utilise': angle
        })
        # Création de la GeoDataFrame des lignes de vue
        gdf_lignes_vue = gpd.GeoDataFrame(lines_records, geometry='geometry', crs=gdf_reference_points.crs)
    
    # --- 11. Calcul des points d'extrémité des lignes de vue ---
    points_extremites = []

    for _, ref in gdf_reference_points.iterrows():
        x_ref, y_ref = ref.geometry.x, ref.geometry.y
        angle = ref['orientation_moyenne']
        lv = creer_ligne_de_vue(x_ref, y_ref, angle, decalage_orientation, longueur=150)
        
        # Recherche des intersections avec les lignes de bâtiments
        inters = lignes_bat[lignes_bat.geometry.intersects(lv)]
        if inters.empty:
            continue

        pts = []
        for _, br in inters.iterrows():
            inter = lv.intersection(br.geometry)
            if inter.is_empty:
                continue
            if inter.geom_type == 'Point':
                pts.append(inter)
            elif inter.geom_type == 'MultiPoint':
                pts.extend(inter.geoms)

        if not pts:
            continue
        
        # Choisir le point d’intersection le plus proche du point de référence
        dists = [ref.geometry.distance(p) for p in pts]
        pf = pts[dists.index(min(dists))]
        
        points_extremites.append({
            'geometry': pf,
            'objet_id': ref['objet_id'],
            'subgroup_id': ref['subgroup_id'],
            'angle_utilise': angle,
            'type_objet': ref['type_objet'],
            'fonction_objet': ref['fonction_objet']
        })
    
    # --- 12. Logs de contrôle pour le debug ---
    # Ajoutez des impressions pour vérifier les données d'entrée
    logger.info(f"Chargement des annotations depuis {annotations_json}")
    logger.info(f"Annotations chargées : {len(annotations)} images")
    logger.info(f"Chargement des données EXIF depuis {exif_json}")
    logger.info(f"Données EXIF chargées : {len(exif_data)} entrées")
    # Ajoutez des impressions pour vérifier les GeoDataFrames avant l'écriture
    logger.info(f"Nombre de points dans gdf_points : {len(gdf_points)}")
    logger.info(f"Nombre d'objets dans gdf_geom_modif : {len(gdf_geom_modif)}")
    logger.info(f"Nombre de points cartographiques dans gdf_carto : {len(gdf_carto)}")
    logger.info(f"Nombre de points de référence dans gdf_reference_points : {len(gdf_reference_points)}")
    logger.info(f"Nombre de lignes de vue dans gdf_lignes_vue : {len(gdf_lignes_vue)}")
    logger.info(f"Nombre de points d'extrémité dans points_extremites : {len(points_extremites)}")

    # --- 13. Écriture des couches dans le GeoPackage de sortie ---
    
    # Couche de référence donné par l'utilisateur (maj_cartographie), phm = photomapon
    try:
        if not gdf_geom_modif.empty:
            gdf_geom_modif.to_file(gpkg_output, layer=selected_layer, driver='GPKG', mode='a')
            logger.info(f"Couche '{selected_layer}' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'toiture' : {e}")

    # Copie de toutes les couches existantes du GPKG source
    try:
        layers = fiona.listlayers(ancien_gpkg)
        for layer in layers:
            # On saute la couche déjà traitée si besoin
            if layer == selected_layer:
                continue
            gdf = gpd.read_file(ancien_gpkg, layer=layer)
            if not gdf.empty:
                gdf.to_file(gpkg_output, layer=layer, driver='GPKG', mode='a')
                logger.info(f"Couche existante '{layer}' copiée dans le GPKG de sortie")
    except Exception as e:
        logger.info(f"Erreur lors de la copie des couches existantes : {e}")

    # Couche des points pour chaque photo annotée
    try:
        if not gdf_photos.empty:
            gdf_photos.to_file(gpkg_output, layer='phm_photo', driver='GPKG', mode='a')
            logger.info(f"Couche 'phm_photo' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'photo' : {e}")

    # Couche de point de référence pour créer les points de la couche "point_objet_annot" (point objet brut)
    try:
        gdf_points.to_file(gpkg_output, layer='phm_point_geom', driver='GPKG', mode='w')
        logger.info(f"Couche 'phm_point_geom' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'point_geom' : {e}")

    # Couche pour chaque objet annoté indépendamment des doublons
    try:
        if not gdf_carto.empty:
            gdf_carto.to_file(gpkg_output, layer='phm_point_objet_annot', driver='GPKG', mode='a')
            logger.info(f"Couche 'phm_point_objet_annot' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'point_objet' : {e}")

    # Couche de point de référence utilisé pour la création final des objets
    try:
        if not gdf_reference_points.empty:
            gdf_reference_points.to_file(gpkg_output, layer='phm_point_ref', driver='GPKG', mode='a')
            logger.info(f"Couche 'phm_point_ref' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'point_ref' : {e}")

    # Couche des lignes de vue finales
    try:
        if not gdf_lignes_vue.empty:
            gdf_lignes_vue.to_file(gpkg_output, layer='phm_ligne_vue', driver='GPKG', mode='a')
            logger.info(f"Couche 'phm_ligne_vue' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'ligne_vue' : {e}")

    # Couche pour chaque objet annoté final (angle moyen, sans doublons)
    try:
        if points_extremites:
            gdf_extremites = gpd.GeoDataFrame(points_extremites, geometry='geometry', crs='EPSG:2154')
            gdf_extremites.to_file(gpkg_output, layer='phm_point_objet', driver='GPKG', mode='a')
            logger.info(f"Couche 'phm_point_objet' écrite avec succès")
    except Exception as e:
        logger.info(f"Erreur lors de l'écriture de la couche 'point_extremite' : {e}")