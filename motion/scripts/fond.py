"""Reconstruit un fond dégradé propre à partir d'une capture (même compressée).

Ajuste, canal par canal, une surface lisse de degré 2 sur les couleurs de
l'image (bord sombre de capture ignoré), puis la redessine à la taille de la
vidéo avec un léger tramage pour éviter les bandes une fois encodé en H.264.

Usage :
    python -I scripts/fond.py capture.jpg [--width 1440 --height 1080]
"""
import argparse
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))


def design(x, y):
    return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], axis=-1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1080)
    args = parser.parse_args()

    img = np.asarray(Image.open(args.source).convert("RGB")).astype(np.float64)
    keep = img.mean(axis=(0, 2)) > 60  # retire les colonnes de bord noir
    img = img[:, keep]
    h, w, _ = img.shape
    ys, xs = np.mgrid[0:h:4, 0:w:4]
    samples = img[ys, xs].reshape(-1, 3)
    A = design((xs / (w - 1)).ravel(), (ys / (h - 1)).ravel())
    coef, *_ = np.linalg.lstsq(A, samples, rcond=None)

    gy, gx = np.mgrid[0 : args.height, 0 : args.width]
    out = design(gx / (args.width - 1), gy / (args.height - 1)) @ coef
    rng = np.random.default_rng(7)
    out += rng.uniform(-0.5, 0.5, out.shape) + rng.uniform(-0.5, 0.5, out.shape)
    out = np.clip(np.round(out), 0, 255).astype(np.uint8)

    dest = os.path.join(os.path.dirname(HERE), "public", "fond.png")
    Image.fromarray(out, "RGB").save(dest, optimize=True)
    corners = [out[0, 0], out[0, -1], out[-1, 0], out[-1, -1]]
    print("fond.png", out.shape[1], "×", out.shape[0], "coins :", [tuple(int(v) for v in c) for c in corners])


if __name__ == "__main__":
    main()
