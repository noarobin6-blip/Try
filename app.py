# =============================================================================
#  app.py — RFP Intelligence : interface
# -----------------------------------------------------------------------------
#  Lancement :  streamlit run app.py     →  http://localhost:8501
#
#  Ce fichier ne contient AUCUN calcul métier. Il assemble : navigation,
#  filtres globaux, mise en page, drill-down, export. Toute métrique vient de
#  core.py — un chiffre affiché ici est un chiffre calculé là-bas.
# =============================================================================
from __future__ import annotations

import datetime as dt
import inspect
import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import core

st.set_page_config(
    page_title="RFP Intelligence",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"about": "RFP Intelligence — pilotage de l'activité RFP et due diligence."},
)


# --- Compatibilité des versions de Streamlit ---------------------------------
def _kw_largeur(fonction) -> dict[str, object]:
    """`use_container_width` est déprécié au profit de `width` : on choisit le
    bon mot-clé au lieu de parier sur la version installée."""
    params = inspect.signature(fonction).parameters
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


KW_PLOT = _kw_largeur(st.plotly_chart)
KW_TABLE = _kw_largeur(st.dataframe)
KW_BOUTON = _kw_largeur(st.button)
SELECTION_DISPONIBLE = "on_select" in inspect.signature(st.plotly_chart).parameters

# Architecture de l'information : chaque page répond à une question de pilotage.
PAGES: list[tuple[str, str, str, str]] = [
    # (clé, libellé, groupe, sous-titre)
    ("synthese", "Vue d'ensemble", "Pilotage",
     "Où en est l'activité, et qu'est-ce qui demande votre attention."),
    ("activite", "Activité", "Opérations",
     "Volumes reçus, capacité de traitement et délais."),
    ("rfp", "Pipeline RFP", "Opérations",
     "Appels d'offres : flux, résultats et valeur commerciale."),
    ("dd", "Due diligence", "Opérations",
     "Charge de due diligence par expertise et par géographie."),
    ("aum", "Encours & gains", "Performance",
     "Ce que l'effort commercial rapporte réellement."),
    ("esg", "ESG", "Performance",
     "Poids de la composante ESG dans les questionnaires."),
    ("insights", "Insights", "Intelligence",
     "Constats calculés sur la sélection courante, et analyse des causes."),
    ("explorateur", "Explorateur", "Données",
     "Du chiffre agrégé au dossier individuel."),
    ("donnees", "Qualité & export", "Données",
     "Journal d'import, définitions et rapport autonome."),
]
LIBELLES_PAGES = {cle: libelle for cle, libelle, _, _ in PAGES}
GROUPES = ["Pilotage", "Opérations", "Performance", "Intelligence", "Données"]

# Indicateurs mis en avant par page — la couche métrique les produit tous, la
# page choisit ceux qui répondent à sa question.
KPIS_PAR_PAGE = {
    "synthese": ["questionnaires", "dd", "rfp", "rfp_gagnes",
                 "aum", "succes", "delai_dd", "delai_rfp"],
    "activite": ["questionnaires", "dd", "rfp", "questions",
                 "delai_dd", "delai_rfp", "sla", "esg"],
    "rfp": ["rfp", "rfp_gagnes", "succes", "pipeline", "aum", "delai_rfp"],
    "dd": ["dd", "delai_dd", "sla", "questions"],
    "aum": ["aum", "rfp_gagnes", "succes", "pipeline"],
    "esg": ["esg", "questionnaires", "dd", "rfp"],
    "insights": [],
    "explorateur": [],
    "donnees": [],
}


# =============================================================================
#  THÈME — appliqué avant toute génération de style
# =============================================================================
THEMES_LISIBLES = {"institutionnel": "Institutionnel", "sombre": "Sombre",
                   "clair": "Clair (impression)"}

_theme_demande = st.session_state.get("theme", core.THEME_DEFAUT)
if _theme_demande not in core.THEMES:
    _theme_demande = core.THEME_DEFAUT
core.appliquer_theme(_theme_demande)
EST_SOMBRE = _theme_demande == "sombre"


SOMBRE_CSS = """
[data-testid="stSidebar"], .stSelectbox div[data-baseweb="select"] > div,
.stMultiSelect div[data-baseweb="select"] > div, .stTextInput input,
div[data-baseweb="popover"] div, [data-testid="stExpander"] details {
  background-color: var(--surface) !important; color: var(--ink) !important;
  border-color: var(--border) !important; }
div[data-baseweb="select"] svg, div[data-baseweb="select"] span { color: var(--ink-2) !important; }
[data-testid="stElementContainer"] .js-plotly-plot .bg { fill: transparent !important; }
label, .stSelectbox label p, .stMultiSelect label p { color: var(--ink-2) !important; }
"""


def feuille_de_style() -> str:
    sombre_css = SOMBRE_CSS if EST_SOMBRE else ""
    halo = ("radial-gradient(900px 520px at 82% -12%, color-mix(in srgb, var(--serie1) 11%, transparent), transparent 60%)"
            if EST_SOMBRE else
            "radial-gradient(1100px 600px at 88% -18%, color-mix(in srgb, var(--accent) 5%, transparent), transparent 62%)")
    return f"""
<style>
{core.police_css()}
:root {{
  --plane:{core.PLANE}; --surface:{core.SURFACE}; --elevation:{core.ELEVATION};
  --ink:{core.INK}; --ink-2:{core.INK_2}; --muted:{core.INK_MUTED};
  --grid:{core.GRID}; --border:{core.BORDER}; --serie1:{core.SERIES[0]};
  --serie2:{core.SERIES[1]}; --accent:{core.ACCENT}; --laiton:{core.ACCENT_2};
  --bon:{core.TEXTE_BON}; --mauvais:{core.TEXTE_MAUVAIS};
}}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
  background: var(--plane); color: var(--ink); font-family: {core.FONT_STACK};
}}
[data-testid="stAppViewContainer"]::before {{
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0; background:{halo};
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1.1rem 2.2rem 4rem; max-width: 1640px; position: relative; z-index: 1; }}
:focus-visible {{ outline: 2px solid var(--serie1); outline-offset: 2px; border-radius: 6px; }}

/* ------------------------------------------------------------ en-tête ----- */
.entete {{ display:flex; align-items:flex-start; gap:22px; padding-bottom:14px;
           margin-bottom:6px; border-bottom:1px solid var(--border); }}
.entete__fil {{ font-size:10.5px; letter-spacing:.14em; text-transform:uppercase;
                color:var(--muted); font-weight:650; }}
.entete__titre {{ font-size:27px; font-weight:600; letter-spacing:-.028em; margin:4px 0 5px;
                  line-height:1.1; color:var(--ink); }}
.entete__sous {{ font-size:12.5px; color:var(--ink-2); max-width:78ch; }}
.entete__meta {{ margin-left:auto; text-align:right; font-size:11px; color:var(--muted);
                 line-height:1.8; white-space:nowrap; }}
.entete__meta b {{ color:var(--ink-2); font-weight:600; }}

/* ------------------------------------------------------- filtres actifs --- */
.chips {{ display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:2px 0 10px; }}
.chip {{ display:inline-flex; align-items:center; gap:6px; font-size:11px; font-weight:560;
         padding:3px 9px; border-radius:6px; background:color-mix(in srgb, var(--serie1) 12%, transparent);
         color:var(--ink); border:1px solid color-mix(in srgb, var(--serie1) 26%, transparent); }}
.chip b {{ font-weight:650; color:var(--muted); font-size:9.5px; letter-spacing:.07em;
           text-transform:uppercase; }}
.chip--vide {{ background:transparent; border-color:var(--border); color:var(--muted); }}

/* ---------------------------------------------------------- indicateurs --- */
.kpis {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:12px; }}
.kpis + .kpis {{ margin-top:12px; }}
@media (max-width:1400px) {{ .kpis {{ grid-template-columns:repeat(3, minmax(0,1fr)); }} }}
@media (max-width:1100px) {{ .kpis {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
a.kpi, div.kpi {{ display:block; background:var(--surface); border:1px solid var(--border);
  border-radius:10px; padding:13px 15px 11px; text-decoration:none; color:inherit;
  transition:border-color .16s ease, transform .16s ease; height:100%; }}
a.kpi:hover {{ border-color:color-mix(in srgb, var(--accent) 45%, transparent);
               transform:translateY(-1px); }}
.kpi__tete {{ display:flex; align-items:baseline; gap:8px; }}
.kpi__label {{ font-size:10px; letter-spacing:.09em; text-transform:uppercase;
               color:var(--muted); font-weight:650; }}
.kpi__info {{ margin-left:auto; font-size:10px; color:var(--muted); opacity:.55; }}
.kpi__corps {{ display:flex; align-items:flex-end; justify-content:space-between; gap:10px;
               margin-top:7px; }}
.kpi__valeur {{ font-size:25px; font-weight:600; letter-spacing:-.018em; line-height:1.05;
                font-variant-numeric:tabular-nums; color:var(--ink); }}
.kpi__bas {{ display:flex; align-items:center; gap:8px; margin-top:8px; flex-wrap:wrap; }}
.kpi__detail {{ font-size:10.5px; color:var(--muted); line-height:1.4; }}
.puce {{ display:inline-flex; gap:4px; font-size:10.5px; font-weight:650; padding:2px 7px;
         border-radius:5px; white-space:nowrap; }}
.puce--bon {{ background:color-mix(in srgb, var(--bon) 14%, transparent); color:var(--bon); }}
.puce--mauvais {{ background:color-mix(in srgb, var(--mauvais) 14%, transparent); color:var(--mauvais); }}
.puce--neutre {{ background:color-mix(in srgb, var(--ink) 7%, transparent); color:var(--ink-2); }}
.note-lecture {{ font-size:11px; color:var(--muted); border-left:2px solid var(--border);
                 padding-left:11px; margin:14px 0 4px; line-height:1.55; max-width:112ch; }}

/* -------------------------------------------------------------- cartes ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  background:var(--surface); border:1px solid var(--border) !important; border-radius:12px;
  transition:border-color .16s ease; }}
[data-testid="stColumn"] > div,
[data-testid="stColumn"] > div > [data-testid="stVerticalBlock"],
[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] {{ height:100%; }}
.carte__titre {{ font-size:14.5px; font-weight:620; letter-spacing:-.012em; color:var(--ink); }}
.carte__accroche {{ font-size:12px; color:var(--ink-2); margin:5px 0 2px; line-height:1.55; }}
.carte__note {{ font-size:10.5px; color:var(--muted); line-height:1.5; margin-top:8px;
                padding-top:8px; border-top:1px solid var(--border); }}
.carte__clic {{ font-size:10px; color:var(--muted); margin-top:4px; }}

/* ------------------------------------------------------------- insights --- */
.alerte {{ background:color-mix(in srgb, var(--mauvais) 8%, var(--surface));
           border:1px solid color-mix(in srgb, var(--mauvais) 28%, transparent);
           border-left:3px solid var(--mauvais); border-radius:9px; padding:12px 15px;
           font-size:12.5px; color:var(--ink); line-height:1.5; }}
.insights {{ display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px;
             margin-bottom:6px; }}
@media (max-width:1240px) {{ .insights {{ grid-template-columns:repeat(2, minmax(0,1fr)); }} }}
a.insight, div.insight {{ background:var(--surface); border:1px solid var(--border);
            border-radius:10px; padding:15px 17px; height:100%; text-decoration:none;
            color:inherit; display:flex; flex-direction:column;
            border-left:3px solid var(--serie1); transition:border-color .16s ease; }}
a.insight:hover {{ border-color:color-mix(in srgb, var(--accent) 45%, transparent);
                   border-left-color:var(--serie1); }}
.insight__lien {{ margin-top:auto; padding-top:10px; font-size:11px; font-weight:600;
                  color:var(--accent); }}
.insight--alerte .insight__lien {{ color:var(--mauvais); }}
.insight--alerte {{ border-left-color:var(--mauvais); }}
.insight--positif {{ border-left-color:var(--bon); }}
.insight__texte {{ font-size:13px; color:var(--ink); line-height:1.5; font-weight:520; }}
.insight__appui {{ font-size:11px; color:var(--muted); margin-top:7px; }}

/* -------------------------------------------------------- barre latérale -- */
[data-testid="stSidebar"] {{ background:var(--surface); border-right:1px solid var(--border); }}
[data-testid="stSidebar"] .block-container {{ padding-top:.9rem; }}
.marque__texte {{ font-size:12.5px; font-weight:640; letter-spacing:-.01em; line-height:1.2;
                  color:var(--ink); }}
.marque__texte span {{ display:block; font-size:9px; letter-spacing:.15em; text-transform:uppercase;
  color:var(--muted); font-weight:600; margin-top:3px; }}
.nav-groupe {{ font-size:9.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted);
               font-weight:700; margin:14px 0 2px; padding-left:2px; }}
.side-info {{ font-size:10.5px; color:var(--muted); line-height:1.65; }}
.side-info b {{ color:var(--ink-2); font-weight:600; }}

/* Navigation : des boutons déguisés en lignes, pour garder les groupes. */
[data-testid="stSidebar"] .stButton button {{ width:100%; justify-content:flex-start;
  text-align:left; padding:6px 10px; border-radius:7px; font-size:12.5px; font-weight:520;
  border:1px solid transparent; background:transparent; color:var(--muted);
  transition:background .16s ease, color .16s ease; box-shadow:none; }}
[data-testid="stSidebar"] .stButton button:hover {{
  background:color-mix(in srgb, var(--ink) 6%, transparent); color:var(--ink); }}
[data-testid="stSidebar"] .stButton button[kind="primary"] {{
  background:color-mix(in srgb, var(--accent) 10%, transparent); color:var(--accent);
  font-weight:660; border-color:transparent;
  box-shadow:inset 2px 0 0 var(--accent); border-radius:0 7px 7px 0; }}
[data-testid="stSidebar"] .stButton button p {{ font-size:12.5px !important; }}

/* --------------------------------------------------------------- divers --- */
[data-testid="stExpander"] details {{ border:none !important; background:transparent; }}
[data-testid="stExpander"] summary {{ font-size:11.5px; color:var(--muted); }}
[data-testid="stExpander"] summary:hover {{ color:var(--ink-2); }}
.stDownloadButton button, .block-container .stButton button {{ border-radius:8px;
  font-size:12.5px; font-weight:600; border:1px solid var(--border);
  background:var(--elevation); color:var(--ink); }}
.block-container .stButton button[kind="primary"] {{ background:var(--accent);
  border-color:var(--accent); color:#fff; }}
[data-testid="stAlert"], [data-testid="stAlertContainer"] {{
  background:color-mix(in srgb, var(--ink) 5%, transparent) !important;
  border:1px solid var(--border); border-radius:9px; color:var(--ink-2) !important; }}
[data-testid="stAlert"] p, [data-testid="stAlertContainer"] p {{
  font-size:12px !important; color:var(--ink-2) !important; }}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:9px; }}
[data-testid="stMetricValue"] {{ font-variant-numeric:tabular-nums; }}
#MainMenu, footer, [data-testid="stAppDeployButton"] {{ display:none; }}
/* Le thème sombre repeint les surfaces des widgets, que le thème Streamlit
   (statique, défini dans config.toml) ne peut pas suivre à l'exécution. */
{sombre_css}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{ transition:none !important; animation:none !important; }}
}}
</style>
"""


st.markdown(feuille_de_style(), unsafe_allow_html=True)


# =============================================================================
#  PETITS COMPOSANTS
# =============================================================================
FLECHES = {"hausse": "▲", "baisse": "▼", "plat": ""}


def sparkline(valeurs: list[float], largeur: int = 96, hauteur: int = 24) -> str:
    """Mini-tendance en SVG : la forme de la série, sans axes ni promesse de
    précision. Le chiffre exact reste dans le graphique de la page."""
    valeurs = [v for v in valeurs if v == v]
    if len(valeurs) < 4:
        return ""
    mini, maxi = min(valeurs), max(valeurs)
    etendue = (maxi - mini) or 1.0
    pas = largeur / (len(valeurs) - 1)
    points = [(i * pas, hauteur - 2 - (v - mini) / etendue * (hauteur - 5))
              for i, v in enumerate(valeurs)]
    trace = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    fin_x, fin_y = points[-1]
    return (f'<svg width="{largeur}" height="{hauteur}" viewBox="0 0 {largeur} {hauteur}" '
            f'aria-hidden="true" style="overflow:visible">'
            f'<polyline points="{trace}" fill="none" stroke="{core.SERIES[0]}" '
            f'stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" opacity=".75"/>'
            f'<circle cx="{fin_x:.1f}" cy="{fin_y:.1f}" r="2.4" fill="{core.SERIES[0]}"/></svg>')


def carte_kpi(kpi: core.Kpi) -> str:
    """Carte d'indicateur. Cliquable quand elle mène quelque part : le chiffre
    ouvre la page qui l'explique."""
    puce = ""
    if kpi.delta_affichage:
        fleche = FLECHES.get(kpi.delta_direction, "")
        puce = (f"<span class='puce puce--{kpi.delta_sens}'>"
                f"{fleche + ' ' if fleche else ''}{kpi.delta_affichage}</span>")
    corps = (f"<div class='kpi__tete'><span class='kpi__label'>{kpi.libelle}</span>"
             f"<span class='kpi__info' aria-hidden='true'>i</span></div>"
             f"<div class='kpi__corps'><span class='kpi__valeur'>{kpi.affichage}</span>"
             f"{sparkline(kpi.serie)}</div>"
             f"<div class='kpi__bas'>{puce}"
             f"<span class='kpi__detail'>{kpi.detail}</span></div>")
    titre = kpi.aide.replace('"', "'")
    if kpi.cible and kpi.cible in LIBELLES_PAGES:
        return (f"<a class='kpi' href='?page={kpi.cible}' target='_self' title=\"{titre}\">"
                f"{corps}</a>")
    return f"<div class='kpi' title=\"{titre}\">{corps}</div>"


def bandeau_kpis(analyse: core.Analysis, cles: list[str]) -> None:
    par_cle = {k.cle: k for k in analyse.kpis}
    choisis = [par_cle[c] for c in cles if c in par_cle]
    for depart in range(0, len(choisis), 4):
        ligne = choisis[depart:depart + 4]
        st.markdown(f"<div class='kpis'>{''.join(carte_kpi(k) for k in ligne)}</div>",
                    unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _html_animation(nom: str, taille: int, boucle: bool = True) -> str:
    donnees, lecteur = core.animation(nom), core.lecteur_lottie()
    if not donnees or not lecteur:
        return ""
    return (
        f'<div id="a" style="width:{taille}px;height:{taille}px"></div>'
        f"<script>{lecteur}</script><script>"
        "var sobre=window.matchMedia('(prefers-reduced-motion: reduce)').matches;"
        f"var anim=lottie.loadAnimation({{container:document.getElementById('a'),"
        f"renderer:'svg',loop:{str(boucle).lower()},autoplay:!sobre,"
        f"animationData:{json.dumps(donnees, separators=(',', ':'))}}});"
        "if(sobre){anim.goToAndStop(anim.totalFrames-1,true);}</script>")


def animation(nom: str, taille: int, boucle: bool = True) -> None:
    code = _html_animation(nom, taille, boucle)
    if code:
        components.html(code, height=taille + 4, width=taille + 4)


# =============================================================================
#  DONNÉES
# =============================================================================
@st.cache_data(show_spinner="Chargement des données…")
def charger() -> tuple[pd.DataFrame, core.LoadReport]:
    return core.load_data()


def ecran_erreur(message: str) -> None:
    st.markdown("<div class='entete'><div><div class='entete__fil'>Configuration</div>"
                "<div class='entete__titre'>Données inaccessibles</div></div></div>",
                unsafe_allow_html=True)
    st.error(message)
    st.markdown(
        "**Pour brancher le produit sur vos données**, ouvrir `core.py` et modifier le "
        "bloc `[BRANCHEMENT PRINCIPAL]` en tête de fichier :\n\n"
        "1. `DATA_PATH` — chemin du classeur ; 2. `SHEET_NAME` — onglet ; "
        "3. `COLUMN_MAP` — nom réel de chaque colonne (la correspondance ignore casse, "
        "accents et espaces) ; 4. `USE_FAKE_DATA = False`.")
    st.stop()


try:
    df_complet, rapport = charger()
except core.DonneesInvalides as exc:
    ecran_erreur(str(exc))
except Exception as exc:                                    # pragma: no cover
    ecran_erreur(f"Erreur inattendue au chargement : {type(exc).__name__} — {exc}")

if df_complet.empty:
    ecran_erreur("Le fichier ne contient aucune ligne exploitable après normalisation.")

DATE_MIN = df_complet["date_reception"].min().date()
DATE_MAX = df_complet["date_reception"].max().date()
ANNEES = sorted(df_complet["date_reception"].dt.year.unique(), reverse=True)

PERIODES = {
    "12 derniers mois": 12,
    "24 derniers mois": 24,
    "36 derniers mois": 36,
    "Historique complet": None,
}


# =============================================================================
#  ÉTAT — page dans l'URL, filtres en session
# =============================================================================
def page_courante() -> str:
    demandee = st.query_params.get("page", st.session_state.get("page", "synthese"))
    if demandee not in LIBELLES_PAGES:
        demandee = "synthese"
    st.session_state["page"] = demandee
    return demandee


def ajouter_filtre(champ: str, valeur: str, page: str | None = None) -> bool:
    """Ajoute une modalité aux filtres actifs — c'est le drill-down.

    Streamlit interdit d'écrire dans la clé d'un widget déjà affiché : on
    recrée donc la génération de widgets en reportant l'état courant, ce qui
    préserve les autres filtres et la période.
    """
    generation = st.session_state.get("generation", 0)
    report: dict[str, list[str]] = {}
    for dimension in core.DIMENSIONS:
        valeurs = list(st.session_state.get(f"dim_{dimension}_{generation}", []))
        if valeurs:
            report[dimension] = valeurs
    deja = report.get(champ, [])
    if valeur in deja:
        return False
    report[champ] = deja + [valeur]
    periode = st.session_state.get(f"periode_{generation}")

    suivante = generation + 1
    st.session_state["generation"] = suivante
    for dimension, valeurs in report.items():
        st.session_state[f"dim_{dimension}_{suivante}"] = valeurs
    if periode is not None:
        st.session_state[f"periode_{suivante}"] = periode
    if page:
        st.query_params["page"] = page
        st.session_state["page"] = page
    return True


def aller_a(page: str, **filtres_supplementaires: object) -> None:
    """Navigue, en emportant éventuellement un filtre."""
    for champ, valeur in filtres_supplementaires.items():
        ajouter_filtre(champ, str(valeur))
    st.query_params["page"] = page
    st.session_state["page"] = page
    st.rerun()


def _reinitialiser_filtres() -> None:
    """Incrémenter la génération recrée des widgets neufs, donc vierges :
    supprimer les clés ne suffit pas, Streamlit restaurerait la valeur portée
    par le widget déjà affiché."""
    for cle in [k for k in st.session_state if k.startswith(("dim_", "periode", "bornes"))]:
        st.session_state.pop(cle, None)
    st.session_state["generation"] = st.session_state.get("generation", 0) + 1


PAGE = page_courante()


# =============================================================================
#  BARRE LATÉRALE — marque, navigation, source
# =============================================================================
def barre_laterale() -> None:
    with st.sidebar:
        colonnes = st.columns([1, 3], gap="small")
        with colonnes[0]:
            animation("marque", 42)
        with colonnes[1]:
            st.markdown("<div class='marque__texte'>RFP Intelligence"
                        "<span>Asset Management</span></div>", unsafe_allow_html=True)

        for groupe in GROUPES:
            pages = [p for p in PAGES if p[2] == groupe]
            if not pages:
                continue
            st.markdown(f"<div class='nav-groupe'>{groupe}</div>", unsafe_allow_html=True)
            for cle, libelle, _, _ in pages:
                if st.button(libelle, key=f"nav_{cle}",
                             type="primary" if cle == PAGE else "secondary", **KW_BOUTON):
                    st.query_params["page"] = cle
                    st.session_state["page"] = cle
                    st.rerun()

        st.divider()
        choix = st.selectbox("Apparence", list(THEMES_LISIBLES),
                             format_func=lambda c: THEMES_LISIBLES[c],
                             index=list(THEMES_LISIBLES).index(_theme_demande),
                             key="choix_theme")
        if choix != _theme_demande:
            st.session_state["theme"] = choix
            st.rerun()

        st.markdown(
            f"<div class='side-info'><b>Source</b><br>{rapport.source}<br><br>"
            f"<b>Profondeur</b><br>{core.fmt_date(DATE_MIN)} → {core.fmt_date(DATE_MAX)}<br><br>"
            f"<b>Lignes exploitables</b><br>{core.fmt_int(rapport.n_lignes_retenues)} sur "
            f"{core.fmt_int(rapport.n_lignes_source)}</div>", unsafe_allow_html=True)


barre_laterale()


# =============================================================================
#  FILTRES GLOBAUX — une seule barre, au-dessus de tout ce qu'elle porte
# =============================================================================
def barre_filtres() -> core.Filters:
    generation = st.session_state.setdefault("generation", 0)
    colonnes = st.columns([1.3, 1, 1, 1, 1, 0.8], gap="small")

    with colonnes[0]:
        choix = st.selectbox("Période", list(PERIODES), index=3,
                             key=f"periode_{generation}")
    mode = PERIODES[choix]
    if mode is None:
        debut, fin = DATE_MIN, DATE_MAX
    else:
        # Fenêtre alignée sur le 1er du mois : un seul mois partiel, celui en cours.
        ancre = pd.Timestamp(DATE_MAX).replace(day=1) - pd.DateOffset(months=mode - 1)
        debut, fin = max(DATE_MIN, ancre.date()), DATE_MAX

    dims: dict[str, list[str]] = {}
    principales = [c for c in core.DIMENSIONS_PRINCIPALES if c in df_complet.columns][:4]
    for colonne, champ in zip(colonnes[1:5], principales):
        options = _options(champ)
        if len(options) < 2:
            continue
        with colonne:
            dims[champ] = st.multiselect(core.DIMENSIONS[champ], options, default=[],
                                         placeholder="Tous", key=f"dim_{champ}_{generation}")

    with colonnes[5]:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        with st.popover("Plus de filtres", **KW_BOUTON):
            secondaires = [c for c in core.DIMENSIONS
                           if c not in principales and c in df_complet.columns]
            for champ in secondaires:
                options = _options(champ)
                if len(options) < 2:
                    continue
                dims[champ] = st.multiselect(core.DIMENSIONS[champ], options, default=[],
                                             placeholder="Tous",
                                             key=f"dim_{champ}_{generation}")
            st.button("Réinitialiser tous les filtres", on_click=_reinitialiser_filtres,
                      **KW_BOUTON)
    return core.Filters(date_min=debut, date_max=fin, dims=dims)


@st.cache_data(show_spinner=False)
def _options_cache(champ: str, empreinte: int) -> list[str]:
    serie = df_complet[champ].dropna()
    return sorted(v for v in serie.unique().tolist() if v != core.VALEUR_INCONNUE)


def _options(champ: str) -> list[str]:
    return _options_cache(champ, len(df_complet))


def chips_filtres(filtres: core.Filters) -> None:
    """Les filtres actifs, toujours visibles : on ne lit jamais un chiffre sans
    savoir sur quoi il porte."""
    morceaux = []
    if filtres.date_min and filtres.date_max:
        morceaux.append(f"<span class='chip'><b>Période</b>{core.fmt_date(filtres.date_min)}"
                        f" → {core.fmt_date(filtres.date_max)}</span>")
    actifs = 0
    for champ, valeurs in (filtres.dims or {}).items():
        for valeur in valeurs:
            actifs += 1
            morceaux.append(f"<span class='chip'><b>{core.DIMENSIONS.get(champ, champ)}</b>"
                            f"{valeur}</span>")
    if not actifs:
        morceaux.append("<span class='chip chip--vide'>Aucun filtre de dimension</span>")
    st.markdown(f"<div class='chips'>{''.join(morceaux)}</div>", unsafe_allow_html=True)
    return actifs


filtres = barre_filtres()
df = core.filter_data(df_complet, filtres)
df_precedent = core.filter_data(df_complet, filtres.periode_precedente())
def _granularite_par_defaut(filtres: core.Filters) -> str:
    """Un axe mensuel sur treize ans donne cent cinquante barres illisibles :
    la granularité suit la longueur de la fenêtre, jusqu'à ce que l'utilisateur
    en décide autrement."""
    duree = filtres.duree_jours or 0
    if duree > 6 * 365:
        return "annee"
    if duree > 3 * 365:
        return "trimestre"
    return "mois"


granularite = st.session_state.get("granularite") or _granularite_par_defaut(filtres)
analyse = core.build_analysis(df, filtres, rapport, df_precedent,
                              options={"granularite": granularite,
                                       "esg_mode": st.session_state.get("esg_mode", "part")})


# =============================================================================
#  EN-TÊTE DE PAGE
# =============================================================================
_, titre_page, groupe_page, sous_titre = next(p for p in PAGES if p[0] == PAGE)
st.markdown(
    f"""
    <div class="entete">
      <div>
        <div class="entete__fil">{groupe_page}</div>
        <div class="entete__titre">{titre_page}</div>
        <div class="entete__sous">{sous_titre}</div>
      </div>
      <div class="entete__meta">
        <b>{core.fmt_int(len(df))}</b> questionnaires dans la sélection<br>
        {analyse.periode}<br>
        Données arrêtées au {core.fmt_date(DATE_MAX)}
      </div>
    </div>
    """, unsafe_allow_html=True)
n_filtres = chips_filtres(filtres)

if analyse.vide:
    st.warning("Aucun questionnaire ne correspond à cette sélection. "
               "Élargissez la période ou retirez un filtre.")
    st.button("Réinitialiser les filtres", on_click=_reinitialiser_filtres, type="primary")
    st.stop()


# =============================================================================
#  AFFICHAGE DES BLOCS
# =============================================================================
def afficher_bloc(bloc: core.Block) -> None:
    with st.container(border=True):
        st.markdown(f"<div class='carte__titre'>{bloc.titre}</div>"
                    f"<div class='carte__accroche'>{bloc.accroche}</div>",
                    unsafe_allow_html=True)
        cliquable = bool(bloc.dimension) and SELECTION_DISPONIBLE
        if cliquable:
            # Sans clickmode, Plotly n'émet pas d'événement de sélection au clic.
            bloc.figure.update_layout(clickmode="event+select", dragmode=False)
            evenement = st.plotly_chart(
                bloc.figure, theme=None, config=core.PLOT_CONFIG, key=f"fig_{bloc.cle}",
                on_select="rerun", selection_mode="points", **KW_PLOT)
            _traiter_clic(bloc, evenement)
            st.markdown(f"<div class='carte__clic'>Cliquez une barre pour filtrer "
                        f"l'ensemble du tableau de bord sur cette "
                        f"{core.DIMENSIONS.get(bloc.dimension, bloc.dimension).lower()}.</div>",
                        unsafe_allow_html=True)
        else:
            st.plotly_chart(bloc.figure, theme=None, config=core.PLOT_CONFIG, **KW_PLOT)
        with st.expander(f"Voir les données ({len(bloc.tableau)} ligne(s))"):
            st.dataframe(bloc.tableau, hide_index=True, **KW_TABLE)
        if bloc.note:
            st.markdown(f"<div class='carte__note'>{bloc.note}</div>", unsafe_allow_html=True)


def _traiter_clic(bloc: core.Block, evenement) -> None:
    """Un clic sur une barre ajoute la modalité correspondante aux filtres."""
    points = (evenement or {}).get("selection", {}).get("points", [])
    if not points or not bloc.dimension:
        return
    etiquette = points[0].get("label") or points[0].get("y") or points[0].get("x")
    # « Autres (12) » regroupe une queue de classement : il n'existe pas comme
    # modalité, on ne peut pas filtrer dessus.
    if not isinstance(etiquette, str) or etiquette.startswith("Autres"):
        return
    if ajouter_filtre(bloc.dimension, etiquette):
        st.rerun()


def afficher_section(cle: str) -> None:
    """Deux colonnes par défaut, pleine largeur pour les blocs qui la méritent."""
    attente: list[core.Block] = []

    def vider() -> None:
        nonlocal attente
        if not attente:
            return
        colonnes = st.columns(2, gap="medium")
        for colonne, bloc in zip(colonnes, attente):
            with colonne:
                afficher_bloc(bloc)
        attente = []

    for bloc in analyse.section(cle):
        if bloc.large:
            vider()
            afficher_bloc(bloc)
        else:
            attente.append(bloc)
            if len(attente) == 2:
                vider()
    vider()


def selecteur_granularite() -> None:
    options = list(core.GRANULARITES)
    courant = granularite
    colonnes = st.columns([3, 1.4])
    with colonnes[1]:
        if hasattr(st, "segmented_control"):
            choix = st.segmented_control(
                "Granularité", options, format_func=lambda c: core.GRANULARITES[c],
                default=courant, key="granularite_widget", label_visibility="collapsed")
        else:                                   # versions antérieures de Streamlit
            choix = st.radio("Granularité", options,
                             format_func=lambda c: core.GRANULARITES[c],
                             index=options.index(courant), horizontal=True,
                             key="granularite_widget", label_visibility="collapsed")
    if choix and choix != courant:
        st.session_state["granularite"] = choix
        st.rerun()


# =============================================================================
#  PAGES
# =============================================================================
def page_synthese() -> None:
    bandeau_kpis(analyse, KPIS_PAR_PAGE["synthese"])
    st.markdown(f"<div class='note-lecture'>{core.NOTE_CENSURE}</div>",
                unsafe_allow_html=True)

    urgents = core.dossiers_a_surveiller(df)
    if len(urgents):
        gauche, droite = st.columns([3, 1], gap="medium", vertical_alignment="center") \
            if "vertical_alignment" in inspect.signature(st.columns).parameters \
            else st.columns([3, 1], gap="medium")
        with gauche:
            montant = float(urgents["montant_potentiel"].sum(skipna=True))
            st.markdown(
                f"<div class='alerte'><b>{core.fmt_int(len(urgents))} dossier(s) demandent "
                f"une relance</b> — délai cible dépassé ou décision attendue depuis plus de "
                f"quatre mois"
                + (f", {core.fmt_dec(montant, 0, 'M€')} d'encours concernés." if montant else ".")
                + "</div>", unsafe_allow_html=True)
        with droite:
            if st.button("Ouvrir dans l'explorateur", **KW_BOUTON):
                st.session_state["explorateur_vue"] = "attention"
                aller_a("explorateur")

    selecteur_granularite()
    afficher_section("synthese")

    if analyse.insights:
        st.markdown("<div class='nav-groupe' style='margin-top:20px'>Constats</div>",
                    unsafe_allow_html=True)
        cartes_insights(analyse.insights[:3])


def cartes_insights(insights: list[core.Insight]) -> None:
    """Chaque constat est lui-même le lien vers la page qui l'explique : pas de
    bouton suspendu sous la carte, et des hauteurs égales par construction."""
    cartes = []
    for insight in insights:
        corps = (f"<div class='insight__texte'>{insight.texte}</div>"
                 + (f"<div class='insight__appui'>{insight.appui}</div>"
                    if insight.appui else ""))
        if insight.cible and insight.cible in LIBELLES_PAGES:
            corps += (f"<div class='insight__lien'>"
                      f"{LIBELLES_PAGES[insight.cible]} →</div>")
            cartes.append(f"<a class='insight insight--{insight.ton}' "
                          f"href='?page={insight.cible}' target='_self'>{corps}</a>")
        else:
            cartes.append(f"<div class='insight insight--{insight.ton}'>{corps}</div>")
    st.markdown(f"<div class='insights'>{''.join(cartes)}</div>", unsafe_allow_html=True)


def page_avec_blocs(cle: str) -> None:
    kpis = KPIS_PAR_PAGE.get(cle, [])
    if kpis:
        bandeau_kpis(analyse, kpis)
    if cle == "activite":
        selecteur_granularite()
    if cle == "esg":
        colonnes = st.columns([3, 1.4])
        with colonnes[1]:
            mode = st.radio("Affichage", ["part", "volume"],
                            format_func=lambda m: "En part" if m == "part" else "En volume",
                            index=0 if st.session_state.get("esg_mode", "part") == "part" else 1,
                            horizontal=True, label_visibility="collapsed", key="esg_widget")
        if mode != st.session_state.get("esg_mode", "part"):
            st.session_state["esg_mode"] = mode
            st.rerun()
    blocs = analyse.section(cle)
    if not blocs:
        st.info("Aucune analyse disponible sur cette sélection : les colonnes nécessaires "
                "sont absentes du fichier, ou l'effectif est trop faible pour conclure.")
        return
    afficher_section(cle)


def page_insights() -> None:
    if not analyse.insights:
        st.info("Aucun constat ne se dégage de cette sélection.")
    else:
        st.markdown("<div class='note-lecture'>Chaque constat est calculé sur la sélection "
                    "courante. Aucune phrase n'est écrite d'avance : si la donnée ne permet "
                    "pas de l'établir, le constat n'apparaît pas.</div>",
                    unsafe_allow_html=True)
        cartes_insights(analyse.insights)
    diagnostic = analyse.section("diagnostic")
    if diagnostic:
        st.markdown("<div class='nav-groupe' style='margin-top:24px'>Analyse des causes"
                    "</div>", unsafe_allow_html=True)
        st.markdown("<div class='note-lecture'>Ces modèles cherchent ce qui explique les "
                    "délais et ce que la tendance laisse attendre. Ils répondent au "
                    "« pourquoi », pas au « combien ».</div>", unsafe_allow_html=True)
        afficher_section("diagnostic")


# --- Explorateur --------------------------------------------------------------
COLONNES_EXPLORATEUR = [
    ("date_reception", "Réception"), ("famille", "Famille"), ("type_demande", "Type"),
    ("client", "Client"), ("consultant", "Consultant"), ("pays", "Pays"),
    ("classe_actifs", "Classe d'actifs"), ("sous_classe_actifs", "Sous-classe"),
    ("expertise", "Expertise"), ("fonds", "Fonds de référence"),
    ("forme_juridique", "Forme juridique"), ("resultat", "Résultat"),
    ("statut", "Statut"), ("montant_potentiel", "Encours (M€)"),
    ("bande_esg", "ESG"), ("delai_calendaire", "Délai (j)"),
    ("nb_questions", "Questions"), ("analyste", "Analyste"),
    ("date_envoi", "Envoi"), ("langue", "Langue"),
]
# Colonnes affichées d'emblée. L'encours en est volontairement absent : il
# n'existe que pour un appel d'offres remporté, soit moins d'une ligne sur
# vingt — une colonne vide sur tout l'écran n'apprend rien. Elle reste à un
# clic dans le sélecteur de colonnes, et se remplit dès qu'on filtre sur les
# RFP gagnés.
COLONNES_DEFAUT = ["date_reception", "famille", "client", "pays", "classe_actifs",
                   "expertise", "resultat", "delai_calendaire"]


def page_explorateur() -> None:
    disponibles = [(c, l) for c, l in COLONNES_EXPLORATEUR if c in df.columns]
    haut = st.columns([3.4, 1.1, 1.1], gap="small")
    with haut[0]:
        recherche = st.text_input("Rechercher", placeholder="Client, fonds, consultant, pays…",
                                  label_visibility="collapsed", key="recherche")
    with haut[1]:
        with st.popover("Colonnes", **KW_BOUTON):
            colonnes_vues = st.multiselect(
                "Colonnes affichées", [c for c, _ in disponibles],
                default=[c for c in COLONNES_DEFAUT if c in dict(disponibles)],
                format_func=lambda c: dict(disponibles)[c], key="colonnes_vues")
    with haut[2]:
        vue = st.session_state.get("explorateur_vue", "tout")
        seulement_attention = st.toggle("À relancer", value=vue == "attention",
                                        key="filtre_attention")

    table = core.dossiers_a_surveiller(df) if seulement_attention else df
    if recherche:
        motif = core.cle_recherche(recherche)
        table = table[core.index_recherche(table).str.contains(motif, regex=False, na=False)]

    if table.empty:
        st.info("Aucun dossier ne correspond à cette recherche.")
        return

    colonnes_vues = colonnes_vues or COLONNES_DEFAUT
    affichage = table[[c for c in colonnes_vues if c in table.columns]].copy()
    # Les valeurs manquantes s'affichent « None » : c'est le rendu de la grille
    # Streamlit, que ni column_config ni un Styler ne modifient. On arrondit
    # pour éviter en plus les décimales parasites.
    for numerique in ("montant_potentiel", "delai_calendaire", "nb_questions"):
        if numerique in affichage.columns:
            affichage[numerique] = affichage[numerique].round(0)
    affichage = affichage.rename(columns=dict(disponibles))
    config = {}
    for interne, libelle in disponibles:
        if libelle not in affichage.columns:
            continue
        if interne in ("date_reception", "date_envoi"):
            config[libelle] = st.column_config.DateColumn(libelle, format="DD/MM/YYYY")
        elif interne in ("montant_potentiel", "delai_calendaire", "nb_questions"):
            config[libelle] = st.column_config.NumberColumn(libelle, format="%d")

    st.caption(f"{core.fmt_int(len(table))} dossier(s) · cliquez une ligne pour ouvrir "
               f"sa fiche")
    evenement = st.dataframe(
        affichage.sort_values(affichage.columns[0], ascending=False),
        hide_index=True, height=560, column_config=config,
        on_select="rerun", selection_mode="single-row", key="table_explorateur",
        **KW_TABLE)

    lignes = (evenement or {}).get("selection", {}).get("rows", [])
    if lignes:
        ordre = affichage.sort_values(affichage.columns[0], ascending=False).index
        fiche_dossier(table.loc[ordre[lignes[0]]])

    st.download_button(
        "Télécharger la sélection (CSV)",
        data=core.table_detaillee(table, formate=False).to_csv(index=False, sep=";")
             .encode("utf-8-sig"),
        file_name=f"rfp_intelligence_{dt.date.today():%Y%m%d}.csv", mime="text/csv",
        **_kw_largeur(st.download_button))


def fiche_dossier(ligne: pd.Series) -> None:
    """Fiche détaillée en panneau, sans quitter la liste ni perdre les filtres."""
    @st.dialog(f"{ligne.get('client', 'Dossier')} — {ligne.get('type_demande', '')}",
               width="large")
    def _fiche() -> None:
        couleurs = {core.RESULTAT_GAGNE: core.TEXTE_BON,
                    core.RESULTAT_PERDU: core.TEXTE_MAUVAIS}
        resultat = ligne.get("resultat", "—")
        st.markdown(
            f"<span class='puce' style='background:color-mix(in srgb,"
            f"{couleurs.get(resultat, core.INK_MUTED)} 15%, transparent);"
            f"color:{couleurs.get(resultat, core.INK_2)}'>{resultat}</span>"
            f"&nbsp;<span class='puce puce--neutre'>{ligne.get('famille', '')}</span>",
            unsafe_allow_html=True)
        gauche, droite = st.columns(2, gap="large")
        champs_gauche = [("Client", "client"), ("Consultant", "consultant"),
                         ("Pays", "pays"), ("Type de client", "type_client"),
                         ("Fonds de référence", "fonds"), ("Forme juridique", "forme_juridique")]
        champs_droite = [("Classe d'actifs", "classe_actifs"),
                         ("Sous-classe", "sous_classe_actifs"), ("Expertise", "expertise"),
                         ("Analyste", "analyste"), ("Langue", "langue"), ("ESG", "bande_esg")]
        for colonne, champs in ((gauche, champs_gauche), (droite, champs_droite)):
            with colonne:
                for libelle, champ in champs:
                    if champ in ligne.index and pd.notna(ligne[champ]):
                        st.markdown(f"<div class='kpi__label'>{libelle}</div>"
                                    f"<div style='font-size:13px;margin-bottom:9px'>"
                                    f"{ligne[champ]}</div>", unsafe_allow_html=True)
        st.divider()
        mesures = st.columns(4)
        mesures[0].metric("Reçu le", core.fmt_date(ligne.get("date_reception")))
        mesures[1].metric("Envoyé le", core.fmt_date(ligne.get("date_envoi")))
        delai = ligne.get("delai_calendaire")
        mesures[2].metric("Délai", core.fmt_dec(delai, 0, "j") if pd.notna(delai) else "—")
        montant = ligne.get("montant_potentiel")
        mesures[3].metric("Encours", core.fmt_dec(montant, 0, "M€") if pd.notna(montant) else "—")
        if pd.notna(ligne.get("nb_questions")):
            st.caption(f"{core.fmt_int(ligne['nb_questions'])} questions · "
                       f"délai cible {core.fmt_int(ligne.get('sla_cible', 0))} jours ouvrés")
    _fiche()


# --- Qualité & export ---------------------------------------------------------
def page_donnees() -> None:
    gauche, droite = st.columns([1, 1], gap="medium")
    with gauche:
        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Qualité des données</div>"
                        "<div class='carte__accroche'>Contrôles passés à l'import. "
                        "Aucune ligne n'est écartée sans être comptée.</div>",
                        unsafe_allow_html=True)
            st.markdown(
                f"<div class='side-info'>Source : <b>{rapport.source}</b><br>"
                f"Lignes lues : <b>{core.fmt_int(rapport.n_lignes_source)}</b> · "
                f"retenues : <b>{core.fmt_int(rapport.n_lignes_retenues)}</b><br>"
                f"Colonnes ignorées : {', '.join(rapport.colonnes_ignorees) or 'aucune'}</div>",
                unsafe_allow_html=True)
            if rapport.colonnes_absentes:
                st.info("Dimensions absentes du fichier, analyses correspondantes masquées : "
                        + ", ".join(core.DIMENSIONS.get(c, c) for c in rapport.colonnes_absentes))
            if rapport.est_propre:
                st.success("Aucune anomalie détectée.")
            else:
                for alerte in rapport.alertes:
                    st.warning(alerte)
            if analyse.erreurs:
                st.error("Blocs non construits : " + " · ".join(analyse.erreurs))

        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Définitions</div>"
                        "<div class='carte__accroche'>Les métriques sont calculées à un "
                        "seul endroit ; voici ce qu'elles recouvrent.</div>",
                        unsafe_allow_html=True)
            for kpi in analyse.kpis:
                with st.expander(kpi.libelle):
                    st.markdown(f"**{kpi.affichage}** — {kpi.aide}")

    with droite:
        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Rapport autonome</div>"
                        "<div class='carte__accroche'>Un fichier HTML unique, paginé, "
                        "graphiques interactifs inclus, qui s'ouvre sans Python ni "
                        "connexion — transmissible en pièce jointe.</div>",
                        unsafe_allow_html=True)
            theme_rapport = st.selectbox(
                "Thème du rapport", list(THEMES_LISIBLES),
                format_func=lambda c: THEMES_LISIBLES[c],
                index=list(THEMES_LISIBLES).index(core.THEME), key="theme_rapport")
            if st.button("Générer le rapport", type="primary", **KW_BOUTON):
                import export
                attente = st.empty()
                with attente.container():
                    animation("chargement", 54, boucle=True)
                theme_initial = core.THEME
                try:
                    core.appliquer_theme(theme_rapport)
                    analyse_export = core.build_analysis(
                        df, filtres, rapport, df_precedent,
                        options={"granularite": granularite})
                    chemin = export.ecrire_rapport(analyse_export, export.CHEMIN_RAPPORT)
                    st.session_state["rapport_html"] = Path(chemin).read_bytes()
                    st.session_state["rapport_chemin"] = str(chemin)
                finally:
                    core.appliquer_theme(theme_initial)
                attente.empty()
            if "rapport_html" in st.session_state:
                colonnes = st.columns([1, 4], gap="small")
                with colonnes[0]:
                    animation("valide", 44, boucle=False)
                with colonnes[1]:
                    poids = len(st.session_state["rapport_html"]) / 1_048_576
                    st.download_button(
                        f"Télécharger rapport.html ({poids:.1f} Mo)",
                        data=st.session_state["rapport_html"],
                        file_name=f"rfp_intelligence_{dt.date.today():%Y%m%d}.html",
                        mime="text/html", **_kw_largeur(st.download_button))
                    st.caption(f"Également écrit sur le disque : "
                               f"`{st.session_state['rapport_chemin']}`")


# =============================================================================
#  ROUTAGE
# =============================================================================
if PAGE == "synthese":
    page_synthese()
elif PAGE == "insights":
    page_insights()
elif PAGE == "explorateur":
    page_explorateur()
elif PAGE == "donnees":
    page_donnees()
else:
    page_avec_blocs(PAGE)

st.markdown(
    f"<div class='note-lecture' style='margin-top:26px'>RFP Intelligence · "
    f"{core.fmt_int(rapport.n_lignes_retenues)} questionnaires dans la base · "
    f"{core.fmt_int(len(df))} dans la sélection · "
    f"Données arrêtées au {core.fmt_date(DATE_MAX)}</div>", unsafe_allow_html=True)
