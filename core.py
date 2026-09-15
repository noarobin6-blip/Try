# =============================================================================
#  core.py — Moteur de données et d'analyse du dashboard d'activité RFP / RFI
# -----------------------------------------------------------------------------
#  RÈGLE D'ARCHITECTURE : ce fichier n'importe JAMAIS Streamlit.
#  Il ne fait que : charger → normaliser → enrichir → filtrer → calculer →
#  construire les figures Plotly. Il est donc testable et réutilisable seul
#  (notebook, script, API) et partagé à l'identique par app.py et export.py.
# =============================================================================
from __future__ import annotations

import base64
import datetime as dt
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

_PANDAS_2 = int(pd.__version__.split(".")[0]) >= 2

# =============================================================================
#  [BRANCHEMENT PRINCIPAL] — TOUT CE QUI SE PARAMÈTRE TIENT DANS CE BLOC
#  Pour brancher le dashboard sur les vraies données :
#    1. USE_FAKE_DATA = False
#    2. DATA_PATH / SHEET_NAME → chemin et onglet du fichier Excel
#    3. COLUMN_MAP → à droite, le nom EXACT des colonnes du fichier
#       (la correspondance est tolérante : casse, accents, espaces et
#        underscores sont ignorés — "Date Réception" == "date_reception")
#    4. Les colonnes absentes du fichier sont simplement neutralisées :
#       les graphiques concernés disparaissent, l'application ne casse pas.
#  Temps de branchement visé : 5 minutes.
# =============================================================================

USE_FAKE_DATA = True          # True = données synthétiques, False = lecture Excel
DATA_PATH = "données.xlsx"    # [BRANCHEMENT] remplacer par ton chemin
SHEET_NAME = "Activité"       # [BRANCHEMENT] nom de l'onglet

COLUMN_MAP = {
    "date_reception": "Date_Reception",   # [BRANCHEMENT] adapter aux noms réels
    "date_envoi": "Date_Envoi",
    "type_demande": "Type",               # RFP, RFI, DDQ
    "client": "Client_Nom",
    "type_client": "Type_Client",         # institutionnel, distributeur, consultant
    "pays": "Pays",
    "fonds": "Fonds",
    "classe_actifs": "Classe_Actifs",
    "statut": "Statut",                   # en cours, envoyé, gagné, perdu, abandonné
    "analyste": "Analyste_Nom",
    "nb_questions": "Nombre_Questions",
    "langue": "Langue",
    "montant_potentiel": "Montant_EUR",
}

# [BRANCHEMENT] Intitulés alternatifs tolérés pour chaque champ, en plus de
# COLUMN_MAP. Sert quand le classeur reçu ne porte pas exactement les mêmes
# en-têtes : inutile de modifier COLUMN_MAP, il suffit d'ajouter l'intitulé ici.
# La comparaison ignore casse, accents, espaces, tirets et underscores.
COLUMN_ALIASES: dict[str, list[str]] = {
    "date_reception": ["date de reception", "date réception", "date de réception",
                       "date demande", "date d'arrivee", "received date", "date in"],
    "date_envoi": ["date de envoi", "date d'envoi", "date reponse", "date de réponse",
                   "date rendu", "sent date", "date out"],
    "type_demande": ["type de demande", "type demande", "nature de la demande",
                     "nature", "request type", "categorie"],
    "client": ["nom du client", "client", "prospect", "contrepartie", "client name"],
    "type_client": ["type de client", "segment client", "segment", "canal", "client type"],
    "pays": ["pays du client", "country", "juridiction", "zone"],
    "fonds": ["fonds", "nom du fonds", "strategie", "stratégie", "fund", "produit"],
    "classe_actifs": ["classe d'actifs", "classe actifs", "asset class", "classe"],
    "statut": ["statut", "statut du dossier", "etat", "état", "status", "issue"],
    "analyste": ["analyste", "nom de l'analyste", "responsable", "redacteur",
                 "rédacteur", "owner", "assigne a"],
    "nb_questions": ["nombre de questions", "nb questions", "questions", "volume questions",
                     "number of questions"],
    "langue": ["langue", "langue de reponse", "langue de réponse", "language"],
    "montant_potentiel": ["montant", "montant eur", "montant potentiel", "encours",
                          "encours potentiel", "aum", "ticket", "amount"],
}

# Seules ces trois colonnes sont indispensables ; le reste est optionnel.
REQUIRED_FIELDS: tuple[str, ...] = ("date_reception", "type_demande", "statut")

STATUS_NORMALIZATION = {
    "en cours": "En cours",
    "en-cours": "En cours",
    "encours": "En cours",
    "en traitement": "En cours",
    "wip": "En cours",
    "envoye": "Envoyé",
    "envoyé": "Envoyé",
    "soumis": "Envoyé",
    "repondu": "Envoyé",
    "submitted": "Envoyé",
    "gagne": "Gagné",
    "gagné": "Gagné",
    "won": "Gagné",
    "remporte": "Gagné",
    "perdu": "Perdu",
    "lost": "Perdu",
    "abandonne": "Abandonné",
    "abandonné": "Abandonné",
    "annule": "Abandonné",
    "no bid": "Abandonné",
    "nobid": "Abandonné",
    "declined": "Abandonné",
}

TYPE_NORMALIZATION = {
    "rfp": "RFP",
    "r.f.p": "RFP",
    "request for proposal": "RFP",
    "appel d'offres": "RFP",
    "rfi": "RFI",
    "r.f.i": "RFI",
    "request for information": "RFI",
    "ddq": "DDQ",
    "d.d.q": "DDQ",
    "due diligence": "DDQ",
    "due diligence questionnaire": "DDQ",
    "questionnaire": "DDQ",
}

CLIENT_TYPE_NORMALIZATION = {
    "institutionnel": "Institutionnel",
    "institution": "Institutionnel",
    "institutional": "Institutionnel",
    "asset owner": "Institutionnel",
    "distributeur": "Distributeur",
    "distribution": "Distributeur",
    "wholesale": "Distributeur",
    "plateforme": "Distributeur",
    "consultant": "Consultant",
    "conseil": "Consultant",
    "gatekeeper": "Consultant",
}

LANGUE_NORMALIZATION = {
    "fr": "Français", "francais": "Français", "français": "Français", "french": "Français",
    "en": "Anglais", "anglais": "Anglais", "english": "Anglais", "uk": "Anglais",
    "de": "Allemand", "allemand": "Allemand", "german": "Allemand", "deutsch": "Allemand",
    "it": "Italien", "italien": "Italien", "italian": "Italien",
    "es": "Espagnol", "espagnol": "Espagnol", "spanish": "Espagnol",
    "nl": "Néerlandais", "neerlandais": "Néerlandais", "dutch": "Néerlandais",
}

# Valeur attribuée à une modalité inconnue (elle reste visible, jamais supprimée)
VALEUR_INCONNUE = "Non renseigné"

# Ordre métier des statuts (pipeline), utilisé partout dans l'interface
STATUT_EN_COURS, STATUT_ENVOYE = "En cours", "Envoyé"
STATUT_GAGNE, STATUT_PERDU, STATUT_ABANDONNE = "Gagné", "Perdu", "Abandonné"
STATUT_ORDER = [STATUT_EN_COURS, STATUT_ENVOYE, STATUT_GAGNE, STATUT_PERDU, STATUT_ABANDONNE]
STATUTS_ENVOYES = (STATUT_ENVOYE, STATUT_GAGNE, STATUT_PERDU)   # la réponse est partie
STATUTS_DECIDES = (STATUT_GAGNE, STATUT_PERDU)                  # le client a tranché
TYPE_ORDER = ["RFP", "RFI", "DDQ"]

# [BRANCHEMENT] Engagement de service, en jours OUVRÉS, par type de demande
SLA_JOURS_OUVRES = {"RFP": 15, "RFI": 8, "DDQ": 12}
SLA_DEFAUT = 12

# [BRANCHEMENT] Horizon de projection de la tendance (mois)
PROJECTION_MOIS = 6
# [BRANCHEMENT] Seuil de significativité statistique
ALPHA = 0.05

# [BRANCHEMENT] Données synthétiques : profondeur d'historique et graine
FAKE_MOIS_HISTORIQUE = 36
FAKE_SEED = 20260914
FAKE_VOLUME_MENSUEL_BASE = 38

# Avertissement affiché sous les indicateurs : les décisions clients arrivent
# plusieurs mois après l'envoi, donc les périodes récentes sont mécaniquement
# riches en dossiers non tranchés (censure à droite). Ne jamais lire un taux de
# succès récent comme un taux définitif.
NOTE_CENSURE = ("Les clients tranchent plusieurs mois après l'envoi de la réponse : sur une "
                "période récente, le taux de succès et l'encours remporté sont mécaniquement "
                "sous-évalués, et l'encours en jeu surévalué.")

# Dimensions filtrables : clé interne -> libellé affiché (pilote la barre latérale)
DIMENSIONS: dict[str, str] = {
    "type_demande": "Type de demande",
    "statut": "Statut",
    "classe_actifs": "Classe d'actifs",
    "type_client": "Type de client",
    "pays": "Pays",
    "analyste": "Analyste",
    "langue": "Langue",
}

# =============================================================================
#  IDENTITÉ VISUELLE — deux thèmes, une seule source de vérité
# -----------------------------------------------------------------------------
#  Le thème « sombre » est celui de l'écran et du rapport ; le thème « clair »
#  existe pour l'impression (`python export.py --clair`). Chaque palette
#  catégorielle a été passée au contrôle daltonisme / contraste sur SA surface :
#    sombre : 8 slots sur #14181e — bande de clarté, chroma, séparation CVD et
#             contraste ≥ 3:1 tous validés ; 3 premiers slots valides en
#             toutes-paires (nuages de points).
#    clair  : mêmes teintes re-étagées pour #fcfcfb.
#  L'ORDRE des teintes est le mécanisme de sécurité daltonisme, pas une
#  préférence esthétique : ne pas permuter sans revalider.
# =============================================================================
FONT_STACK = ('"InterVariable", "Inter", system-ui, -apple-system, "Segoe UI", '
              'Roboto, "Helvetica Neue", Arial, sans-serif')
TEMPLATE_NAME = "rfp_premium"

THEMES: dict[str, dict[str, Any]] = {
    "sombre": dict(
        PLANE="#0d1014",          # fond de page
        SURFACE="#14181e",        # cartes et aires de tracé
        ELEVATION="#1b212a",      # survol, éléments soulevés
        INK="#eef2f6",            # encre primaire
        INK_2="#a7b2c0",          # encre secondaire
        INK_MUTED="#6c7889",      # axes, libellés discrets
        GRID="#222831",           # grille (filet plein, jamais pointillé)
        AXIS="#2f3845",           # ligne de base
        BORDER="rgba(255,255,255,0.08)",
        VOILE="rgba(20,24,30,0.92)",     # fond des annotations posées sur un tracé
        ACCENT="#3987e5",         # chrome : rail actif, liens, focus
        SERIES=["#3987e5", "#d95926", "#199e70", "#c98500",
                "#d55181", "#008300", "#9085e9", "#e66767"],
        # Rampe séquentielle : le « presque rien » se fond dans la surface,
        # le maximum s'en détache — l'inverse exact du thème clair.
        SEQUENTIEL=["#151f2b", "#193356", "#1c4a83", "#2260ab",
                    "#2f79cc", "#4f95e0", "#7fb2f0"],
        ORDINAL=["#2f79cc", "#4f95e0", "#7fb2f0", "#a9cbf6"],
        STATUS_GOOD="#0ca30c", STATUS_WARNING="#fab219",
        STATUS_SERIOUS="#ec835a", STATUS_CRITICAL="#d03b3b",
        TEXTE_BON="#4ac45f", TEXTE_MAUVAIS="#ef7676",
    ),
    "clair": dict(
        PLANE="#f7f6f3",
        SURFACE="#fcfcfb",
        ELEVATION="#ffffff",
        INK="#0b0b0b",
        INK_2="#52514e",
        INK_MUTED="#898781",
        GRID="#e6e4dd",
        AXIS="#c3c2b7",
        BORDER="rgba(11,11,11,0.10)",
        VOILE="rgba(252,252,251,0.92)",
        ACCENT="#0d366b",
        SERIES=["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
        SEQUENTIEL=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                    "#256abf", "#184f95", "#0d366b"],
        ORDINAL=["#2a78d6", "#1c5cab", "#184f95", "#104281"],
        STATUS_GOOD="#0ca30c", STATUS_WARNING="#fab219",
        STATUS_SERIOUS="#ec835a", STATUS_CRITICAL="#d03b3b",
        TEXTE_BON="#006300", TEXTE_MAUVAIS="#a82f2f",
    ),
}

# [BRANCHEMENT] Thème par défaut de l'écran et du rapport : "sombre" ou "clair"
THEME_DEFAUT = "sombre"

# Jetons exposés au reste du programme — renseignés par appliquer_theme().
THEME = THEME_DEFAUT
PLANE = SURFACE = ELEVATION = INK = INK_2 = INK_MUTED = ""
GRID = AXIS = BORDER = VOILE = ACCENT = ""
STATUS_GOOD = STATUS_WARNING = STATUS_SERIOUS = STATUS_CRITICAL = ""
TEXTE_BON = TEXTE_MAUVAIS = ""
SERIES: list[str] = []
SEQUENTIEL: list[str] = []
ORDINAL: list[str] = []
STATUT_COLORS: dict[str, str] = {}
TYPE_COLORS: dict[str, str] = {}
CLIENT_TYPE_COLORS: dict[str, str] = {}


def _luminance(couleur: str) -> float:
    """Luminance relative WCAG d'une couleur hexadécimale."""
    h = couleur.lstrip("#")
    canaux = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        canaux.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canaux[0] + 0.7152 * canaux[1] + 0.0722 * canaux[2]


def encre_lisible(fond: str) -> str:
    """Encre à poser sur un aplat : celle des deux qui contraste le plus.
    Indispensable pour les valeurs écrites dans une cellule de carte de chaleur
    ou dans un segment d'entonnoir, dont la couleur varie avec la donnée."""
    clair, sombre = "#ffffff", "#0d1014"
    lum = _luminance(fond)
    contraste_clair = 1.05 / (lum + 0.05)
    contraste_sombre = (lum + 0.05) / 0.05
    return clair if contraste_clair >= contraste_sombre else sombre


def couleur_rampe(rampe: Sequence[str], t: float) -> str:
    """Couleur de la rampe séquentielle à la position t ∈ [0, 1]."""
    if not math.isfinite(t):
        return rampe[0]
    return rampe[min(len(rampe) - 1, max(0, int(round(t * (len(rampe) - 1)))))]


def appliquer_theme(nom: str = THEME_DEFAUT) -> None:
    """Bascule tous les jetons de couleur et réenregistre le gabarit Plotly.

    Les fonctions de tracé lisent ces noms à l'exécution : changer de thème
    avant de construire les figures suffit, il n'y a rien d'autre à propager.
    """
    global THEME, PLANE, SURFACE, ELEVATION, INK, INK_2, INK_MUTED, GRID, AXIS
    global BORDER, VOILE, ACCENT, SERIES, SEQUENTIEL, ORDINAL
    global STATUS_GOOD, STATUS_WARNING, STATUS_SERIOUS, STATUS_CRITICAL
    global TEXTE_BON, TEXTE_MAUVAIS, STATUT_COLORS, TYPE_COLORS, CLIENT_TYPE_COLORS

    if nom not in THEMES:
        raise ValueError(f"Thème inconnu : {nom!r}. Choix : {', '.join(THEMES)}.")
    jetons = THEMES[nom]
    THEME = nom
    PLANE, SURFACE, ELEVATION = jetons["PLANE"], jetons["SURFACE"], jetons["ELEVATION"]
    INK, INK_2, INK_MUTED = jetons["INK"], jetons["INK_2"], jetons["INK_MUTED"]
    GRID, AXIS, BORDER, VOILE = jetons["GRID"], jetons["AXIS"], jetons["BORDER"], jetons["VOILE"]
    ACCENT = jetons["ACCENT"]
    SERIES = list(jetons["SERIES"])
    SEQUENTIEL = list(jetons["SEQUENTIEL"])
    ORDINAL = list(jetons["ORDINAL"])
    STATUS_GOOD, STATUS_WARNING = jetons["STATUS_GOOD"], jetons["STATUS_WARNING"]
    STATUS_SERIOUS, STATUS_CRITICAL = jetons["STATUS_SERIOUS"], jetons["STATUS_CRITICAL"]
    TEXTE_BON, TEXTE_MAUVAIS = jetons["TEXTE_BON"], jetons["TEXTE_MAUVAIS"]

    # Couleurs d'état : réservées, jamais réutilisées pour une série d'identité.
    # Le couple vert/rouge est indissociable sous deutéranopie : partout où ces
    # couleurs servent, le libellé et la valeur sont écrits sur la marque
    # (règle « icône + libellé ») et la vue tableau existe.
    STATUT_COLORS = {
        STATUT_EN_COURS: INK_MUTED,      # neutre : aucun résultat encore
        STATUT_ENVOYE: SERIES[0],        # en attente de décision
        STATUT_GAGNE: STATUS_GOOD,
        STATUT_PERDU: STATUS_CRITICAL,
        STATUT_ABANDONNE: STATUS_SERIOUS,
    }
    TYPE_COLORS = dict(zip(TYPE_ORDER, SERIES[:3]))
    CLIENT_TYPE_COLORS = dict(zip(["Institutionnel", "Distributeur", "Consultant"], SERIES[:3]))
    _register_template()


def _register_template() -> None:
    """Gabarit Plotly maison : marques fines, grille en filet, encre sobre."""
    axe = dict(
        showgrid=True, gridcolor=GRID, gridwidth=1, griddash="solid",
        zeroline=False, showline=True, linecolor=AXIS, linewidth=1,
        ticks="outside", tickcolor=AXIS, ticklen=4,
        tickfont=dict(color=INK_MUTED, size=11.5),
        title=dict(font=dict(color=INK_2, size=12)),
        automargin=True,
    )
    pio.templates[TEMPLATE_NAME] = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT_STACK, size=12.5, color=INK_2),
            paper_bgcolor="rgba(0,0,0,0)",   # la carte hôte porte le fond
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=SERIES,
            xaxis=axe,
            yaxis=axe,
            margin=dict(l=8, r=16, t=28, b=8),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                bgcolor="rgba(0,0,0,0)", borderwidth=0,
                font=dict(size=11.5, color=INK_2),
                itemsizing="constant", tracegroupgap=6, traceorder="normal",
            ),
            hoverlabel=dict(
                bgcolor=ELEVATION, bordercolor=AXIS, align="left",
                font=dict(family=FONT_STACK, size=12, color=INK),
            ),
            hovermode="closest",
            bargap=0.28,
            separators=", ",   # virgule décimale, milliers en espace fine
            colorscale=dict(sequential=[[i / (len(SEQUENTIEL) - 1), c]
                                        for i, c in enumerate(SEQUENTIEL)]),
            annotationdefaults=dict(font=dict(family=FONT_STACK, size=11.5, color=INK_2),
                                    showarrow=False),
        )
    )
    try:   # extrémités de barres arrondies : Plotly >= 5.19 seulement
        pio.templates[TEMPLATE_NAME].layout.barcornerradius = 4
    except (ValueError, AttributeError):   # pragma: no cover — Plotly plus ancien
        pass


appliquer_theme(THEME_DEFAUT)


# =============================================================================
#  RESSOURCES EMBARQUÉES — animations Lottie et police variable
# -----------------------------------------------------------------------------
#  Tout est servi depuis assets/ et jamais depuis un CDN : l'écran comme le
#  rapport doivent fonctionner sur un poste sans accès réseau.
#  Si un fichier manque, la fonction renvoie une valeur vide : l'interface perd
#  son animation, jamais son contenu.
# =============================================================================
DOSSIER_ASSETS = Path(__file__).resolve().parent / "assets"
ANIMATIONS = ("marque", "flux", "chargement", "valide")


@lru_cache(maxsize=8)
def _texte_asset(nom: str) -> str:
    try:
        return (DOSSIER_ASSETS / nom).read_text(encoding="utf-8")
    except OSError:
        return ""


@lru_cache(maxsize=8)
def _base64_asset(nom: str) -> str:
    try:
        return base64.b64encode((DOSSIER_ASSETS / nom).read_bytes()).decode("ascii")
    except OSError:
        return ""


@lru_cache(maxsize=8)
def animation(nom: str) -> dict[str, Any] | None:
    """Animation Lottie prête à sérialiser, ou None si le fichier manque."""
    brut = _texte_asset(f"lottie/{nom}.json")
    if not brut:
        return None
    try:
        return json.loads(brut)
    except json.JSONDecodeError:
        return None


def lecteur_lottie() -> str:
    """Source du lecteur Lottie (build « light », licence MIT). Vide si absent."""
    return _texte_asset("lottie_light.min.js")


def police_css() -> str:
    """Règle @font-face portant la police variable en base64.

    Inter est sous licence SIL OFL (assets/INTER-LICENSE.txt) : l'embarquer est
    autorisé, et c'est la seule façon d'obtenir la même typographie sur un poste
    hors ligne comme dans un rapport transmis par courriel.
    """
    b64 = _base64_asset("inter-variable.woff2")
    if not b64:
        return ""
    return ("@font-face{font-family:'InterVariable';font-style:normal;"
            "font-weight:100 900;font-display:swap;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2-variations');}}")


PLOT_CONFIG = {
    "displayModeBar": False,
    "responsive": True,
    "scrollZoom": False,
}

# =============================================================================
#  FORMATAGE FRANÇAIS  (espace fine insécable en séparateur de milliers)
# =============================================================================
# Typographie française : espace insécable comme séparateur de milliers et
# devant une unité. L'espace FINE insécable (U+202F) serait la forme la plus
# juste, mais elle mesure moins de deux pixels dans un texte courant : à la
# lecture, « 1 835 » redevient « 1835 ». La lisibilité prime.
NBSP = " "
ESP_UNITE = NBSP


def fmt_int(x: Any, unite: str = "") -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    s = f"{int(round(float(x))):,}".replace(",", NBSP)
    return f"{s}{ESP_UNITE}{unite}" if unite else s


def fmt_dec(x: Any, n: int = 1, unite: str = "") -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    s = f"{float(x):,.{n}f}".replace(",", "\x00").replace(".", ",").replace("\x00", NBSP)
    return f"{s}{ESP_UNITE}{unite}" if unite else s


def fmt_pct(x: Any, n: int = 0) -> str:
    """x est une proportion (0-1)."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    return fmt_dec(float(x) * 100, n, "%")


def fmt_eur(x: Any, court: bool = True) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    x = float(x)
    if court and abs(x) >= 1e9:
        return fmt_dec(x / 1e9, 2, "Md€")
    if court and abs(x) >= 1e6:
        return fmt_dec(x / 1e6, 1, "M€")
    if court and abs(x) >= 1e3:
        return fmt_dec(x / 1e3, 0, "k€")
    return fmt_int(x, "€")


def fmt_compact(x: Any) -> str:
    """Format court pour les graduations d'axe : 12 k, 1,3 M, 4,2 Md."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    x = float(x)
    if abs(x) >= 1e9:
        return fmt_dec(x / 1e9, 1, "Md")
    if abs(x) >= 1e6:
        return fmt_dec(x / 1e6, 1, "M")
    if abs(x) >= 1e3:
        return fmt_dec(x / 1e3, 0, "k")
    return fmt_int(x)


def fmt_eur_tick(x: Any) -> str:
    """Graduation monétaire : « 5 Md€ », « 2,5 Md€ », « 500 M€ »."""
    if x is None or (isinstance(x, float) and not math.isfinite(x)) or pd.isna(x):
        return "—"
    x = float(x)
    for seuil, unite in ((1e9, "Md€"), (1e6, "M€"), (1e3, "k€")):
        if abs(x) >= seuil:
            valeur = x / seuil
            return fmt_dec(valeur, 0 if abs(valeur - round(valeur)) < 0.05 else 1, unite)
    return fmt_int(x, "€")


def fmt_jours(x: Any) -> str:
    return "—" if x is None or pd.isna(x) else fmt_dec(x, 1, "j")


def fmt_p(p: float | None) -> str:
    if p is None or pd.isna(p):
        return "—"
    return "p < 0,001" if p < 0.001 else f"p = {fmt_dec(p, 3)}"


MOIS_FR = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc."]
MOIS_FR_LONG = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet",
                "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def fmt_mois(ts: pd.Timestamp) -> str:
    ts = pd.Timestamp(ts)
    return f"{MOIS_FR[ts.month - 1]} {ts.year}"


def fmt_date(d: Any) -> str:
    if d is None or pd.isna(d):
        return "—"
    d = pd.Timestamp(d)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


# =============================================================================
#  BOÎTE À OUTILS STATISTIQUE
#  Implémentée à la main (bêta incomplète régularisée) pour éviter SciPy :
#  une dépendance de 60 Mo pour trois p-values ne se justifie pas.
#  Validée contre les tables de Student dans le bloc d'auto-test en bas de
#  fichier (`python core.py`).
# =============================================================================
def _betacf(a: float, b: float, x: float) -> float:
    """Fraction continue de Lentz pour la fonction bêta incomplète."""
    MAXIT, EPS, FPMIN = 300, 3.0e-16, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = FPMIN if abs(d) < FPMIN else d
        c = 1.0 + aa / c
        c = FPMIN if abs(c) < FPMIN else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def betainc_reg(a: float, b: float, x: float) -> float:
    """Fonction bêta incomplète régularisée I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    back = math.exp(lbeta + b * math.log1p(-x) + a * math.log(x))
    return 1.0 - back * _betacf(b, a, 1.0 - x) / b


def t_sf_two_sided(t: float, df: float) -> float:
    """P(|T| > |t|) pour une loi de Student à `df` degrés de liberté."""
    if df <= 0 or not math.isfinite(t):
        return float("nan")
    t = abs(float(t))
    return betainc_reg(df / 2.0, 0.5, df / (df + t * t))


def t_ppf(p: float, df: float) -> float:
    """Quantile de Student (bissection sur la fonction de répartition)."""
    if df <= 0:
        return float("nan")
    if p <= 0.5:
        return -t_ppf(1.0 - p, df)
    lo, hi = 0.0, 200.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        cdf = 1.0 - 0.5 * t_sf_two_sided(mid, df)
        if cdf < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def z_ppf(p: float) -> float:
    """Quantile de la loi normale centrée réduite (bissection sur erf)."""
    if not 0.0 < p < 1.0:
        return float("nan")
    lo, hi = -12.0, 12.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def wilson_ci(succes: int, total: int, niveau: float = 0.95) -> tuple[float, float]:
    """Intervalle de confiance de Wilson : robuste aux petits effectifs,
    contrairement à l'intervalle normal qui déborde de [0, 1]."""
    if total <= 0:
        return (float("nan"), float("nan"))
    z = z_ppf(0.5 + niveau / 2.0)
    p = succes / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    marge = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - marge), min(1.0, centre + marge))


@dataclass(frozen=True)
class OLSResult:
    """Régression linéaire simple y = a + b·x, avec inférence complète."""
    n: int
    pente: float
    ordonnee: float
    r2: float
    r2_ajuste: float
    stderr_pente: float
    t_stat: float
    p_value: float
    ic_pente: tuple[float, float]
    sigma: float          # écart-type résiduel
    x_moyen: float
    sxx: float

    @property
    def significatif(self) -> bool:
        return bool(np.isfinite(self.p_value) and self.p_value < ALPHA)

    def predire(self, x: Iterable[float]) -> np.ndarray:
        x = np.asarray(list(x), dtype=float)
        return self.ordonnee + self.pente * x

    def bande(self, x: Iterable[float], niveau: float = 0.95,
              prediction: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """Bande de confiance (moyenne) ou de prédiction (observation)."""
        x = np.asarray(list(x), dtype=float)
        ddl = self.n - 2
        if ddl <= 0 or not math.isfinite(self.sigma) or self.sxx <= 0:
            nan = np.full_like(x, np.nan, dtype=float)
            return nan, nan
        t = t_ppf(0.5 + niveau / 2.0, ddl)
        base = 1.0 / self.n + (x - self.x_moyen) ** 2 / self.sxx
        se = self.sigma * np.sqrt(base + (1.0 if prediction else 0.0))
        centre = self.predire(x)
        return centre - t * se, centre + t * se


def ols(x: Sequence[float], y: Sequence[float]) -> OLSResult | None:
    """Moindres carrés ordinaires sur deux vecteurs (NaN écartés)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = x.size
    if n < 3 or np.allclose(x, x[0]):
        return None
    x_moyen, y_moyen = x.mean(), y.mean()
    sxx = float(((x - x_moyen) ** 2).sum())
    sxy = float(((x - x_moyen) * (y - y_moyen)).sum())
    syy = float(((y - y_moyen) ** 2).sum())
    pente = sxy / sxx
    ordonnee = y_moyen - pente * x_moyen
    residus = y - (ordonnee + pente * x)
    sse = float((residus ** 2).sum())
    ddl = n - 2
    sigma = math.sqrt(sse / ddl) if ddl > 0 else float("nan")
    r2 = 1.0 - sse / syy if syy > 0 else float("nan")
    r2_aj = 1.0 - (1.0 - r2) * (n - 1) / ddl if ddl > 0 and math.isfinite(r2) else float("nan")
    se_pente = sigma / math.sqrt(sxx) if sxx > 0 else float("nan")
    t_stat = pente / se_pente if se_pente else float("nan")
    p = t_sf_two_sided(t_stat, ddl) if math.isfinite(t_stat) else float("nan")
    t_crit = t_ppf(0.975, ddl) if ddl > 0 else float("nan")
    return OLSResult(
        n=int(n), pente=float(pente), ordonnee=float(ordonnee), r2=float(r2),
        r2_ajuste=float(r2_aj), stderr_pente=float(se_pente), t_stat=float(t_stat),
        p_value=float(p), ic_pente=(pente - t_crit * se_pente, pente + t_crit * se_pente),
        sigma=float(sigma), x_moyen=float(x_moyen), sxx=sxx,
    )


@dataclass(frozen=True)
class Coefficient:
    nom: str
    valeur: float
    stderr: float
    t_stat: float
    p_value: float
    ic_bas: float
    ic_haut: float

    @property
    def significatif(self) -> bool:
        return bool(np.isfinite(self.p_value) and self.p_value < ALPHA)


@dataclass(frozen=True)
class MultiOLSResult:
    n: int
    r2: float
    r2_ajuste: float
    coefficients: list[Coefficient]
    cible: str

    @property
    def explicatives(self) -> list[Coefficient]:
        return [c for c in self.coefficients if c.nom != "Constante"]


def ols_multiple(X: pd.DataFrame, y: pd.Series, cible: str = "y") -> MultiOLSResult | None:
    """Régression multiple (matrice de conception + constante) avec t et p par
    coefficient. numpy.linalg.lstsq + variance sigma²·(XᵀX)⁻¹ : c'est tout ce
    qu'exige une analyse de facteurs explicatifs honnête."""
    data = X.copy()
    data["__y__"] = y.to_numpy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    if len(data) < len(X.columns) + 3:
        return None
    yv = data.pop("__y__").to_numpy(dtype=float)
    noms = ["Constante"] + list(data.columns)
    Xm = np.column_stack([np.ones(len(data)), data.to_numpy(dtype=float)])
    n, k = Xm.shape
    if n <= k:
        return None
    beta, *_ = np.linalg.lstsq(Xm, yv, rcond=None)
    residus = yv - Xm @ beta
    sse = float(residus @ residus)
    sst = float(((yv - yv.mean()) ** 2).sum())
    ddl = n - k
    sigma2 = sse / ddl
    try:
        xtx_inv = np.linalg.pinv(Xm.T @ Xm)
    except np.linalg.LinAlgError:
        return None
    se = np.sqrt(np.maximum(np.diag(sigma2 * xtx_inv), 0.0))
    t_crit = t_ppf(0.975, ddl)
    coefs: list[Coefficient] = []
    for nom, b, s in zip(noms, beta, se):
        t_stat = b / s if s > 0 else float("nan")
        p = t_sf_two_sided(t_stat, ddl) if math.isfinite(t_stat) else float("nan")
        coefs.append(Coefficient(nom=nom, valeur=float(b), stderr=float(s),
                                 t_stat=float(t_stat), p_value=float(p),
                                 ic_bas=float(b - t_crit * s), ic_haut=float(b + t_crit * s)))
    r2 = 1.0 - sse / sst if sst > 0 else float("nan")
    r2_aj = 1.0 - (1.0 - r2) * (n - 1) / ddl if math.isfinite(r2) else float("nan")
    return MultiOLSResult(n=int(n), r2=float(r2), r2_ajuste=float(r2_aj),
                          coefficients=coefs, cible=cible)


# =============================================================================
#  GÉNÉRATEUR DE DONNÉES SYNTHÉTIQUES
#  Produit un fichier "brut" volontairement SALE (casse hétérogène, accents
#  manquants, dates et montants en texte, doublons, trous) et aux noms de
#  colonnes de COLUMN_MAP : la chaîne de normalisation est donc réellement
#  exercée, et non court-circuitée.
# =============================================================================
_CLIENTS: list[tuple[str, str, str, str]] = [
    # (nom, type de client, pays, langue)
    ("Caisse de Retraite Helvetia", "Institutionnel", "Suisse", "Français"),
    ("Fondation Van der Berg", "Institutionnel", "Pays-Bas", "Anglais"),
    ("Régime de Prévoyance Atlantique", "Institutionnel", "France", "Français"),
    ("Assurances Mutuelles du Nord", "Institutionnel", "France", "Français"),
    ("Pensioenfonds Rijnmond", "Institutionnel", "Pays-Bas", "Anglais"),
    ("Nordic Pension Alliance", "Institutionnel", "Suède", "Anglais"),
    ("Fondo Previdenza Lombarda", "Institutionnel", "Italie", "Italien"),
    ("Stiftung Rheinland Vorsorge", "Institutionnel", "Allemagne", "Allemand"),
    ("Caja de Pensiones Ibérica", "Institutionnel", "Espagne", "Espagnol"),
    ("Sovereign Reserve Authority", "Institutionnel", "Singapour", "Anglais"),
    ("Université de Genève — Dotation", "Institutionnel", "Suisse", "Français"),
    ("Mutuelle Santé Rhône", "Institutionnel", "France", "Français"),
    ("Banque Privée du Léman", "Distributeur", "Suisse", "Français"),
    ("Groupe Financier Bellecour", "Distributeur", "France", "Français"),
    ("Nordbank Wealth", "Distributeur", "Allemagne", "Allemand"),
    ("Plateforme Épargne Digitale", "Distributeur", "France", "Français"),
    ("Iberia Private Wealth", "Distributeur", "Espagne", "Espagnol"),
    ("Albion Wealth Partners", "Distributeur", "Royaume-Uni", "Anglais"),
    ("Banca Patrimoniale Veneta", "Distributeur", "Italie", "Italien"),
    ("Luxembourg Fund Platform", "Distributeur", "Luxembourg", "Anglais"),
    ("Assurance Vie Méditerranée", "Distributeur", "France", "Français"),
    ("Cabinet Meridian Consulting", "Consultant", "Royaume-Uni", "Anglais"),
    ("Kestrel Investment Advisory", "Consultant", "Royaume-Uni", "Anglais"),
    ("Conseil Actuariel Lutèce", "Consultant", "France", "Français"),
    ("Helvetica Investment Counsel", "Consultant", "Suisse", "Allemand"),
    ("Delta Manager Research", "Consultant", "États-Unis", "Anglais"),
    ("Benelux Fiduciary Advisors", "Consultant", "Belgique", "Néerlandais"),
]

_FONDS: list[tuple[str, str]] = [
    ("Horizon Actions Europe ISR", "Actions"),
    ("Horizon Actions Monde", "Actions"),
    ("Sélection Small Caps Euro", "Actions"),
    ("Convictions Actions Émergentes", "Actions"),
    ("Rendement Obligations Euro", "Obligataire"),
    ("Crédit Investment Grade", "Obligataire"),
    ("Obligations Vertes Souveraines", "Obligataire"),
    ("Dette Émergente Devises Fortes", "Obligataire"),
    ("Allocation Patrimoine Équilibré", "Diversifié"),
    ("Allocation Flexible Prudent", "Diversifié"),
    ("Performance Absolue Market Neutral", "Alternatif"),
    ("Stratégie Global Macro", "Alternatif"),
    ("Infrastructures Durables Europe", "Actifs réels"),
    ("Immobilier Core Zone Euro", "Actifs réels"),
    ("Trésorerie Court Terme Euro", "Monétaire"),
]

_ANALYSTES: list[tuple[str, float, float]] = [
    # (nom, part de la charge, coefficient de vitesse : < 1 = plus rapide)
    ("Camille Rousseau", 0.20, 0.86),
    ("Thomas Lefèvre", 0.18, 0.94),
    ("Inès Marchand", 0.16, 0.90),
    ("Julien Bertrand", 0.14, 1.08),
    ("Sofia Almeida", 0.13, 1.00),
    ("Marc Dubreuil", 0.11, 1.15),
    ("Léa Nguyen", 0.08, 1.05),
]

_SAISONNALITE = {1: 1.18, 2: 1.10, 3: 1.22, 4: 0.96, 5: 0.94, 6: 1.06,
                 7: 0.78, 8: 0.52, 9: 1.26, 10: 1.30, 11: 1.16, 12: 0.82}

_VARIANTES_STATUT = {
    STATUT_EN_COURS: ["en cours", "En cours", "EN COURS", "en-cours", "en cours "],
    STATUT_ENVOYE: ["envoyé", "envoye", "Envoyé", "ENVOYE", "soumis"],
    STATUT_GAGNE: ["gagné", "gagne", "Gagné", "GAGNE", "won"],
    STATUT_PERDU: ["perdu", "Perdu", "PERDU", "lost"],
    STATUT_ABANDONNE: ["abandonné", "abandonne", "Abandonné", "no bid"],
}
_VARIANTES_TYPE = {
    "RFP": ["RFP", "rfp", "Rfp", "RFP ", "R.F.P"],
    "RFI": ["RFI", "rfi", "Rfi", " RFI"],
    "DDQ": ["DDQ", "ddq", "Ddq", "DDQ ", "due diligence"],
}
_VARIANTES_TYPE_CLIENT = {
    "Institutionnel": ["Institutionnel", "institutionnel", "INSTITUTIONNEL", "institution"],
    "Distributeur": ["Distributeur", "distributeur", "wholesale", "DISTRIBUTEUR"],
    "Consultant": ["Consultant", "consultant", "CONSULTANT", "gatekeeper"],
}
_VARIANTES_LANGUE = {
    "Français": ["Français", "francais", "FR", "fr"],
    "Anglais": ["Anglais", "anglais", "EN", "english"],
    "Allemand": ["Allemand", "allemand", "DE"],
    "Italien": ["Italien", "italien", "IT"],
    "Espagnol": ["Espagnol", "espagnol", "ES"],
    "Néerlandais": ["Néerlandais", "neerlandais", "NL"],
}


def _logistique(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


def generate_fake_data(n_mois: int = FAKE_MOIS_HISTORIQUE,
                       seed: int = FAKE_SEED,
                       aujourdhui: dt.date | None = None) -> pd.DataFrame:
    """Jeu de données synthétique mais crédible : saisonnalité (creux d'août,
    pics de septembre et de janvier), croissance tendancielle, délais corrélés
    au volume de questions et à la charge du mois, taux de succès dépendant du
    segment et du respect du délai."""
    rng = np.random.default_rng(seed)
    today = pd.Timestamp(aujourdhui or dt.date.today()).normalize()
    debut = (today - pd.DateOffset(months=n_mois - 1)).replace(day=1)
    mois_debut = pd.Timestamp(debut)

    poids_analystes = np.array([a[1] for a in _ANALYSTES], dtype=float)
    poids_analystes /= poids_analystes.sum()
    appetence = {"Institutionnel": 7.0, "Distributeur": 6.0, "Consultant": 4.5}
    poids_clients = rng.dirichlet(np.array([appetence[c[1]] for c in _CLIENTS]))
    poids_fonds = rng.dirichlet(np.full(len(_FONDS), 6.0))

    lignes: list[dict[str, Any]] = []
    for i in range(n_mois):
        mois = mois_debut + pd.DateOffset(months=i)
        croissance = 1.0 + 0.019 * i                       # ~+70 % sur 3 ans
        intensite = FAKE_VOLUME_MENSUEL_BASE * croissance * _SAISONNALITE[mois.month]
        n_mois_courant = int(rng.poisson(intensite))
        if mois.year == today.year and mois.month == today.month:
            # mois en cours : au prorata des jours écoulés
            n_mois_courant = int(n_mois_courant * today.day / 30.0)
        jours_dispo = pd.date_range(mois, mois + pd.offsets.MonthEnd(0), freq="B")
        jours_dispo = jours_dispo[jours_dispo <= today]
        if len(jours_dispo) == 0 or n_mois_courant <= 0:
            continue
        charge_mois = n_mois_courant / max(intensite, 1.0)   # tension du mois

        for _ in range(n_mois_courant):
            reception = pd.Timestamp(rng.choice(jours_dispo.to_numpy()))
            type_demande = str(rng.choice(TYPE_ORDER, p=[0.38, 0.34, 0.28]))
            i_client = int(rng.choice(len(_CLIENTS), p=poids_clients))
            client, type_client, pays, langue = _CLIENTS[i_client]
            i_fonds = int(rng.choice(len(_FONDS), p=poids_fonds))
            fonds, classe = _FONDS[i_fonds]
            i_analyste = int(rng.choice(len(_ANALYSTES), p=poids_analystes))
            analyste, _, vitesse = _ANALYSTES[i_analyste]

            base_q = {"RFP": 4.85, "RFI": 3.80, "DDQ": 4.35}[type_demande]
            nb_questions = int(np.clip(rng.lognormal(base_q, 0.42), 8, 600))

            # Délai ouvré = f(volume de questions, analyste, tension du mois, aléa)
            attendu = (2.5
                       + 0.062 * nb_questions * vitesse
                       + 4.0 * (charge_mois - 1.0)
                       + {"RFP": 2.0, "RFI": 0.0, "DDQ": 1.0}[type_demande]
                       + (1.8 if langue != "Français" else 0.0))
            delai = int(np.clip(round(rng.gamma(shape=6.0, scale=max(attendu, 1.0) / 6.0)), 1, 90))
            if rng.random() < 0.04:            # dossiers lourds qui s'enlisent
                delai = int(min(90, delai * rng.uniform(1.8, 3.0)))

            mult = {"Institutionnel": 1.0, "Distributeur": 0.72, "Consultant": 1.25}[type_client]
            base_m = {"RFP": 16.6, "RFI": 16.1, "DDQ": 15.6}[type_demande]
            montant = float(np.clip(rng.lognormal(base_m, 0.85) * mult, 5e5, 8e8))

            envoi = pd.Timestamp(np.busday_offset(reception.date(), delai, roll="forward"))
            sla = SLA_JOURS_OUVRES.get(type_demande, SLA_DEFAUT)
            abandon = rng.random() < 0.035

            if abandon and rng.random() < 0.7:
                statut, envoi_final = STATUT_ABANDONNE, pd.NaT
            elif envoi > today:
                statut, envoi_final = STATUT_EN_COURS, pd.NaT
            else:
                envoi_final = envoi
                z = (-1.15
                     + {"RFP": 0.18, "RFI": 0.05, "DDQ": -0.08}[type_demande]
                     + {"Institutionnel": 0.08, "Distributeur": 0.22, "Consultant": -0.18}[type_client]
                     + {"Actions": 0.10, "Obligataire": 0.16, "Diversifié": 0.02,
                        "Alternatif": -0.22, "Actifs réels": -0.05, "Monétaire": 0.24}[classe]
                     - 0.050 * max(0, delai - sla)
                     - 0.28 * math.log10(montant / 2.0e7)
                     + (0.14 if vitesse < 0.95 else 0.0))
                decision = envoi + pd.Timedelta(days=int(rng.integers(45, 240)))
                if decision > today:
                    statut = STATUT_ENVOYE
                else:
                    statut = STATUT_GAGNE if rng.random() < _logistique(z) else STATUT_PERDU

            lignes.append({
                "date_reception": reception, "date_envoi": envoi_final,
                "type_demande": type_demande, "client": client, "type_client": type_client,
                "pays": pays, "fonds": fonds, "classe_actifs": classe, "statut": statut,
                "analyste": analyste, "nb_questions": nb_questions, "langue": langue,
                "montant_potentiel": round(montant, 2),
            })

    propre = pd.DataFrame(lignes).sort_values("date_reception").reset_index(drop=True)
    return _salir(propre, rng)


def _salir(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Reproduit les imperfections d'un vrai export Excel."""
    brut = pd.DataFrame(index=df.index)

    def variante(valeurs: pd.Series, table: dict[str, list[str]]) -> list[Any]:
        return [rng.choice(table[v]) if v in table else v for v in valeurs]

    # Dates : 8 % saisies en texte "jj/mm/aaaa"
    def dates_mixtes(col: pd.Series) -> list[Any]:
        out: list[Any] = []
        for v in col:
            if pd.isna(v):
                out.append(pd.NaT)
            elif rng.random() < 0.08:
                out.append(f"{v.day:02d}/{v.month:02d}/{v.year}")
            else:
                out.append(v)
        return out

    brut[COLUMN_MAP["date_reception"]] = dates_mixtes(df["date_reception"])
    brut[COLUMN_MAP["date_envoi"]] = dates_mixtes(df["date_envoi"])
    brut[COLUMN_MAP["type_demande"]] = variante(df["type_demande"], _VARIANTES_TYPE)
    brut[COLUMN_MAP["client"]] = [
        v.upper() if rng.random() < 0.05 else (v + " " if rng.random() < 0.05 else v)
        for v in df["client"]
    ]
    brut[COLUMN_MAP["type_client"]] = variante(df["type_client"], _VARIANTES_TYPE_CLIENT)
    brut[COLUMN_MAP["pays"]] = [np.nan if rng.random() < 0.02 else v for v in df["pays"]]
    brut[COLUMN_MAP["fonds"]] = df["fonds"].to_numpy()
    brut[COLUMN_MAP["classe_actifs"]] = df["classe_actifs"].to_numpy()
    brut[COLUMN_MAP["statut"]] = variante(df["statut"], _VARIANTES_STATUT)
    brut[COLUMN_MAP["analyste"]] = df["analyste"].to_numpy()
    brut[COLUMN_MAP["nb_questions"]] = [
        str(v) if rng.random() < 0.03 else v for v in df["nb_questions"]
    ]
    brut[COLUMN_MAP["langue"]] = variante(df["langue"], _VARIANTES_LANGUE)
    brut[COLUMN_MAP["montant_potentiel"]] = [
        (f"{v:,.2f} €".replace(",", " ").replace(".", ","))
        if rng.random() < 0.10 else v
        for v in df["montant_potentiel"]
    ]
    # Colonne hors périmètre : doit être ignorée sans bruit
    brut["Commentaire_Interne"] = ""
    # 1,2 % de doublons stricts, comme dans tout classeur partagé
    doublons = brut.sample(frac=0.012, random_state=int(rng.integers(0, 10_000)))
    return pd.concat([brut, doublons], ignore_index=True).sample(
        frac=1.0, random_state=7).reset_index(drop=True)


# =============================================================================
#  CHARGEMENT, NORMALISATION, ENRICHISSEMENT
# =============================================================================
class DonneesInvalides(RuntimeError):
    """Levée quand le fichier source est inexploitable — message actionnable."""


@dataclass
class LoadReport:
    """Journal de qualité des données, affiché tel quel dans l'application."""
    source: str = ""
    n_lignes_source: int = 0
    n_lignes_retenues: int = 0
    colonnes_absentes: list[str] = field(default_factory=list)
    colonnes_ignorees: list[str] = field(default_factory=list)
    lignes_sans_date: int = 0
    doublons_supprimes: int = 0
    dates_illisibles: dict[str, int] = field(default_factory=dict)
    valeurs_inconnues: dict[str, list[str]] = field(default_factory=dict)
    incoherences: dict[str, int] = field(default_factory=dict)
    horodatage: dt.datetime = field(default_factory=dt.datetime.now)

    @property
    def alertes(self) -> list[str]:
        msgs: list[str] = []
        if self.colonnes_absentes:
            libelles = ", ".join(COLUMN_MAP.get(c, c) for c in self.colonnes_absentes)
            msgs.append(f"Colonnes absentes du fichier, analyses correspondantes masquées : {libelles}.")
        if self.lignes_sans_date:
            msgs.append(f"{fmt_int(self.lignes_sans_date)} ligne(s) sans date de réception exploitable, écartée(s).")
        if self.doublons_supprimes:
            msgs.append(f"{fmt_int(self.doublons_supprimes)} doublon(s) strict(s) supprimé(s).")
        for col, n in self.dates_illisibles.items():
            msgs.append(f"{fmt_int(n)} date(s) illisible(s) dans « {COLUMN_MAP.get(col, col)} ».")
        for col, vals in self.valeurs_inconnues.items():
            apercu = ", ".join(f"« {v} »" for v in vals[:5])
            suite = " …" if len(vals) > 5 else ""
            msgs.append(f"Modalité(s) non reconnue(s) dans « {COLUMN_MAP.get(col, col)} » : {apercu}{suite} "
                        f"→ à ajouter dans la table de normalisation.")
        for libelle, n in self.incoherences.items():
            msgs.append(f"{fmt_int(n)} ligne(s) : {libelle}.")
        return msgs

    @property
    def est_propre(self) -> bool:
        return not self.alertes


def _strip_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte)
                   if not unicodedata.combining(c))


def _cle(valeur: Any) -> str:
    """Clé de comparaison tolérante : minuscules, sans accent, sans ponctuation
    de séparation. « Date Réception » == « date_reception » == « DATE-RECEPTION »."""
    if valeur is None or (isinstance(valeur, float) and math.isnan(valeur)):
        return ""
    texte = _strip_accents(str(valeur)).lower().strip()
    texte = re.sub(r"[\s_\-./]+", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def _resoudre_colonnes(colonnes: Iterable[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """Associe chaque champ interne à la colonne réelle du fichier."""
    index = {}
    for col in colonnes:
        index.setdefault(_cle(col), col)
    trouvees: dict[str, str] = {}
    absentes: list[str] = []
    for champ, nom_attendu in COLUMN_MAP.items():
        candidats = [nom_attendu, champ, *COLUMN_ALIASES.get(champ, [])]
        reelle = next((index[c] for c in map(_cle, candidats) if c in index), None)
        if reelle is None:
            absentes.append(champ)
        else:
            trouvees[champ] = reelle
    utilisees = set(trouvees.values())
    ignorees = [c for c in colonnes if c not in utilisees]
    return trouvees, absentes, ignorees


def _vers_datetime(serie: pd.Series) -> tuple[pd.Series, int]:
    """Parse une colonne de dates hétérogène : datetime, texte jj/mm/aaaa,
    numéro de série Excel. Retourne la série et le nombre d'échecs."""
    if serie.empty:
        return pd.to_datetime(serie, errors="coerce"), 0
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie.dt.tz_localize(None) if getattr(serie.dtype, "tz", None) else serie, 0

    brut = serie.copy()
    resultat = pd.Series(pd.NaT, index=serie.index, dtype="datetime64[ns]")

    numerique = pd.to_numeric(brut, errors="coerce")
    masque_serie_excel = numerique.between(20000, 60000) & brut.map(
        lambda v: not isinstance(v, str) or _cle(v).replace(" ", "").isdigit())
    if masque_serie_excel.any():
        resultat.loc[masque_serie_excel] = pd.to_datetime(
            numerique[masque_serie_excel], unit="D", origin="1899-12-30", errors="coerce")

    reste = ~masque_serie_excel
    if reste.any():
        try:
            # format="mixed" n'existe qu'à partir de pandas 2.0 : sur 1.x il
            # serait pris pour un format littéral et produirait des NaT muets.
            parse = (pd.to_datetime(brut[reste], errors="coerce", dayfirst=True, format="mixed")
                     if _PANDAS_2 else
                     pd.to_datetime(brut[reste], errors="coerce", dayfirst=True))
        except (ValueError, TypeError):
            parse = pd.to_datetime(brut[reste], errors="coerce", dayfirst=True)
        resultat.loc[reste] = parse

    non_vide = brut.notna() & (brut.astype(str).str.strip() != "")
    echecs = int((non_vide & resultat.isna()).sum())
    return resultat.dt.normalize(), echecs


def _vers_nombre(serie: pd.Series) -> pd.Series:
    """Accepte 12500, « 12 500,50 € », « 12,500.50 » et les cellules vides."""
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    def convertir(v: Any) -> float:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return float("nan")
        if isinstance(v, (int, float, np.integer, np.floating)):
            return float(v)
        texte = re.sub(r"[^\d,.\-]", "", str(v).replace(" ", "").replace(" ", ""))
        if not texte or texte in {"-", ".", ","}:
            return float("nan")
        if "," in texte and "." in texte:               # 12.500,50 ou 12,500.50
            texte = (texte.replace(".", "").replace(",", ".")
                     if texte.rfind(",") > texte.rfind(".") else texte.replace(",", ""))
        elif "," in texte:
            texte = texte.replace(",", ".")
        try:
            return float(texte)
        except ValueError:
            return float("nan")

    return serie.map(convertir).astype(float)


def _nettoyer_texte(serie: pd.Series) -> pd.Series:
    texte = serie.astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    return texte.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA, "-": pd.NA, "n/a": pd.NA})


def _unifier_libelles(serie: pd.Series) -> pd.Series:
    """« BNP PARIBAS », « bnp paribas » et « BNP Paribas  » désignent le même
    client : on retient l'orthographe la plus fréquente."""
    valides = serie.dropna()
    if valides.empty:
        return serie
    cles = valides.map(_cle)
    canon: dict[str, str] = {}
    for cle, groupe in valides.groupby(cles, sort=False):
        canon[cle] = groupe.value_counts().index[0]
    return serie.map(lambda v: canon.get(_cle(v), v) if pd.notna(v) else v)


def _appliquer_normalisation(serie: pd.Series, table: Mapping[str, str],
                             champ: str, rapport: LoadReport,
                             titre_par_defaut: bool = True) -> pd.Series:
    """Applique une table de normalisation ; journalise les modalités inconnues
    sans jamais les faire disparaître (elles restent visibles, titrées)."""
    index = {_cle(k): v for k, v in table.items()}
    inconnues: dict[str, None] = {}

    def convertir(v: Any) -> Any:
        if pd.isna(v):
            return VALEUR_INCONNUE
        cle = _cle(v)
        if cle in index:
            return index[cle]
        inconnues.setdefault(str(v).strip(), None)
        return str(v).strip().capitalize() if titre_par_defaut else str(v).strip()

    resultat = serie.map(convertir)
    if inconnues:
        rapport.valeurs_inconnues[champ] = sorted(inconnues)
    return resultat


def normalize(brut: pd.DataFrame, source: str = "") -> tuple[pd.DataFrame, LoadReport]:
    """Fichier brut → table canonique. Aucune ligne n'est écartée silencieusement."""
    rapport = LoadReport(source=source, n_lignes_source=len(brut))
    colonnes, absentes, ignorees = _resoudre_colonnes(list(brut.columns))
    rapport.colonnes_absentes = absentes
    rapport.colonnes_ignorees = ignorees

    manquantes_critiques = [c for c in REQUIRED_FIELDS if c in absentes]
    if manquantes_critiques:
        attendues = ", ".join(f"« {COLUMN_MAP[c]} »" for c in manquantes_critiques)
        presentes = ", ".join(f"« {c} »" for c in list(brut.columns)[:20]) or "aucune"
        raise DonneesInvalides(
            f"Colonne(s) indispensable(s) introuvable(s) : {attendues}.\n"
            f"Colonnes présentes dans le fichier : {presentes}.\n"
            f"→ Corriger COLUMN_MAP en tête de core.py (bloc [BRANCHEMENT PRINCIPAL])."
        )

    df = pd.DataFrame(index=brut.index)
    for champ, colonne in colonnes.items():
        df[champ] = brut[colonne]

    # --- Dates -------------------------------------------------------------
    for champ in ("date_reception", "date_envoi"):
        if champ in df:
            df[champ], echecs = _vers_datetime(df[champ])
            if echecs:
                rapport.dates_illisibles[champ] = echecs
        else:
            df[champ] = pd.NaT

    # --- Nombres -----------------------------------------------------------
    for champ in ("nb_questions", "montant_potentiel"):
        df[champ] = _vers_nombre(df[champ]) if champ in df else np.nan
    df.loc[df["nb_questions"] <= 0, "nb_questions"] = np.nan
    df.loc[df["montant_potentiel"] < 0, "montant_potentiel"] = np.nan

    # --- Modalités ---------------------------------------------------------
    for champ in ("type_demande", "statut", "type_client", "langue",
                  "client", "pays", "fonds", "classe_actifs", "analyste"):
        df[champ] = _nettoyer_texte(df[champ]) if champ in df else pd.Series(pd.NA, index=df.index, dtype="string")

    df["type_demande"] = _appliquer_normalisation(df["type_demande"], TYPE_NORMALIZATION, "type_demande", rapport)
    df["statut"] = _appliquer_normalisation(df["statut"], STATUS_NORMALIZATION, "statut", rapport)
    df["type_client"] = _appliquer_normalisation(df["type_client"], CLIENT_TYPE_NORMALIZATION, "type_client", rapport)
    df["langue"] = _appliquer_normalisation(df["langue"], LANGUE_NORMALIZATION, "langue", rapport)
    for champ in ("client", "pays", "fonds", "classe_actifs", "analyste"):
        df[champ] = _unifier_libelles(df[champ]).fillna(VALEUR_INCONNUE).astype(object)

    # --- Hygiène -----------------------------------------------------------
    avant = len(df)
    df = df.drop_duplicates()
    rapport.doublons_supprimes = avant - len(df)

    sans_date = df["date_reception"].isna()
    rapport.lignes_sans_date = int(sans_date.sum())
    df = df.loc[~sans_date].copy()

    # Incohérences chronologiques : on neutralise la date d'envoi, on journalise
    envoi_anterieur = df["date_envoi"].notna() & (df["date_envoi"] < df["date_reception"])
    if envoi_anterieur.any():
        rapport.incoherences["date d'envoi antérieure à la réception (envoi ignoré)"] = int(envoi_anterieur.sum())
        df.loc[envoi_anterieur, "date_envoi"] = pd.NaT

    futur = df["date_reception"] > pd.Timestamp.today().normalize()
    if futur.any():
        rapport.incoherences["date de réception dans le futur (ligne conservée)"] = int(futur.sum())

    df = df.sort_values("date_reception").reset_index(drop=True)
    rapport.n_lignes_retenues = len(df)
    return df, rapport


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les champs dérivés : calendrier, délais ouvrés, SLA, jalons."""
    df = df.copy()
    aujourdhui = pd.Timestamp.today().normalize()

    reception = df["date_reception"]
    df["mois"] = reception.dt.to_period("M").dt.to_timestamp()
    df["annee"] = reception.dt.year.astype("Int64")
    df["mois_num"] = reception.dt.month.astype("Int64")
    df["mois_nom"] = reception.dt.month.map(lambda m: MOIS_FR_LONG[int(m) - 1] if pd.notna(m) else VALEUR_INCONNUE)
    df["trimestre"] = reception.dt.to_period("Q").astype(str).str.replace(r"(\d{4})Q(\d)", r"T\2 \1", regex=True)
    df["semaine"] = reception.dt.isocalendar().week.astype("Int64")

    # Délai de traitement en jours OUVRÉS (le seul qui ait un sens en gestion)
    envoye = df["date_envoi"].notna()
    df["delai_ouvre"] = np.nan
    if envoye.any():
        debut = df.loc[envoye, "date_reception"].to_numpy("datetime64[D]")
        fin = df.loc[envoye, "date_envoi"].to_numpy("datetime64[D]")
        df.loc[envoye, "delai_ouvre"] = np.busday_count(debut, fin).astype(float)
    df["delai_calendaire"] = (df["date_envoi"] - df["date_reception"]).dt.days.astype(float)

    df["sla_cible"] = df["type_demande"].map(SLA_JOURS_OUVRES).fillna(SLA_DEFAUT).astype(float)
    df["dans_sla"] = np.where(df["delai_ouvre"].notna(), df["delai_ouvre"] <= df["sla_cible"], np.nan)
    df["dans_sla"] = pd.to_numeric(df["dans_sla"], errors="coerce")

    df["est_envoye"] = df["statut"].isin(STATUTS_ENVOYES) | df["date_envoi"].notna()
    df["est_decide"] = df["statut"].isin(STATUTS_DECIDES)
    df["est_gagne"] = df["statut"].eq(STATUT_GAGNE)
    df["est_perdu"] = df["statut"].eq(STATUT_PERDU)
    df["est_en_cours"] = df["statut"].eq(STATUT_EN_COURS)
    df["est_abandonne"] = df["statut"].eq(STATUT_ABANDONNE)

    # Ancienneté des dossiers encore ouverts (jours ouvrés depuis la réception)
    df["anciennete_ouvree"] = np.nan
    ouverts = df["est_en_cours"]
    if ouverts.any():
        debut = df.loc[ouverts, "date_reception"].to_numpy("datetime64[D]")
        fin = np.full(int(ouverts.sum()), np.datetime64(aujourdhui.date(), "D"))
        df.loc[ouverts, "anciennete_ouvree"] = np.maximum(np.busday_count(debut, fin), 0).astype(float)
    df["en_retard"] = (df["est_en_cours"] & (df["anciennete_ouvree"] > df["sla_cible"])).fillna(False)

    df["montant_gagne"] = np.where(df["est_gagne"], df["montant_potentiel"], np.nan)
    df["montant_en_jeu"] = np.where(df["statut"].isin([STATUT_EN_COURS, STATUT_ENVOYE]),
                                    df["montant_potentiel"], np.nan)
    return df


def load_data(path: str | None = None, sheet: str | None = None,
              use_fake: bool | None = None) -> tuple[pd.DataFrame, LoadReport]:
    """Point d'entrée unique : renvoie la table enrichie et son journal qualité."""
    utiliser_fake = USE_FAKE_DATA if use_fake is None else use_fake
    if utiliser_fake:
        brut = generate_fake_data()
        source = f"Données synthétiques ({fmt_int(len(brut))} lignes, graine {FAKE_SEED})"
    else:
        chemin = path or DATA_PATH
        onglet = sheet if sheet is not None else SHEET_NAME
        try:
            brut = pd.read_excel(chemin, sheet_name=onglet)
        except FileNotFoundError as exc:
            raise DonneesInvalides(
                f"Fichier introuvable : « {chemin} ».\n"
                f"→ Corriger DATA_PATH en tête de core.py, ou repasser USE_FAKE_DATA à True."
            ) from exc
        except ValueError as exc:
            raise DonneesInvalides(
                f"Onglet « {onglet} » introuvable dans « {chemin} » ({exc}).\n"
                f"→ Corriger SHEET_NAME en tête de core.py."
            ) from exc
        if isinstance(brut, dict):                     # sheet_name=None
            brut = pd.concat(brut.values(), ignore_index=True)
        source = f"{chemin} — onglet « {onglet} »"

    df, rapport = normalize(brut, source=source)
    return enrich(df), rapport


# =============================================================================
#  FILTRES
# =============================================================================
@dataclass
class Filters:
    """Sélection active. `dims` porte les filtres de modalités ; une dimension
    absente ou vide = aucune restriction."""
    date_min: dt.date | None = None
    date_max: dt.date | None = None
    dims: dict[str, list[str]] = field(default_factory=dict)

    def sans_dates(self) -> "Filters":
        return Filters(dims={k: list(v) for k, v in self.dims.items()})

    @property
    def duree_jours(self) -> int | None:
        if self.date_min and self.date_max:
            return (self.date_max - self.date_min).days + 1
        return None

    def periode_precedente(self) -> "Filters":
        """Fenêtre immédiatement antérieure, de même longueur : la seule
        comparaison honnête pour un delta."""
        duree = self.duree_jours
        if not duree or self.date_min is None:
            return Filters(dims=dict(self.dims))
        fin = self.date_min - dt.timedelta(days=1)
        return Filters(date_min=fin - dt.timedelta(days=duree - 1), date_max=fin,
                       dims={k: list(v) for k, v in self.dims.items()})

    def describe(self) -> str:
        morceaux: list[str] = []
        if self.date_min and self.date_max:
            morceaux.append(f"Du {fmt_date(self.date_min)} au {fmt_date(self.date_max)}")
        for champ, valeurs in self.dims.items():
            if valeurs:
                libelle = DIMENSIONS.get(champ, champ)
                apercu = ", ".join(map(str, valeurs[:4])) + (" …" if len(valeurs) > 4 else "")
                morceaux.append(f"{libelle} : {apercu}")
        return " · ".join(morceaux) if morceaux else "Périmètre complet, aucun filtre appliqué"

    @property
    def actif(self) -> bool:
        return bool(self.date_min or self.date_max or any(self.dims.values()))


def filter_data(df: pd.DataFrame, filtres: Filters | None) -> pd.DataFrame:
    if filtres is None or df.empty:
        return df
    masque = pd.Series(True, index=df.index)
    if filtres.date_min is not None:
        masque &= df["date_reception"] >= pd.Timestamp(filtres.date_min)
    if filtres.date_max is not None:
        masque &= df["date_reception"] <= pd.Timestamp(filtres.date_max)
    for champ, valeurs in (filtres.dims or {}).items():
        if valeurs and champ in df.columns:
            masque &= df[champ].isin(valeurs)
    return df.loc[masque].copy()


def _dispo(df: pd.DataFrame, *colonnes: str, min_modalites: int = 1) -> bool:
    """Une analyse n'est construite que si ses colonnes portent une information
    réelle : colonne présente, non vide, et pas uniquement « Non renseigné »."""
    if df.empty:
        return False
    for col in colonnes:
        if col not in df.columns:
            return False
        serie = df[col]
        if pd.api.types.is_numeric_dtype(serie):
            if serie.notna().sum() < 3:
                return False
        else:
            valides = serie[serie.notna() & (serie != VALEUR_INCONNUE)]
            if valides.empty or valides.nunique() < min_modalites:
                return False
    return True


# =============================================================================
#  AGRÉGATIONS
# =============================================================================
def agg_mensuel(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par mois calendaire, sans trou (les mois creux valent 0)."""
    if df.empty:
        return pd.DataFrame()
    base = df.groupby("mois", observed=True).agg(
        volume=("date_reception", "size"),
        envoyees=("est_envoye", "sum"),
        decidees=("est_decide", "sum"),
        gagnees=("est_gagne", "sum"),
        questions=("nb_questions", "sum"),
        delai_median=("delai_ouvre", "median"),
        delai_q1=("delai_ouvre", lambda s: s.quantile(0.25)),
        delai_q3=("delai_ouvre", lambda s: s.quantile(0.75)),
        sla_cible=("sla_cible", "mean"),
        taux_sla=("dans_sla", "mean"),
        montant=("montant_potentiel", "sum"),
        montant_gagne=("montant_gagne", "sum"),
    )
    calendrier = pd.date_range(df["mois"].min(), df["mois"].max(), freq="MS")
    base = base.reindex(calendrier)
    for col in ("volume", "envoyees", "decidees", "gagnees", "questions", "montant", "montant_gagne"):
        base[col] = base[col].fillna(0)
    base.index.name = "mois"
    base["taux_succes"] = np.where(base["decidees"] > 0, base["gagnees"] / base["decidees"], np.nan)
    base["indice"] = np.arange(len(base), dtype=float)
    base["libelle"] = [fmt_mois(m) for m in base.index]
    return base.reset_index()


def agg_type_mois(df: pd.DataFrame) -> pd.DataFrame:
    """Volume mensuel ventilé par type de demande (colonnes = types)."""
    if df.empty:
        return pd.DataFrame()
    pivot = (df.pivot_table(index="mois", columns="type_demande", values="date_reception",
                            aggfunc="size", fill_value=0)
             .reindex(pd.date_range(df["mois"].min(), df["mois"].max(), freq="MS"), fill_value=0))
    ordre = [t for t in TYPE_ORDER if t in pivot.columns] + \
            [c for c in pivot.columns if c not in TYPE_ORDER]
    pivot = pivot[ordre]
    pivot.index.name = "mois"
    return pivot.reset_index()


def agg_dimension(df: pd.DataFrame, colonne: str, min_effectif: int = 1) -> pd.DataFrame:
    """Tableau de bord d'une dimension : volume, conversion, délai, montants.
    Alimente à la fois les graphiques et leur jumeau tableau."""
    if df.empty or colonne not in df.columns:
        return pd.DataFrame()
    g = df.groupby(colonne, dropna=False, observed=True).agg(
        volume=("date_reception", "size"),
        envoyees=("est_envoye", "sum"),
        decidees=("est_decide", "sum"),
        gagnees=("est_gagne", "sum"),
        questions=("nb_questions", "sum"),
        delai_median=("delai_ouvre", "median"),
        taux_sla=("dans_sla", "mean"),
        montant=("montant_potentiel", "sum"),
        montant_gagne=("montant_gagne", "sum"),
    )
    g = g[g["volume"] >= min_effectif].copy()
    if g.empty:
        return g.reset_index()
    g["taux_succes"] = np.where(g["decidees"] > 0, g["gagnees"] / g["decidees"], np.nan)
    ic = [wilson_ci(int(k), int(n)) if n > 0 else (np.nan, np.nan)
          for k, n in zip(g["gagnees"], g["decidees"])]
    g["ic_bas"] = [a for a, _ in ic]
    g["ic_haut"] = [b for _, b in ic]
    g.index.name = colonne
    return g.reset_index().sort_values("volume", ascending=False)


def taux_succes(df: pd.DataFrame) -> tuple[float, int, int, tuple[float, float]]:
    """(taux, gagnées, décidées, IC 95 % de Wilson)."""
    if df.empty:
        return (float("nan"), 0, 0, (float("nan"), float("nan")))
    gagnees, decidees = int(df["est_gagne"].sum()), int(df["est_decide"].sum())
    taux = gagnees / decidees if decidees else float("nan")
    return taux, gagnees, decidees, wilson_ci(gagnees, decidees)


# =============================================================================
#  INDICATEURS CLÉS
# =============================================================================
@dataclass
class Kpi:
    cle: str
    libelle: str
    affichage: str
    valeur: float | None = None
    detail: str = ""
    delta_affichage: str = ""
    delta_sens: str = "neutre"      # "bon" | "mauvais" | "neutre"
    delta_direction: str = "plat"   # "hausse" | "baisse" | "plat"
    aide: str = ""


def _delta(courant: float | None, precedent: float | None, *,
           mode: str = "relatif", n: int = 0, unite: str = "",
           sens_hausse: str = "bon") -> tuple[str, str, str]:
    """Calcule l'affichage d'une variation et sa lecture métier."""
    if courant is None or precedent is None or pd.isna(courant) or pd.isna(precedent):
        return ("", "neutre", "plat")
    ecart = float(courant) - float(precedent)
    if mode == "relatif":
        if not precedent:
            return ("", "neutre", "plat")
        ratio = ecart / abs(float(precedent))
        texte = f"{'+' if ratio >= 0 else '−'}{fmt_dec(abs(ratio) * 100, 1, '%')}"
    elif mode == "points":
        texte = f"{'+' if ecart >= 0 else '−'}{fmt_dec(abs(ecart) * 100, 1)}{NBSP}pt"
    else:
        texte = f"{'+' if ecart >= 0 else '−'}{fmt_dec(abs(ecart), n, unite)}"
    if abs(ecart) < 1e-12:
        return ("stable", "neutre", "plat")
    direction = "hausse" if ecart > 0 else "baisse"
    if sens_hausse == "neutre":
        sens = "neutre"
    elif sens_hausse == "bon":
        sens = "bon" if ecart > 0 else "mauvais"
    else:
        sens = "mauvais" if ecart > 0 else "bon"
    return (texte, sens, direction)


def compute_kpis(df: pd.DataFrame, df_precedent: pd.DataFrame | None = None) -> list[Kpi]:
    """Huit indicateurs, chacun comparé à la période immédiatement antérieure
    de même durée (la seule comparaison qui ne mente pas)."""
    if df.empty:
        return []
    prec = df_precedent if df_precedent is not None and not df_precedent.empty else None

    def val(frame: pd.DataFrame | None, f: Callable[[pd.DataFrame], float]) -> float | None:
        if frame is None or frame.empty:
            return None
        try:
            v = float(f(frame))
        except (ValueError, TypeError, ZeroDivisionError):
            return None
        return v if math.isfinite(v) else None

    kpis: list[Kpi] = []

    volume = len(df)
    d = _delta(volume, val(prec, len), mode="relatif")
    kpis.append(Kpi("volume", "Demandes reçues", fmt_int(volume), float(volume),
                    detail=f"{fmt_int(df['est_envoye'].sum())} réponse(s) envoyée(s)",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Nombre de demandes reçues sur la période filtrée."))

    charge = df["nb_questions"].sum(skipna=True)
    d = _delta(charge, val(prec, lambda f: f["nb_questions"].sum(skipna=True)), mode="relatif")
    kpis.append(Kpi("charge", "Questions traitées", fmt_int(charge), float(charge),
                    detail=f"{fmt_dec(df['nb_questions'].mean(), 0)} par demande en moyenne",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Volume de questions : la vraie mesure de la charge d'un pôle RFP."))

    delai = df["delai_ouvre"].median()
    d = _delta(delai, val(prec, lambda f: f["delai_ouvre"].median()),
               mode="absolu", n=1, unite="j", sens_hausse="mauvais")
    kpis.append(Kpi("delai", "Délai médian de réponse", fmt_jours(delai),
                    None if pd.isna(delai) else float(delai),
                    detail=f"9e décile à {fmt_jours(df['delai_ouvre'].quantile(0.9))}",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Médiane des délais en jours ouvrés, réception → envoi."))

    sla = df["dans_sla"].mean()
    d = _delta(sla, val(prec, lambda f: f["dans_sla"].mean()), mode="points")
    n_sla = int(df["dans_sla"].notna().sum())
    kpis.append(Kpi("sla", "Respect du délai cible", fmt_pct(sla, 1),
                    None if pd.isna(sla) else float(sla),
                    detail=f"sur {fmt_int(n_sla)} réponse(s) envoyée(s)",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Part des réponses envoyées dans le délai cible du type de demande "
                         f"({', '.join(f'{k} : {v} j' for k, v in SLA_JOURS_OUVRES.items())})."))

    taux, gagnees, decidees, ic = taux_succes(df)
    d = _delta(taux, val(prec, lambda f: taux_succes(f)[0]), mode="points")
    kpis.append(Kpi("succes", "Taux de succès", fmt_pct(taux, 1),
                    None if pd.isna(taux) else float(taux),
                    detail=f"{fmt_int(gagnees)} gagnées sur {fmt_int(decidees)} décidées · "
                           f"IC 95 % {fmt_pct(ic[0], 1)}–{fmt_pct(ic[1], 1)}",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Gagnées / (gagnées + perdues). Les dossiers en attente de décision "
                         "sont exclus du dénominateur. " + NOTE_CENSURE))

    montant_gagne = df["montant_gagne"].sum(skipna=True)
    d = _delta(montant_gagne, val(prec, lambda f: f["montant_gagne"].sum(skipna=True)), mode="relatif")
    kpis.append(Kpi("gagne", "Encours remporté", fmt_eur(montant_gagne), float(montant_gagne),
                    detail=f"{fmt_eur(df['montant_potentiel'].sum(skipna=True))} sollicités au total",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Somme des montants potentiels des demandes gagnées. " + NOTE_CENSURE))

    pipeline = df["montant_en_jeu"].sum(skipna=True)
    n_pipeline = int(df["statut"].isin([STATUT_EN_COURS, STATUT_ENVOYE]).sum())
    d = _delta(pipeline, val(prec, lambda f: f["montant_en_jeu"].sum(skipna=True)), mode="relatif")
    kpis.append(Kpi("pipeline", "Encours en jeu", fmt_eur(pipeline), float(pipeline),
                    detail=f"{fmt_int(n_pipeline)} dossier(s) en cours ou en attente de décision",
                    delta_affichage=d[0], delta_sens=d[1], delta_direction=d[2],
                    aide="Montant des demandes non encore tranchées : le pipeline commercial."))

    en_cours = int(df["est_en_cours"].sum())
    en_retard = int(df["en_retard"].sum())
    kpis.append(Kpi("encours", "Dossiers ouverts", fmt_int(en_cours), float(en_cours),
                    detail=(f"ancienneté médiane : {fmt_jours(df.loc[df['est_en_cours'], 'anciennete_ouvree'].median())} ouvrés"
                            if en_cours else "aucun dossier en cours"),
                    delta_affichage=(f"{fmt_int(en_retard)} au-delà du délai cible" if en_retard
                                     else ("tous dans le délai" if en_cours else "")),
                    delta_sens="mauvais" if en_retard else ("bon" if en_cours else "neutre"),
                    delta_direction="plat",
                    aide="Demandes reçues dont la réponse n'est pas encore partie."))
    return kpis


# =============================================================================
#  BLOCS D'ANALYSE (figure + narration + jumeau tableau)
#  Chaque bloc est autonome et renvoie None si la donnée ne le permet pas :
#  le dashboard s'adapte au fichier, il n'impose rien.
# =============================================================================
SECTIONS: dict[str, str] = {
    "apercu": "Vue d'ensemble",
    "commercial": "Performance commerciale",
    "operations": "Efficacité opérationnelle",
    "statistiques": "Analyse statistique",
}


@dataclass
class Block:
    cle: str
    section: str
    titre: str
    accroche: str
    figure: go.Figure
    tableau: pd.DataFrame
    note: str = ""
    large: bool = False


def _fig(hauteur: int = 340, **layout: Any) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(template=TEMPLATE_NAME, height=hauteur, **layout)
    return fig


def _marque(couleur: str | Sequence[str], largeur: float = 1.5) -> dict[str, Any]:
    """Couleur + anneau de la couleur de fond : c'est l'écart de 2 px entre
    marques adjacentes, jamais une bordure décorative."""
    return dict(color=couleur, line=dict(color=SURFACE, width=largeur))


def _rgba(hex_couleur: str, alpha: float) -> str:
    h = hex_couleur.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _axe_mois(fig: go.Figure, mois: Sequence[Any], max_libelles: int = 13) -> None:
    """Libellés de mois en français, espacés pour ne jamais se chevaucher."""
    mois = list(mois)
    if not mois:
        return
    pas = max(1, math.ceil(len(mois) / max_libelles))
    ticks = mois[::pas]
    fig.update_xaxes(tickmode="array", tickvals=ticks,
                     ticktext=[fmt_mois(m) for m in ticks], tickangle=0)


def _axe_valeurs(fig: go.Figure, maxi: float, formateur: Callable[[float], str],
                 axe: str = "x", n_ticks: int = 5) -> None:
    """Graduations rondes libellées en français — « 5 Md€ » plutôt que « 5G »."""
    if not (isinstance(maxi, (int, float)) and math.isfinite(maxi)) or maxi <= 0:
        return
    brut = maxi / n_ticks
    exposant = 10.0 ** math.floor(math.log10(brut))
    pas = next((m * exposant for m in (1, 2, 2.5, 5, 10) if brut <= m * exposant), exposant * 10)
    valeurs = np.arange(0, maxi + pas * 0.5, pas)
    reglage = dict(tickmode="array", tickvals=list(valeurs),
                   ticktext=[formateur(v) for v in valeurs])
    (fig.update_xaxes if axe == "x" else fig.update_yaxes)(**reglage)


def _labels_exterieurs(fig: go.Figure, valeurs: Sequence[float], marge: float = 1.18) -> None:
    """Réserve la place des libellés posés en bout de barre (jamais rognés)."""
    maxi = max([v for v in valeurs if pd.notna(v)] or [0])
    if maxi > 0:
        fig.update_xaxes(range=[0, maxi * marge])


def _mois_complets(mensuel: pd.DataFrame) -> pd.DataFrame:
    """Écarte le mois en cours : un mois à moitié écoulé tire toute tendance
    vers le bas et fausserait aussi bien l'ajustement que le commentaire."""
    if mensuel.empty:
        return mensuel
    courant = pd.Timestamp.today().normalize().replace(day=1)
    complets = mensuel[mensuel["mois"] < courant]
    return complets if len(complets) >= 4 else mensuel


def _bloc_flux(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if mensuel.empty or len(mensuel) < 3:
        return None
    pivot = agg_type_mois(df)
    types = [c for c in pivot.columns if c != "mois"]
    fig = _fig(380, barmode="stack", hovermode="x unified")
    for i, t in enumerate(types):
        fig.add_trace(go.Bar(
            x=pivot["mois"], y=pivot[t], name=str(t),
            marker=_marque(TYPE_COLORS.get(t, SERIES[i % len(SERIES)]), 1.2),
            hovertemplate="%{y} " + str(t) + "<extra></extra>",
        ))
    complets = _mois_complets(mensuel)
    reg = ols(complets["indice"], complets["volume"])
    stats["tendance_volume"] = reg
    if reg is not None:
        fig.add_trace(go.Scatter(
            x=complets["mois"], y=reg.predire(complets["indice"]),
            mode="lines", name="Tendance (MCO)",
            line=dict(color=INK, width=2, shape="linear"),
            hovertemplate="Tendance : %{y:.1f}<extra></extra>",
        ))
    if len(complets) < len(mensuel):
        partiel = mensuel.iloc[-1]
        fig.add_annotation(x=partiel["mois"], y=partiel["volume"], yshift=16, xanchor="right",
                           text="mois en cours<br>(partiel)", align="right",
                           font=dict(size=10.5, color=INK_MUTED))
    _axe_mois(fig, mensuel["mois"])
    fig.update_yaxes(title_text="Demandes reçues", rangemode="tozero")
    fig.update_layout(bargap=0.22)

    total = int(mensuel["volume"].sum())
    if reg is not None and reg.significatif:
        sens = "progression" if reg.pente > 0 else "recul"
        accroche = (f"{fmt_int(total)} demandes sur {len(mensuel)} mois, en {sens} de "
                    f"{fmt_dec(abs(reg.pente), 1)} demande(s) par mois "
                    f"(R² = {fmt_dec(reg.r2, 2)}, {fmt_p(reg.p_value)}).")
    elif reg is not None:
        accroche = (f"{fmt_int(total)} demandes sur {len(mensuel)} mois ; la pente observée "
                    f"({fmt_dec(reg.pente, 1)}/mois) n'est pas significative ({fmt_p(reg.p_value)}) : "
                    f"le flux est stable.")
    else:
        accroche = f"{fmt_int(total)} demandes sur la période."

    tableau = pivot.copy()
    tableau.insert(1, "Total", tableau[types].sum(axis=1))
    tableau["mois"] = tableau["mois"].map(fmt_mois)
    tableau = tableau.rename(columns={"mois": "Mois"})
    return Block("flux", "apercu", "Flux de demandes par mois", accroche, fig, tableau,
                 note="La droite noire est un ajustement par moindres carrés sur le volume "
                      "mensuel total, mois en cours exclu ; elle résume la tendance, "
                      "elle ne prédit pas un mois isolé.",
                 large=True)


def _bloc_entonnoir(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if df.empty:
        return None
    recues = len(df)
    envoyees = int(df["est_envoye"].sum())
    decidees = int(df["est_decide"].sum())
    gagnees = int(df["est_gagne"].sum())
    etapes = ["Demandes reçues", "Réponses envoyées", "Décisions rendues", "Mandats gagnés"]
    valeurs = [recues, envoyees, decidees, gagnees]
    if recues == 0:
        return None
    couleurs = list(ORDINAL)[:len(etapes)]
    fig = _fig(330)
    fig.add_trace(go.Funnel(
        y=etapes, x=valeurs,
        text=[f"{fmt_int(v)}   ·   {fmt_pct(v / recues, 0)}" for v in valeurs],
        textinfo="text", textposition="inside",
        # L'encre est calculée segment par segment : la rampe change de clarté,
        # une couleur de texte fixe finirait illisible sur l'une des marches.
        insidetextfont=dict(color=[encre_lisible(c) for c in couleurs],
                            size=12.5, family=FONT_STACK),
        marker=dict(color=couleurs, line=dict(color=SURFACE, width=2)),
        connector=dict(fillcolor="rgba(0,0,0,0)", line=dict(color=GRID, width=1)),
        hovertemplate="%{y} : %{x} dossiers<extra></extra>",
    ))
    fig.update_layout(margin=dict(l=8, r=8, t=16, b=8))

    passage = [np.nan] + [valeurs[i] / valeurs[i - 1] if valeurs[i - 1] else np.nan
                          for i in range(1, len(valeurs))]
    tableau = pd.DataFrame({
        "Étape": etapes,
        "Dossiers": valeurs,
        "Part des demandes reçues": [fmt_pct(v / recues, 1) for v in valeurs],
        "Taux de passage": [fmt_pct(p, 1) if pd.notna(p) else "—" for p in passage],
    })
    stats["conversion"] = dict(zip(etapes, valeurs))
    accroche = (f"{fmt_pct(envoyees / recues, 1)} des demandes reçues ont donné lieu à une réponse, "
                f"et {fmt_pct(gagnees / decidees, 1) if decidees else '—'} des dossiers tranchés "
                f"ont été remportés.")
    return Block("entonnoir", "apercu", "Entonnoir de conversion", accroche, fig, tableau,
                 note="Les dossiers encore en attente de décision restent comptés dans "
                      "« Réponses envoyées » mais sortent du dénominateur du taux de succès.")


def _bloc_statuts(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if df.empty:
        return None
    comptes = df["statut"].value_counts()
    ordre = [s for s in STATUT_ORDER if s in comptes.index]
    ordre += [s for s in comptes.index if s not in ordre]
    valeurs = [int(comptes[s]) for s in ordre]
    total = sum(valeurs)
    fig = _fig(330)
    fig.add_trace(go.Bar(
        y=ordre, x=valeurs, orientation="h",
        marker=_marque([STATUT_COLORS.get(s, SERIES[0]) for s in ordre]),
        text=[f"{fmt_int(v)}   {fmt_pct(v / total, 1)}" for v in valeurs],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=12),
        hovertemplate="%{y} : %{x} dossiers<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Dossiers", showgrid=True)
    _labels_exterieurs(fig, valeurs, 1.28)

    tableau = pd.DataFrame({"Statut": ordre, "Dossiers": valeurs,
                            "Part": [fmt_pct(v / total, 1) for v in valeurs]})
    en_cours = int(df["est_en_cours"].sum())
    retard = int(df["en_retard"].sum())
    accroche = (f"{fmt_int(en_cours)} dossier(s) encore ouvert(s)"
                + (f", dont {fmt_int(retard)} au-delà du délai cible." if retard
                   else ", tous dans le délai cible."))
    return Block("statuts", "apercu", "État du portefeuille de demandes", accroche, fig, tableau,
                 note="Les couleurs d'état ne portent jamais l'information seules : "
                      "chaque barre est libellée et chiffrée.")


def _bloc_succes_classe(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not _dispo(df, "classe_actifs", min_modalites=2):
        return None
    agg = agg_dimension(df, "classe_actifs")
    agg = agg[agg["decidees"] >= 8].sort_values("taux_succes")
    if len(agg) < 2:
        return None
    taux_global = taux_succes(df)[0]
    x = agg["taux_succes"] * 100
    fig = _fig(max(300, 52 * len(agg) + 90))
    fig.add_trace(go.Bar(
        y=agg["classe_actifs"], x=x, orientation="h",
        marker=_marque(SERIES[0]),
        error_x=dict(type="data", symmetric=False,
                     array=(agg["ic_haut"] - agg["taux_succes"]) * 100,
                     arrayminus=(agg["taux_succes"] - agg["ic_bas"]) * 100,
                     color=INK_MUTED, thickness=1.2, width=5),
        customdata=np.stack([agg["gagnees"], agg["decidees"], agg["ic_bas"] * 100, agg["ic_haut"] * 100], axis=-1),
        hovertemplate=("<b>%{y}</b><br>Taux de succès : %{x:.1f} %"
                       "<br>%{customdata[0]:.0f} gagnées sur %{customdata[1]:.0f} décidées"
                       "<br>IC 95 % : %{customdata[2]:.1f} – %{customdata[3]:.1f} %<extra></extra>"),
    ))
    if pd.notna(taux_global):
        fig.add_vline(x=taux_global * 100, line=dict(color=INK, width=1),
                      annotation_text=f"moyenne du pôle : {fmt_pct(taux_global, 1)}",
                      annotation_position="top", annotation_font=dict(color=INK_2, size=11))
    fig.update_xaxes(title_text="Taux de succès", ticksuffix=ESP_UNITE + "%")
    # Les valeurs forment une colonne alignée à droite : elles ne peuvent
    # croiser ni les moustaches ni la ligne de moyenne.
    borne = float((agg["ic_haut"] * 100).max())
    for _, ligne in agg.iterrows():
        fig.add_annotation(x=borne * 1.05, y=ligne["classe_actifs"], xanchor="left",
                           text=f"{fmt_pct(ligne['taux_succes'], 1)}   ·   "
                                f"n = {fmt_int(ligne['decidees'])}",
                           font=dict(size=11.5, color=INK_2))
    fig.update_xaxes(range=[0, borne * 1.45])

    meilleure, pire = agg.iloc[-1], agg.iloc[0]
    accroche = (f"« {meilleure['classe_actifs']} » convertit {fmt_pct(meilleure['taux_succes'], 1)} "
                f"des dossiers tranchés contre {fmt_pct(pire['taux_succes'], 1)} pour "
                f"« {pire['classe_actifs']} »"
                + (" — écart significatif au seuil de 5 %."
                   if meilleure["ic_bas"] > pire["ic_haut"]
                   else " — mais les intervalles de confiance se recouvrent : l'écart n'est pas établi."))
    tableau = agg[["classe_actifs", "volume", "decidees", "gagnees", "taux_succes",
                   "ic_bas", "ic_haut", "delai_median", "montant_gagne"]].copy()
    tableau["taux_succes"] = tableau["taux_succes"].map(lambda v: fmt_pct(v, 1))
    tableau["ic_bas"] = tableau["ic_bas"].map(lambda v: fmt_pct(v, 1))
    tableau["ic_haut"] = tableau["ic_haut"].map(lambda v: fmt_pct(v, 1))
    tableau["delai_median"] = tableau["delai_median"].map(fmt_jours)
    tableau["montant_gagne"] = tableau["montant_gagne"].map(fmt_eur)
    tableau.columns = ["Classe d'actifs", "Demandes", "Décidées", "Gagnées", "Taux de succès",
                       "IC 95 % bas", "IC 95 % haut", "Délai médian", "Encours remporté"]
    return Block("succes_classe", "commercial", "Taux de succès par classe d'actifs",
                 accroche, fig, tableau.sort_values("Demandes", ascending=False),
                 note="Les moustaches sont l'intervalle de confiance de Wilson à 95 % : deux classes "
                      "dont les intervalles se recouvrent ne sont pas départageables. "
                      "Classes de moins de 8 décisions écartées.")


def _bloc_montants(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not _dispo(df, "montant_potentiel"):
        return None
    agg = (df.groupby("statut", observed=True)
             .agg(montant=("montant_potentiel", "sum"), dossiers=("statut", "size")))
    ordre = [s for s in STATUT_ORDER if s in agg.index] + \
            [s for s in agg.index if s not in STATUT_ORDER]
    agg = agg.reindex(ordre)
    fig = _fig(330)
    fig.add_trace(go.Bar(
        y=agg.index, x=agg["montant"], orientation="h",
        marker=_marque([STATUT_COLORS.get(s, SERIES[0]) for s in agg.index]),
        text=[fmt_eur(m) for m in agg["montant"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=12),
        customdata=agg["dossiers"].to_numpy(),
        hovertemplate="<b>%{y}</b><br>%{x:,.0f} €<br>%{customdata} dossiers<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title_text="Montant potentiel cumulé")
    _labels_exterieurs(fig, list(agg["montant"]), 1.22)
    _axe_valeurs(fig, float(agg["montant"].max()) * 1.22, fmt_eur_tick)

    gagne = float(agg["montant"].get(STATUT_GAGNE, 0.0) or 0.0)
    en_jeu = float(df["montant_en_jeu"].sum(skipna=True))
    accroche = (f"{fmt_eur(gagne)} remportés sur la période ; {fmt_eur(en_jeu)} restent en jeu "
                f"dans les dossiers non tranchés.")
    tableau = agg.reset_index()
    tableau["montant"] = tableau["montant"].map(fmt_eur)
    tableau.columns = ["Statut", "Montant potentiel", "Dossiers"]
    return Block("montants", "commercial", "Encours en jeu par statut", accroche, fig, tableau,
                 note="Montants potentiels déclarés à la réception de la demande : ils mesurent "
                      "l'enjeu commercial, pas une collecte réalisée.")


def _bloc_clients(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not _dispo(df, "client", min_modalites=3):
        return None
    agg = agg_dimension(df, "client").head(12).sort_values("volume")
    if agg.empty:
        return None
    fig = _fig(max(320, 30 * len(agg) + 90))
    fig.add_trace(go.Bar(
        y=agg["client"], x=agg["volume"], orientation="h",
        marker=_marque(SERIES[0]),
        text=[fmt_int(v) for v in agg["volume"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=12),
        customdata=np.stack([agg["taux_succes"] * 100, agg["montant"], agg["delai_median"]], axis=-1),
        hovertemplate=("<b>%{y}</b><br>%{x} demandes"
                       "<br>Taux de succès : %{customdata[0]:.0f} %"
                       "<br>Montant sollicité : %{customdata[1]:,.0f} €"
                       "<br>Délai médian : %{customdata[2]:.0f} j<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Demandes reçues")
    _labels_exterieurs(fig, list(agg["volume"]), 1.15)
    part = agg["volume"].sum() / len(df)
    accroche = (f"Les {len(agg)} premiers comptes concentrent {fmt_pct(part, 1)} des demandes ; "
                f"« {agg.iloc[-1]['client']} » en représente à lui seul "
                f"{fmt_pct(agg.iloc[-1]['volume'] / len(df), 1)}.")
    tableau = agg.sort_values("volume", ascending=False)[
        ["client", "volume", "decidees", "taux_succes", "delai_median", "montant"]].copy()
    tableau["taux_succes"] = tableau["taux_succes"].map(lambda v: fmt_pct(v, 1))
    tableau["delai_median"] = tableau["delai_median"].map(fmt_jours)
    tableau["montant"] = tableau["montant"].map(fmt_eur)
    tableau.columns = ["Client", "Demandes", "Décidées", "Taux de succès", "Délai médian", "Montant sollicité"]
    return Block("clients", "commercial", "Comptes les plus sollicitants", accroche, fig, tableau,
                 note="Classement par volume de demandes. Le taux de succès figure dans l'infobulle "
                      "et dans le tableau : il n'est pas encodé par la couleur.")


def _bloc_geographie(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not (_dispo(df, "pays", min_modalites=2) and _dispo(df, "type_client", min_modalites=2)):
        return None
    top = df["pays"].value_counts().head(8).index.tolist()
    sous = df[df["pays"].isin(top)]
    table = pd.crosstab(sous["pays"], sous["type_client"]).reindex(top[::-1])
    colonnes = [c for c in CLIENT_TYPE_COLORS if c in table.columns] + \
               [c for c in table.columns if c not in CLIENT_TYPE_COLORS]
    fig = _fig(max(320, 34 * len(table) + 110), barmode="group")
    for i, col in enumerate(colonnes):
        fig.add_trace(go.Bar(
            y=table.index, x=table[col], orientation="h", name=str(col),
            marker=_marque(CLIENT_TYPE_COLORS.get(col, SERIES[i % len(SERIES)]), 1.2),
            hovertemplate="<b>%{y}</b><br>" + str(col) + " : %{x} demandes<extra></extra>",
        ))
    fig.update_xaxes(title_text="Demandes reçues")
    # Les barres groupées se dessinent de bas en haut : la légende suit le même ordre.
    fig.update_layout(bargap=0.32, bargroupgap=0.08, legend_traceorder="reversed")
    premier = table.sum(axis=1).idxmax()
    accroche = (f"{fmt_pct(len(sous) / len(df), 1)} des demandes proviennent des huit premiers pays ; "
                f"« {premier} » arrive en tête avec {fmt_int(table.sum(axis=1).max())} demandes.")
    tableau = table.iloc[::-1].reset_index()
    tableau.insert(1, "Total", table.iloc[::-1].sum(axis=1).to_numpy())
    return Block("geographie", "commercial", "Origine des demandes par pays et type de client",
                 accroche, fig, tableau,
                 note="Huit premiers pays par volume. Trois séries au plus : au-delà, "
                      "les couleurs ne se distinguent plus de façon fiable.")


def _bloc_delai_type(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not _dispo(df, "delai_ouvre"):
        return None
    types = [t for t in TYPE_ORDER if t in df["type_demande"].unique()]
    types += [t for t in df["type_demande"].unique() if t not in types]
    types = [t for t in types if df.loc[df["type_demande"] == t, "delai_ouvre"].notna().sum() >= 5]
    if not types:
        return None
    fig = _fig(max(300, 74 * len(types) + 80))
    for t in types:
        valeurs = df.loc[df["type_demande"] == t, "delai_ouvre"].dropna()
        couleur = TYPE_COLORS.get(t, SERIES[0])
        fig.add_trace(go.Box(
            x=valeurs, name=str(t), orientation="h", boxpoints="outliers",
            marker=dict(color=_rgba(couleur, 0.45), size=5,
                        line=dict(color=SURFACE, width=1)),
            fillcolor=_rgba(couleur, 0.18),
            line=dict(color=couleur, width=1.6), whiskerwidth=0.45,
            hovertemplate="%{x:.0f} jours ouvrés<extra>" + str(t) + "</extra>",
        ))
    # Le délai cible est porté par l'étiquette d'axe ET par un repère vertical :
    # jamais par la couleur seule.
    for i, t in enumerate(types):
        cible = SLA_JOURS_OUVRES.get(t, SLA_DEFAUT)
        fig.add_shape(type="line", x0=cible, x1=cible, y0=i - 0.42, y1=i + 0.42,
                      line=dict(color=INK, width=1.6), layer="above")
    fig.update_yaxes(
        tickmode="array", tickvals=list(range(len(types))),
        ticktext=[f"{t}<br><span style='font-size:10.5px;color:{INK_MUTED}'>"
                  f"cible {SLA_JOURS_OUVRES.get(t, SLA_DEFAUT)} j</span>" for t in types],
        autorange="reversed",
    )
    fig.update_xaxes(title_text="Délai de traitement (jours ouvrés)", rangemode="tozero")
    fig.update_layout(showlegend=False, boxgap=0.45)

    lignes = []
    for t in types:
        sous = df[df["type_demande"] == t]
        v = sous["delai_ouvre"].dropna()
        lignes.append({
            "Type": t, "Réponses envoyées": int(v.size),
            "1er quartile": fmt_jours(v.quantile(0.25)), "Médiane": fmt_jours(v.median()),
            "3e quartile": fmt_jours(v.quantile(0.75)), "9e décile": fmt_jours(v.quantile(0.9)),
            "Délai cible": f"{SLA_JOURS_OUVRES.get(t, SLA_DEFAUT)} j",
            "Respect du délai": fmt_pct(sous["dans_sla"].mean(), 1),
        })
    tableau = pd.DataFrame(lignes)
    pire = min(types, key=lambda t: df.loc[df["type_demande"] == t, "dans_sla"].mean()
               if df.loc[df["type_demande"] == t, "dans_sla"].notna().any() else 1.0)
    taux_pire = df.loc[df["type_demande"] == pire, "dans_sla"].mean()
    accroche = (f"Délai médian global de {fmt_jours(df['delai_ouvre'].median())} ouvrés. "
                f"Le type « {pire} » est le plus tendu : {fmt_pct(taux_pire, 1)} des réponses "
                f"dans la cible de {SLA_JOURS_OUVRES.get(pire, SLA_DEFAUT)} jours.")
    return Block("delai_type", "operations", "Distribution des délais par type de demande",
                 accroche, fig, tableau,
                 note="Boîte = 1er au 3e quartile, trait central = médiane, moustaches = "
                      "1,5 × écart interquartile ; au-delà, chaque dossier est un point. "
                      "Le trait vertical noir marque le délai cible.")


def _bloc_delai_evolution(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if mensuel.empty or mensuel["delai_median"].notna().sum() < 3:
        return None
    m = _mois_complets(mensuel).dropna(subset=["delai_median"])
    fig = _fig(360, hovermode="x unified")
    fig.add_trace(go.Scatter(x=m["mois"], y=m["delai_q1"], mode="lines",
                             line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=m["mois"], y=m["delai_q3"], mode="lines", fill="tonexty",
                             fillcolor=_rgba(SERIES[0], 0.12), line=dict(width=0),
                             name="Intervalle interquartile",
                             hovertemplate="3e quartile : %{y:.1f} j<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=m["mois"], y=m["delai_median"], mode="lines+markers", name="Délai médian",
        line=dict(color=SERIES[0], width=2),
        marker=dict(size=8, color=SERIES[0], line=dict(color=SURFACE, width=2)),
        hovertemplate="Délai médian : %{y:.1f} j<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=m["mois"], y=m["sla_cible"], mode="lines", name="Délai cible (mix du mois)",
        line=dict(color=INK, width=1.4),
        hovertemplate="Cible : %{y:.1f} j<extra></extra>"))
    _axe_mois(fig, m["mois"])
    fig.update_yaxes(title_text="Jours ouvrés", rangemode="tozero")

    reg = ols(m["indice"], m["delai_median"])
    stats["tendance_delai"] = reg
    if reg is not None and reg.significatif:
        sens = "se dégrade" if reg.pente > 0 else "s'améliore"
        accroche = (f"Le délai médian {sens} de {fmt_dec(abs(reg.pente) * 12, 1)} jour(s) par an "
                    f"({fmt_p(reg.p_value)}).")
    else:
        accroche = (f"Délai médian stable autour de {fmt_jours(m['delai_median'].median())} "
                    f"ouvrés ; aucune dérive significative sur la période.")
    derniers = m.tail(1).iloc[0]
    accroche += (f" Dernier mois complet ({fmt_mois(derniers['mois'])}) : "
                 f"{fmt_jours(derniers['delai_median'])} pour une cible de "
                 f"{fmt_jours(derniers['sla_cible'])}.")
    tableau = m[["libelle", "volume", "envoyees", "delai_q1", "delai_median", "delai_q3",
                 "sla_cible", "taux_sla"]].copy()
    for col in ("delai_q1", "delai_median", "delai_q3", "sla_cible"):
        tableau[col] = tableau[col].map(fmt_jours)
    tableau["taux_sla"] = tableau["taux_sla"].map(lambda v: fmt_pct(v, 1))
    tableau.columns = ["Mois", "Demandes", "Réponses envoyées", "1er quartile", "Délai médian",
                       "3e quartile", "Délai cible", "Respect du délai"]
    return Block("delai_evolution", "operations", "Évolution du délai de traitement",
                 accroche, fig, tableau,
                 note="La bande claire couvre la moitié centrale des dossiers du mois. "
                      "Le délai cible varie légèrement d'un mois à l'autre : il suit le mix "
                      "RFP / RFI / DDQ reçu. Le mois en cours est exclu : seuls les dossiers "
                      "déjà envoyés y figureraient, ce qui ferait artificiellement baisser "
                      "la médiane.", large=True)


def _bloc_charge_analyste(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not _dispo(df, "analyste", min_modalites=2):
        return None
    agg = agg_dimension(df, "analyste")
    agg = agg[agg["volume"] >= 3].sort_values("questions")
    if len(agg) < 2:
        return None
    fig = _fig(max(300, 38 * len(agg) + 90))
    fig.add_trace(go.Bar(
        y=agg["analyste"], x=agg["questions"], orientation="h",
        marker=_marque(SERIES[0]),
        text=[fmt_int(q) for q in agg["questions"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=11.5),
        customdata=np.stack([agg["volume"], agg["delai_median"], agg["taux_sla"] * 100], axis=-1),
        hovertemplate=("<b>%{y}</b><br>%{x:,.0f} questions traitées"
                       "<br>%{customdata[0]:.0f} dossiers"
                       "<br>Délai médian : %{customdata[1]:.0f} j"
                       "<br>Respect du délai : %{customdata[2]:.0f} %<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Questions traitées")
    _labels_exterieurs(fig, list(agg["questions"]), 1.18)
    _axe_valeurs(fig, float(agg["questions"].max()) * 1.18, fmt_compact)

    part_max = agg["questions"].max() / agg["questions"].sum()
    accroche = (f"{fmt_int(agg['questions'].sum())} questions réparties sur {len(agg)} analystes ; "
                f"la charge la plus lourde représente {fmt_pct(part_max, 1)} du total.")
    tableau = agg.sort_values("questions", ascending=False)[
        ["analyste", "volume", "questions", "delai_median", "taux_sla", "taux_succes"]].copy()
    tableau["delai_median"] = tableau["delai_median"].map(fmt_jours)
    tableau["taux_sla"] = tableau["taux_sla"].map(lambda v: fmt_pct(v, 1))
    tableau["taux_succes"] = tableau["taux_succes"].map(lambda v: fmt_pct(v, 1))
    tableau.columns = ["Analyste", "Dossiers", "Questions traitées", "Délai médian",
                       "Respect du délai", "Taux de succès"]
    return Block("charge_analyste", "operations", "Répartition de la charge par analyste",
                 accroche, fig, tableau,
                 note="Vue de charge, pas de performance : le nombre de questions dépend du type "
                      "de dossier reçu, et le taux de succès dépend d'abord du marché adressé.")


def _bloc_saisonnalite(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if df.empty or df["annee"].nunique() < 2:
        return None
    pivot = (df.pivot_table(index="annee", columns="mois_num", values="date_reception",
                            aggfunc="size", fill_value=0)
             .reindex(columns=range(1, 13), fill_value=0).sort_index())
    # On masque les mois hors période observée : un 0 « faute de données »
    # n'est pas un 0 d'activité.
    debut, fin = df["date_reception"].min(), df["date_reception"].max()
    z = pivot.astype(float).to_numpy(copy=True)   # copie : pandas 3 renvoie une vue figée
    for i, annee in enumerate(pivot.index):
        for j, mois in enumerate(range(1, 13)):
            borne = pd.Timestamp(year=int(annee), month=mois, day=1)
            if borne < debut.replace(day=1) or borne > fin.replace(day=1):
                z[i, j] = np.nan
    fig = _fig(max(260, 46 * len(pivot) + 110))
    fig.add_trace(go.Heatmap(
        z=z, x=MOIS_FR, y=[str(a) for a in pivot.index],
        colorscale=[[i / (len(SEQUENTIEL) - 1), c] for i, c in enumerate(SEQUENTIEL)],
        xgap=2, ygap=2, hoverongaps=False,
        colorbar=dict(title=dict(text="Demandes", font=dict(size=11, color=INK_2)),
                      thickness=10, outlinewidth=0, tickfont=dict(size=11, color=INK_MUTED),
                      len=0.85),
        hovertemplate="%{x} %{y} : %{z:.0f} demandes<extra></extra>",
    ))
    maxi = np.nanmax(z) if np.isfinite(np.nanmax(z)) else 1.0
    for i, annee in enumerate(pivot.index):
        for j in range(12):
            if np.isfinite(z[i, j]):
                # Encre déduite de la couleur réelle de la cellule : valable
                # quel que soit le thème et quel que soit le sens de la rampe.
                fond = couleur_rampe(SEQUENTIEL, z[i, j] / maxi if maxi else 0.0)
                fig.add_annotation(x=MOIS_FR[j], y=str(annee), text=fmt_int(z[i, j]),
                                   font=dict(size=11, color=encre_lisible(fond)))
    fig.update_xaxes(showgrid=False, showline=False, ticks="")
    fig.update_yaxes(showgrid=False, showline=False, ticks="", autorange="reversed")

    profil = (df.groupby(["annee", "mois_num"], observed=True).size()
                .groupby("mois_num").mean())   # moyenne des années où le mois existe
    creux, pic = int(profil.idxmin()), int(profil.idxmax())
    accroche = (f"Activité maximale en {MOIS_FR_LONG[pic - 1].lower()} "
                f"({fmt_dec(profil.max(), 0)} demandes en moyenne) et minimale en "
                f"{MOIS_FR_LONG[creux - 1].lower()} ({fmt_dec(profil.min(), 0)}) : "
                f"un rapport de 1 à {fmt_dec(profil.max() / max(profil.min(), 1e-9), 1)}.")
    tableau = pivot.reset_index()
    tableau.columns = ["Année"] + MOIS_FR
    tableau["Total"] = pivot.sum(axis=1).to_numpy()
    return Block("saisonnalite", "operations", "Saisonnalité de l'activité", accroche, fig, tableau,
                 note="Les mois antérieurs ou postérieurs à la période observée sont laissés vides "
                      "plutôt que comptés à zéro. Une seule teinte, du clair au foncé : "
                      "l'intensité code la magnitude.", large=True)


def _bloc_regression_delai(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if not (_dispo(df, "delai_ouvre") and _dispo(df, "nb_questions")):
        return None
    sous = df.dropna(subset=["delai_ouvre", "nb_questions"])
    if len(sous) < 30:
        return None
    reg = ols(sous["nb_questions"], sous["delai_ouvre"])
    stats["regression_questions"] = reg
    if reg is None:
        return None
    fig = _fig(400)
    grille = np.linspace(sous["nb_questions"].min(), sous["nb_questions"].max(), 140)
    bas, haut = reg.bande(grille)
    fig.add_trace(go.Scatter(x=grille, y=bas, mode="lines", line=dict(width=0),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=grille, y=haut, mode="lines", fill="tonexty",
                             fillcolor=_rgba(INK, 0.09), line=dict(width=0),
                             name="IC 95 % de la droite", hoverinfo="skip"))
    for t in [t for t in TYPE_ORDER if t in sous["type_demande"].unique()]:
        part = sous[sous["type_demande"] == t]
        fig.add_trace(go.Scatter(
            x=part["nb_questions"], y=part["delai_ouvre"], mode="markers", name=str(t),
            marker=dict(size=8, color=_rgba(TYPE_COLORS.get(t, SERIES[0]), 0.55),
                        line=dict(color=SURFACE, width=1)),
            hovertemplate="%{x:.0f} questions · %{y:.0f} jours ouvrés<extra>" + str(t) + "</extra>",
        ))
    fig.add_trace(go.Scatter(x=grille, y=reg.predire(grille), mode="lines",
                             name="Ajustement MCO", line=dict(color=INK, width=2),
                             hovertemplate="Délai attendu : %{y:.1f} j<extra></extra>"))
    fig.update_xaxes(title_text="Nombre de questions")
    fig.update_yaxes(title_text="Délai de traitement (jours ouvrés)", rangemode="tozero")
    fig.add_annotation(
        xref="paper", yref="paper", x=0.99, y=0.06, xanchor="right", align="right",
        text=(f"délai ≈ {fmt_dec(reg.ordonnee, 1)} + {fmt_dec(reg.pente, 3)} × questions"
              f"<br>R² = {fmt_dec(reg.r2, 2)} · {fmt_p(reg.p_value)} · n = {fmt_int(reg.n)}"),
        bgcolor=VOILE, bordercolor=AXIS, borderwidth=1, borderpad=6,
        font=dict(size=11.5, color=INK_2))

    par_dix = reg.pente * 10
    accroche = (f"Chaque tranche de 10 questions supplémentaires ajoute "
                f"{fmt_dec(par_dix, 1)} jour(s) ouvré(s) de traitement "
                f"(IC 95 % : {fmt_dec(reg.ic_pente[0] * 10, 1)} à {fmt_dec(reg.ic_pente[1] * 10, 1)}). "
                f"Le volume de questions explique {fmt_pct(reg.r2, 0)} de la variance des délais.")
    tableau = pd.DataFrame({
        "Grandeur": ["Pente (jour par question)", "Effet de 10 questions", "Ordonnée à l'origine",
                     "R²", "R² ajusté", "p-value", "Observations"],
        "Valeur": [fmt_dec(reg.pente, 4), fmt_dec(par_dix, 2) + " j", fmt_dec(reg.ordonnee, 2) + " j",
                   fmt_dec(reg.r2, 3), fmt_dec(reg.r2_ajuste, 3), fmt_p(reg.p_value), fmt_int(reg.n)],
    })
    return Block("reg_questions", "statistiques",
                 "Le volume de questions explique-t-il le délai ?", accroche, fig, tableau,
                 note="Moindres carrés ordinaires. La bande grise est l'intervalle de confiance à "
                      "95 % de la droite de régression, pas celui d'un dossier individuel. "
                      "Corrélation n'est pas causalité : d'autres facteurs sont testés ci-dessous.",
                 large=True)


def _bloc_facteurs(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    """Régression multiple : quels facteurs pèsent réellement sur le délai,
    une fois les autres tenus constants ?"""
    if not (_dispo(df, "delai_ouvre") and _dispo(df, "nb_questions")):
        return None
    sous = df.dropna(subset=["delai_ouvre"]).copy()
    if len(sous) < 60:
        return None
    volumes = sous.groupby("mois", observed=True)["date_reception"].transform("size")
    X = pd.DataFrame(index=sous.index)
    X["Questions (+10)"] = sous["nb_questions"] / 10.0
    for t in ("RFP", "DDQ"):                       # modalité de référence : RFI
        if (sous["type_demande"] == t).sum() >= 15:
            X[f"Type {t}"] = (sous["type_demande"] == t).astype(float)
    if _dispo(sous, "langue", min_modalites=2):
        X["Langue étrangère"] = (~sous["langue"].isin(["Français", VALEUR_INCONNUE])).astype(float)
    X["Charge du mois (+10 demandes)"] = volumes / 10.0
    if _dispo(sous, "montant_potentiel"):
        X["Montant (+10 M€)"] = sous["montant_potentiel"] / 1e7
    if X.shape[1] < 2:
        return None

    modele = ols_multiple(X, sous["delai_ouvre"], cible="Délai de traitement (jours ouvrés)")
    stats["modele_delai"] = modele
    if modele is None:
        return None

    coefs = sorted(modele.explicatives, key=lambda c: c.valeur)
    couleurs = [STATUS_CRITICAL if c.valeur > 0 else SERIES[0] for c in coefs]
    fig = _fig(max(300, 44 * len(coefs) + 110))
    # Significativité encodée par le remplissage ET par le libellé : jamais
    # par la seule couleur.
    fig.add_trace(go.Scatter(
        x=[c.valeur for c in coefs],
        y=[c.nom + ("" if c.significatif else "  (non significatif)") for c in coefs],
        mode="markers",
        marker=dict(size=[13 if c.significatif else 11 for c in coefs],
                    color=[coul if c.significatif else SURFACE for c, coul in zip(coefs, couleurs)],
                    line=dict(color=couleurs, width=2)),
        error_x=dict(type="data", symmetric=False,
                     array=[c.ic_haut - c.valeur for c in coefs],
                     arrayminus=[c.valeur - c.ic_bas for c in coefs],
                     color=INK_MUTED, thickness=1.2, width=5),
        customdata=np.stack([[c.ic_bas for c in coefs], [c.ic_haut for c in coefs],
                             [c.p_value for c in coefs]], axis=-1),
        hovertemplate=("<b>%{y}</b><br>Effet : %{x:+.2f} jour(s)"
                       "<br>IC 95 % : %{customdata[0]:+.2f} à %{customdata[1]:+.2f}"
                       "<br>p = %{customdata[2]:.4f}<extra></extra>"),
        showlegend=False,
    ))
    fig.add_vline(x=0, line=dict(color=INK, width=1.2))
    fig.update_xaxes(title_text="Effet sur le délai, toutes choses égales par ailleurs (jours ouvrés)")
    fig.update_yaxes(showgrid=False)
    fig.add_annotation(xref="paper", yref="paper", x=0.99, y=1.10, xanchor="right",
                       text=f"R² ajusté = {fmt_dec(modele.r2_ajuste, 2)} · n = {fmt_int(modele.n)}",
                       font=dict(size=11.5, color=INK_MUTED))

    significatifs = [c for c in modele.explicatives if c.significatif]
    if significatifs:
        dominant = max(significatifs, key=lambda c: abs(c.valeur))
        sens = "allonge" if dominant.valeur > 0 else "raccourcit"
        muets = [c.nom for c in modele.explicatives if not c.significatif]
        accroche = (f"Facteur dominant : « {dominant.nom} » {sens} le délai de "
                    f"{fmt_dec(abs(dominant.valeur), 1)} jour(s) ({fmt_p(dominant.p_value)})."
                    + (f" Sans effet mesurable : {', '.join(muets[:3])}." if muets else ""))
    else:
        accroche = "Aucun des facteurs testés n'a d'effet statistiquement significatif sur le délai."
    tableau = pd.DataFrame([{
        "Facteur": c.nom, "Effet (jours)": fmt_dec(c.valeur, 3),
        "Erreur type": fmt_dec(c.stderr, 3), "IC 95 %": f"{fmt_dec(c.ic_bas, 2)} à {fmt_dec(c.ic_haut, 2)}",
        "t": fmt_dec(c.t_stat, 2), "p-value": fmt_p(c.p_value),
        "Significatif à 5 %": "Oui" if c.significatif else "Non",
    } for c in modele.coefficients])
    return Block("facteurs", "statistiques", "Facteurs explicatifs du délai de traitement",
                 accroche, fig, tableau,
                 note="Régression linéaire multiple. Chaque effet s'interprète à autres facteurs "
                      "constants. La modalité de référence des types de demande est le RFI. "
                      "Un point vide signale un effet non distinguable de zéro au seuil de 5 %.",
                 large=True)


def _bloc_projection(df: pd.DataFrame, mensuel: pd.DataFrame, stats: dict) -> Block | None:
    if mensuel.empty or len(mensuel) < 8:
        return None
    # Le mois en cours est partiel : il fausserait l'ajustement.
    mois_courant = pd.Timestamp.today().normalize().replace(day=1)
    hist = mensuel[mensuel["mois"] < mois_courant]
    if len(hist) < 6:
        hist = mensuel
    reg = ols(hist["indice"], hist["volume"])
    if reg is None:
        return None
    stats["projection"] = reg

    futur_idx = np.arange(hist["indice"].max() + 1, hist["indice"].max() + 1 + PROJECTION_MOIS)
    futur_mois = [hist["mois"].max() + pd.DateOffset(months=int(k))
                  for k in range(1, PROJECTION_MOIS + 1)]
    attendu = np.maximum(reg.predire(futur_idx), 0)
    bas, haut = reg.bande(futur_idx, prediction=True)
    bas, haut = np.maximum(bas, 0), np.maximum(haut, 0)

    fig = _fig(380, hovermode="x unified")
    fig.add_trace(go.Scatter(x=futur_mois, y=bas, mode="lines", line=dict(width=0),
                             hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=futur_mois, y=haut, mode="lines", fill="tonexty",
                             fillcolor=_rgba(SERIES[0], 0.14), line=dict(width=0),
                             name="Intervalle de prédiction 95 %",
                             hovertemplate="Borne haute : %{y:.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=hist["mois"], y=hist["volume"], mode="lines+markers", name="Volume observé",
        line=dict(color=SERIES[0], width=2),
        marker=dict(size=7, color=SERIES[0], line=dict(color=SURFACE, width=1.5)),
        hovertemplate="Observé : %{y:.0f} demandes<extra></extra>"))
    fig.add_trace(go.Scatter(x=hist["mois"], y=reg.predire(hist["indice"]), mode="lines",
                             name="Tendance ajustée", line=dict(color=INK, width=1.6),
                             hovertemplate="Tendance : %{y:.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=[hist["mois"].max()] + futur_mois,
        y=np.concatenate([[reg.predire([hist["indice"].max()])[0]], attendu]),
        mode="lines+markers", name="Projection",
        line=dict(color=SERIES[0], width=2, dash="dot"),
        marker=dict(size=8, color=SURFACE, line=dict(color=SERIES[0], width=2)),
        hovertemplate="Projection : %{y:.0f} demandes<extra></extra>"))
    _axe_mois(fig, list(hist["mois"]) + futur_mois)
    fig.update_yaxes(title_text="Demandes reçues", rangemode="tozero")

    total_projete = float(np.sum(attendu))
    if reg.significatif:
        accroche = (f"À tendance inchangée, {fmt_int(total_projete)} demandes sont attendues sur "
                    f"les {PROJECTION_MOIS} prochains mois, soit {fmt_dec(total_projete / PROJECTION_MOIS, 0)} "
                    f"par mois en moyenne (tendance significative, {fmt_p(reg.p_value)}).")
    else:
        accroche = (f"La tendance n'est pas significative ({fmt_p(reg.p_value)}) : la projection "
                    f"de {fmt_int(total_projete)} demandes sur {PROJECTION_MOIS} mois vaut comme "
                    f"prolongement de la moyenne, pas comme prévision.")
    tableau = pd.DataFrame({
        "Mois": [fmt_mois(m) for m in futur_mois],
        "Volume attendu": [fmt_int(v) for v in attendu],
        "Borne basse (95 %)": [fmt_int(v) for v in bas],
        "Borne haute (95 %)": [fmt_int(v) for v in haut],
    })
    return Block("projection", "statistiques",
                 f"Projection du flux à {PROJECTION_MOIS} mois", accroche, fig, tableau,
                 note="Prolongement linéaire de la tendance observée, avec intervalle de prédiction "
                      "à 95 %. Ce modèle ignore la saisonnalité : il donne un ordre de grandeur, "
                      "pas un budget. Le mois en cours, incomplet, est exclu de l'ajustement.",
                 large=True)


_CONSTRUCTEURS: tuple[Callable[[pd.DataFrame, pd.DataFrame, dict], Block | None], ...] = (
    _bloc_flux, _bloc_entonnoir, _bloc_statuts,
    _bloc_succes_classe, _bloc_montants, _bloc_clients, _bloc_geographie,
    _bloc_delai_type, _bloc_delai_evolution, _bloc_charge_analyste, _bloc_saisonnalite,
    _bloc_regression_delai, _bloc_facteurs, _bloc_projection,
)


@dataclass
class Analysis:
    """Résultat complet d'une analyse : c'est le seul objet que consomment
    app.py (écran) et export.py (rapport HTML)."""
    df: pd.DataFrame
    filtres: Filters
    rapport: LoadReport | None
    kpis: list[Kpi]
    blocs: list[Block]
    stats: dict[str, Any] = field(default_factory=dict)
    erreurs: list[str] = field(default_factory=list)
    genere_le: dt.datetime = field(default_factory=dt.datetime.now)

    @property
    def vide(self) -> bool:
        return self.df.empty

    def section(self, cle: str) -> list[Block]:
        return [b for b in self.blocs if b.section == cle]

    @property
    def sections(self) -> list[tuple[str, str]]:
        return [(cle, libelle) for cle, libelle in SECTIONS.items() if self.section(cle)]

    @property
    def periode(self) -> str:
        if self.df.empty:
            return "—"
        return f"{fmt_date(self.df['date_reception'].min())} → {fmt_date(self.df['date_reception'].max())}"


def build_analysis(df: pd.DataFrame, filtres: Filters | None = None,
                   rapport: LoadReport | None = None,
                   df_precedent: pd.DataFrame | None = None) -> Analysis:
    """Chaîne complète : KPI + tous les blocs. Un bloc qui échoue est signalé
    dans `erreurs` mais n'interrompt jamais le reste du tableau de bord."""
    filtres = filtres or Filters()
    stats: dict[str, Any] = {}
    erreurs: list[str] = []
    kpis = compute_kpis(df, df_precedent) if not df.empty else []
    blocs: list[Block] = []
    mensuel = agg_mensuel(df) if not df.empty else pd.DataFrame()
    if not df.empty:
        for constructeur in _CONSTRUCTEURS:
            try:
                bloc = constructeur(df, mensuel, stats)
            except Exception as exc:                      # robustesse : un bloc, pas l'écran
                erreurs.append(f"{constructeur.__name__} : {type(exc).__name__} — {exc}")
                continue
            if bloc is not None:
                blocs.append(bloc)
    stats["mensuel"] = mensuel
    if df_precedent is not None and not df_precedent.empty:
        precedente = filtres.periode_precedente()
        stats["comparaison"] = (precedente.date_min, precedente.date_max)
    return Analysis(df=df, filtres=filtres, rapport=rapport, kpis=kpis, blocs=blocs,
                    stats=stats, erreurs=erreurs)


# =============================================================================
#  TABLE DÉTAILLÉE (onglet « Données » et export CSV)
# =============================================================================
COLONNES_EXPORT: dict[str, str] = {
    "date_reception": "Date de réception",
    "date_envoi": "Date d'envoi",
    "type_demande": "Type",
    "statut": "Statut",
    "client": "Client",
    "type_client": "Type de client",
    "pays": "Pays",
    "fonds": "Fonds",
    "classe_actifs": "Classe d'actifs",
    "analyste": "Analyste",
    "langue": "Langue",
    "nb_questions": "Questions",
    "delai_ouvre": "Délai (j ouvrés)",
    "sla_cible": "Délai cible",
    "montant_potentiel": "Montant potentiel (€)",
}


def table_detaillee(df: pd.DataFrame, formate: bool = True) -> pd.DataFrame:
    """Vue tabulaire lisible de la sélection (jumeau de tous les graphiques)."""
    if df.empty:
        return pd.DataFrame(columns=list(COLONNES_EXPORT.values()))
    colonnes = [c for c in COLONNES_EXPORT if c in df.columns]
    out = df[colonnes].copy()
    if formate:
        for col in ("date_reception", "date_envoi"):
            if col in out:
                out[col] = out[col].map(fmt_date)
        for col in ("nb_questions", "delai_ouvre", "sla_cible"):
            if col in out:
                out[col] = out[col].map(lambda v: "—" if pd.isna(v) else fmt_int(v))
        if "montant_potentiel" in out:
            out["montant_potentiel"] = out["montant_potentiel"].map(lambda v: fmt_eur(v, court=False))
    return out.rename(columns=COLONNES_EXPORT)


# =============================================================================
#  AUTO-TEST — `python core.py` valide la chaîne de bout en bout
# =============================================================================
def _autotest() -> None:
    print("1. Outils statistiques")
    # Valeurs de référence des tables de Student / loi normale
    assert abs(t_sf_two_sided(2.228, 10) - 0.050) < 1e-3, t_sf_two_sided(2.228, 10)
    assert abs(t_sf_two_sided(2.0, 10) - 0.0734) < 1e-3
    assert abs(t_sf_two_sided(1.96, 1e6) - 0.050) < 1e-3
    assert abs(t_ppf(0.975, 10) - 2.228) < 1e-3
    assert abs(z_ppf(0.975) - 1.95996) < 1e-4
    bas, haut = wilson_ci(50, 100)
    assert abs(bas - 0.4038) < 1e-3 and abs(haut - 0.5962) < 1e-3, (bas, haut)
    # Régression sur une relation exacte
    r = ols([1, 2, 3, 4, 5], [2.0, 4.0, 6.0, 8.0, 10.0])
    assert r is not None and abs(r.pente - 2.0) < 1e-9 and abs(r.r2 - 1.0) < 1e-9
    m = ols_multiple(pd.DataFrame({"a": [1, 2, 3, 4, 5, 6.0], "b": [1, 0, 1, 0, 1, 0.0]}),
                     pd.Series([3.0, 4.0, 7.0, 8.0, 11.0, 12.0]))
    assert m is not None and abs(m.r2 - 1.0) < 1e-6
    print("   ✓ p-values, quantiles, Wilson, MCO simple et multiple")

    print("2. Chargement et normalisation")
    df, rapport = load_data(use_fake=True)
    assert len(df) > 500 and rapport.n_lignes_retenues == len(df)
    assert set(df["statut"].unique()) <= set(STATUT_ORDER + [VALEUR_INCONNUE]), df["statut"].unique()
    assert set(df["type_demande"].unique()) <= set(TYPE_ORDER + [VALEUR_INCONNUE])
    assert df["date_reception"].notna().all()
    assert not rapport.valeurs_inconnues, rapport.valeurs_inconnues
    assert rapport.doublons_supprimes > 0, "les doublons du jeu synthétique doivent être vus"
    print(f"   ✓ {fmt_int(len(df))} lignes, {fmt_int(rapport.doublons_supprimes)} doublons écartés")

    print("3. Filtres")
    filtres = Filters(date_min=(dt.date.today() - dt.timedelta(days=365)), date_max=dt.date.today(),
                      dims={"type_demande": ["RFP", "RFI"]})
    sel = filter_data(df, filtres)
    assert 0 < len(sel) < len(df) and set(sel["type_demande"].unique()) <= {"RFP", "RFI"}
    prec = filter_data(df, filtres.periode_precedente())
    assert prec["date_reception"].max() < sel["date_reception"].min()
    print(f"   ✓ {fmt_int(len(sel))} lignes sélectionnées, {fmt_int(len(prec))} sur la période précédente")

    print("4. Analyse complète")
    analyse = build_analysis(sel, filtres, rapport, prec)
    assert not analyse.erreurs, analyse.erreurs
    assert len(analyse.kpis) == 8
    assert len(analyse.blocs) >= 12, [b.cle for b in analyse.blocs]
    for bloc in analyse.blocs:
        assert bloc.figure.data, f"{bloc.cle} : figure vide"
        assert not bloc.tableau.empty, f"{bloc.cle} : tableau vide"
        assert bloc.accroche and bloc.titre
    print(f"   ✓ {len(analyse.kpis)} KPI, {len(analyse.blocs)} blocs : "
          f"{', '.join(b.cle for b in analyse.blocs)}")

    print("5. Cas limites")
    vide = build_analysis(df.head(0), Filters(), rapport)
    assert vide.vide and not vide.blocs and not vide.erreurs
    minuscule = build_analysis(df.head(3), Filters(), rapport)
    assert not minuscule.erreurs, minuscule.erreurs
    sans_montant = df.copy()
    sans_montant["montant_potentiel"] = np.nan
    partiel = build_analysis(sans_montant, Filters(), rapport)
    assert not partiel.erreurs and "montants" not in [b.cle for b in partiel.blocs]
    print("   ✓ sélection vide, échantillon minuscule et colonne absente gérés")

    print("\nTous les contrôles sont passés.")


if __name__ == "__main__":
    _autotest()
