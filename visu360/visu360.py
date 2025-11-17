# -----------------------------------------------------------------------------
# Version 1.1 PhotoMapon
# Auteur      : Joseph Jacquet | Carte et Liens
# Contact     : contact@carteetliens.fr | www.carteetliens.fr
# Licence     : Ce projet est publié sous la licence GNU GPL v3.
# Description : (visu360.py) Composant Streamlit faisant le pont entre l'interface et la visionneuse Pannelum (./frontend/index.html)
# -----------------------------------------------------------------------------


import streamlit.components.v1 as components
from pathlib import Path
import base64

_component_func = components.declare_component(
    "my_visu360",
    path=str(Path(__file__).parent / "frontend")
)

def pannellum_viewer(
    image_path,
    yaw=0, pitch=0, hfov=110, height=600,
    mode_annotation="", type_objet="", fonction_objet="",
    x=None, y=None,
    hotspots=None, img_width=None, img_height=None, direction=0,
    selected_uuid=None, key=None, cmd_action=None, cmd_data=None,
):
    """
    Appelle le composant frontend. 
    - Envoie les props (image base64, hotspots initiaux, etc.)
    - Permet d'envoyer des commandes via cmd/cmd_data
    """
    if hotspots is None:
        hotspots = []

    # Encode l'image en base64 pour le frontend
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Appel du composant (Streamlit sérialise automatiquement les kwargs)
    return _component_func(
        image_path=f"data:image/jpeg;base64,{img_b64}",
        yaw=yaw,
        pitch=pitch,
        hfov=hfov,
        height=height,
        mode_annotation=mode_annotation,
        type_objet=type_objet,
        fonction_objet=fonction_objet,
        x=x,
        y=y,
        hotspots=hotspots,
        img_width=img_width,
        img_height=img_height,
        direction=direction,
        selected_uuid=selected_uuid,
        cmd_action=cmd_action,
        cmd_data=cmd_data,
        key=key,
        default={"hotspots": hotspots, "yaw": yaw, "pitch": pitch, "hfov": hfov}
    )
