"""Prépare des tenues pour le défilé à partir d'une planche photo (silhouettes
côte à côte sur fond blanc, coupées au cou).

Étapes : découpe des silhouettes, agrandissement x4 (EDSR), détourage
(BiRefNet), décontamination des bords — mis en cache, c'est le plus long —
puis retouche légère de la peau (masque peau = silhouette − vêtements),
étalonnage « studio », taille de rendu et calcul de l'espacement façon
référence. Écrit les PNG dans public/looks et les mesures dans src/looks.json.

Dépendances (dans un venv) :
    pip install "rembg[cpu]" opencv-contrib-python-headless pymatting pillow numpy
(les modèles EDSR, BiRefNet et u2net_cloth_seg se téléchargent au premier lancement)

Usage :
    python -I scripts/preparer_tenues.py planche.jpg [--height 1080]
"""
import argparse
import hashlib
import json
import multiprocessing
import os
import urllib.request
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
from PIL import Image
from pymatting import estimate_foreground_ml
from rembg import new_session, remove

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
EDSR_URL = "https://raw.githubusercontent.com/Saafke/EDSR_Tensorflow/master/models/EDSR_x4.pb"

# Rythme de la vidéo de référence : un corps tous les 0,317 × la hauteur,
# silhouettes presque jointives (on garde 4 px d'air là où un sac déborde).
REFERENCE_PITCH = 0.317
CLEARANCE = 4

# Étalonnage, identique pour toutes les tenues.
BLACK, WHITE = 0.03, 0.97  # étirement des niveaux
GAMMA = 0.9  # < 1 éclaircit les tons moyens
CONTRAST = 0.07  # courbe en S douce
CLARITY = 0.22  # contraste local (ôte l'aspect voilé)
VIBRANCE = 0.16  # couleurs ternes, tons chair épargnés
SHARP = 0.55  # accentuation fine à la taille finale

# Retouche peau, volontairement légère : lissage qui garde les contours,
# un peu de lumière et d'éclat. La carnation de chaque mannequin est conservée.
SKIN_SMOOTH = 0.45
SKIN_LIFT = 5.0  # points de luminance L*
SKIN_GLOW = 0.10  # saturation en plus


def split(sheet):
    """Coupe la planche aux colonnes blanches entre les silhouettes."""
    rows = sheet.mean(axis=(1, 2))
    top = 0
    while top < len(rows) and rows[top] < 100:  # liseré sombre éventuel en haut
        top += 1
    sheet = sheet[top:]
    occupied = (sheet.min(axis=2) < 232).sum(axis=0) >= 3
    spans, start = [], None
    for x, used in enumerate(occupied):
        if used and start is None:
            start = x
        if not used and start is not None:
            spans.append((start, x))
            start = None
    if start is not None:
        spans.append((start, len(occupied)))
    spans = [s for s in spans if s[1] - s[0] > sheet.shape[1] * 0.04]
    cuts = [0] + [(a[1] + b[0]) // 2 for a, b in zip(spans, spans[1:])] + [sheet.shape[1]]
    return [sheet[:, a:b] for a, b in zip(cuts, cuts[1:])]


def upscale(rgb, model_path, band=160, overlap=12):
    """EDSR x4 par bandes horizontales qui se chevauchent (sinon plusieurs Go de RAM)."""
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(model_path)
    sr.setModel("edsr", 4)
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h = bgr.shape[0]
    parts = []
    for top in range(0, h, band):
        a, b = max(0, top - overlap), min(h, top + band + overlap)
        up = sr.upsample(np.ascontiguousarray(bgr[a:b]))
        parts.append(up[(top - a) * 4 : (min(h, top + band) - a) * 4])
    return cv2.cvtColor(np.vstack(parts), cv2.COLOR_BGR2RGB)


def cut_out(rgb, session):
    mask = remove(Image.fromarray(rgb), session=session, only_mask=True).convert("L")
    alpha = np.asarray(mask).astype(np.float64) / 255
    alpha[alpha < 0.02] = 0
    fg = estimate_foreground_ml(rgb.astype(np.float64) / 255, alpha)
    rgba = np.dstack([np.clip(fg, 0, 1), alpha]).astype(np.float32)
    ys, xs = np.where(alpha > 0.03)
    return rgba[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]


def prepare_cutout(crop, edsr, dest):
    """Agrandit et détoure une silhouette, puis l'écrit dans le cache.

    Lancé dans un processus à part : BiRefNet garde ~8 Go de RAM jusqu'à la fin
    du processus, et cumulé sur plusieurs tenues ça dépasse la mémoire.
    """
    rgba = cut_out(upscale(crop, edsr), new_session("birefnet-general-lite"))
    Image.fromarray((rgba * 255).round().astype(np.uint8), "RGBA").save(dest)


def skin_mask(rgba, session):
    """Peau = silhouette − vêtements (u2net_cloth_seg) × couleur chair.

    Les zones très claires sont écartées : un sac en fourrure rose a la même
    teinte qu'une peau mais pas la même luminance.
    """
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    h, w = alpha.shape
    side = max(h, w)
    square = np.ones((side, side, 3), np.float32)
    x0 = (side - w) // 2
    square[:, x0 : x0 + w] = rgb * alpha[..., None] + (1 - alpha[..., None])
    pred = session.predict(Image.fromarray((square * 255).astype(np.uint8)), cc="attire")[0]
    cloth = np.asarray(pred).astype(np.float32)[:, x0 : x0 + w] / 255
    cloth = cv2.dilate(cloth, np.ones((9, 9), np.uint8))
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L, A, B = lab[..., 0], lab[..., 1], lab[..., 2]
    hue = np.degrees(np.arctan2(B, A)) % 360
    color = (
        np.clip(1 - np.abs(hue - 57) / 26, 0, 1)
        * np.clip((np.hypot(A, B) - 8) / 8, 0, 1)
        * np.clip((L - 15) / 10, 0, 1)
        * np.clip((64 - L) / 8, 0, 1)
    )
    return cv2.GaussianBlur(alpha * (1 - cloth) * color, (0, 0), 3)


def retouch_skin(rgba, mask):
    rgb = rgba[..., :3]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    smooth = cv2.bilateralFilter(lab, d=0, sigmaColor=6, sigmaSpace=rgb.shape[0] / 300)
    lab[..., 0] += mask * (SKIN_SMOOTH * (smooth[..., 0] - lab[..., 0]) + SKIN_LIFT)
    for c in (1, 2):
        lab[..., c] += mask * SKIN_SMOOTH * (smooth[..., c] - lab[..., c])
        lab[..., c] *= 1 + SKIN_GLOW * mask
    out = rgba.copy()
    out[..., :3] = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1)
    return out


def grade(rgba, height):
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    rgb = np.clip((rgb - BLACK) / (WHITE - BLACK), 0, 1) ** GAMMA
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    curved = lum + CONTRAST * (lum - 0.5) * (1 - np.abs(2 * lum - 1)) * 2
    rgb = np.clip(rgb * (curved / np.maximum(lum, 1e-4))[..., None], 0, 1)

    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    L = lab[..., 0]
    lab[..., 0] = np.clip(L + CLARITY * (L - cv2.GaussianBlur(L, (0, 0), rgb.shape[0] / 60)), 0, 100)
    A, B = lab[..., 1], lab[..., 2]
    hue = np.degrees(np.arctan2(B, A)) % 360
    skin = np.clip(1 - np.abs(hue - 55) / 30, 0, 1)
    boost = 1 + VIBRANCE * (1 - np.clip(np.hypot(A, B) / 60, 0, 1)) * (1 - 0.85 * skin)
    lab[..., 1], lab[..., 2] = A * boost, B * boost
    rgb = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB), 0, 1)

    width = round(rgb.shape[1] * height / rgb.shape[0])
    img = Image.fromarray((np.dstack([rgb, alpha]) * 255).round().astype(np.uint8), "RGBA")
    arr = np.asarray(img.resize((width, height), Image.LANCZOS)).astype(np.float32) / 255
    col = arr[..., :3]
    col = np.clip(col + SHARP * (col - cv2.GaussianBlur(col, (0, 0), 1.0)), 0, 1)
    return (np.dstack([col, arr[..., 3]]) * 255).round().astype(np.uint8)


def body_profile(rgba):
    """Centre du corps (milieu des pieds) et extension gauche/droite par ligne."""
    solid = rgba[..., 3] > 40
    h = solid.shape[0]
    feet = np.where(solid[int(h * 0.86) : int(h * 0.98)].any(axis=0))[0]
    center = (feet.min() + feet.max()) / 2
    left = np.array([center - np.where(r)[0].min() if r.any() else -1e9 for r in solid])
    right = np.array([np.where(r)[0].max() - center if r.any() else -1e9 for r in solid])
    return center, left, right


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sheet")
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--models", default=os.path.expanduser("~/.u2net"))
    args = parser.parse_args()

    os.makedirs(args.models, exist_ok=True)
    edsr = os.path.join(args.models, "EDSR_x4.pb")
    if not os.path.exists(edsr):
        urllib.request.urlretrieve(EDSR_URL, edsr)
    with open(args.sheet, "rb") as f:
        cache = os.path.join(HERE, ".cache", hashlib.sha1(f.read()).hexdigest()[:12])
    os.makedirs(cache, exist_ok=True)
    sheet = np.asarray(Image.open(args.sheet).convert("RGB"))
    crops = split(sheet)
    cached = [os.path.join(cache, f"look{i}.png") for i in range(1, len(crops) + 1)]
    spawn = multiprocessing.get_context("spawn")
    for crop, dest in zip(crops, cached):
        if not os.path.exists(dest):
            with ProcessPoolExecutor(max_workers=1, mp_context=spawn) as pool:
                pool.submit(prepare_cutout, crop, edsr, dest).result()

    clothes = new_session("u2net_cloth_seg")
    out_dir = os.path.join(PROJECT, "public", "looks")
    os.makedirs(out_dir, exist_ok=True)
    looks = []
    for i, dest in enumerate(cached, 1):
        rgba = np.asarray(Image.open(dest)).astype(np.float32) / 255
        rgba = grade(retouch_skin(rgba, skin_mask(rgba, clothes)), args.height)
        Image.fromarray(rgba, "RGBA").save(os.path.join(out_dir, f"look{i}.png"), optimize=True)
        center, left, right = body_profile(rgba)
        looks.append({"file": f"looks/look{i}.png", "width": rgba.shape[1], "height": rgba.shape[0],
                      "center": round(float(center), 1), "_left": left, "_right": right})
        print(f"look{i} : {rgba.shape[1]}×{rgba.shape[0]}", flush=True)

    base = REFERENCE_PITCH * args.height
    for i, look in enumerate(looks):
        nxt = looks[(i + 1) % len(looks)]
        need = float(np.max(look["_right"] + nxt["_left"])) + CLEARANCE
        look["pitch"] = round(max(base, need), 1)
    for look in looks:
        del look["_left"], look["_right"]
    with open(os.path.join(PROJECT, "src", "looks.json"), "w") as f:
        json.dump(looks, f, indent=2)
    print("pas :", [l["pitch"] for l in looks])


if __name__ == "__main__":
    main()
