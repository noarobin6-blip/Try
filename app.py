# =============================================================================
#  app.py — Interface Streamlit du dashboard d'activité RFP / RFI
# -----------------------------------------------------------------------------
#  Lancement :  streamlit run app.py     →  http://localhost:8501
#  Ce fichier ne contient AUCUN calcul métier : il filtre, il met en page, il
#  déclenche l'export. Tout le reste vit dans core.py.
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
    page_title="Activité RFP / RFI",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"about": "Dashboard d'activité RFP / RFI — pôle de réponse aux appels d'offres."},
)


# --- Compatibilité des versions de Streamlit ---------------------------------
# `use_container_width` est déprécié au profit de `width` dans les versions
# récentes : on choisit le bon mot-clé au lieu de parier sur la version.
def _kw_largeur(fonction) -> dict[str, object]:
    params = inspect.signature(fonction).parameters
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


KW_PLOT = _kw_largeur(st.plotly_chart)
KW_TABLE = _kw_largeur(st.dataframe)
KW_BOUTON = _kw_largeur(st.button)

PAGES = [
    ("apercu", "Vue d'ensemble"),
    ("commercial", "Performance commerciale"),
    ("operations", "Efficacité opérationnelle"),
    ("statistiques", "Analyse statistique"),
    ("donnees", "Données & qualité"),
]


# =============================================================================
#  HABILLAGE — mêmes jetons que core.py, donc que le rapport exporté
# =============================================================================
def feuille_de_style() -> str:
    return f"""
<style>
{core.police_css()}
:root {{
  --plane: {core.PLANE};  --surface: {core.SURFACE}; --elevation: {core.ELEVATION};
  --ink: {core.INK};      --ink-2: {core.INK_2};     --muted: {core.INK_MUTED};
  --grid: {core.GRID};    --border: {core.BORDER};   --serie1: {core.SERIES[0]};
  --bon: {core.TEXTE_BON}; --mauvais: {core.TEXTE_MAUVAIS};
}}
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {{
  background: var(--plane); color: var(--ink);
  font-family: {core.FONT_STACK};
}}
/* Halo d'ambiance, unique source lumineuse, très basse intensité */
[data-testid="stAppViewContainer"]::before {{
  content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background:
    radial-gradient(900px 520px at 80% -10%, color-mix(in srgb, var(--serie1) 12%, transparent), transparent 62%),
    radial-gradient(700px 420px at -8% 108%, color-mix(in srgb, var(--serie1) 7%, transparent), transparent 60%);
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding: 1.5rem 2.4rem 4rem; max-width: 1580px; position: relative; z-index: 1; }}

/* ---------------------------------------------------------------- entête -- */
.entete {{ display: flex; align-items: flex-start; gap: 20px; padding-bottom: 18px;
           margin-bottom: 22px; border-bottom: 1px solid var(--border); }}
.entete__sur {{ font-size: 10.5px; letter-spacing: .15em; text-transform: uppercase;
                color: var(--muted); font-weight: 650; }}
.entete__titre {{ font-size: 30px; font-weight: 600; letter-spacing: -.03em; margin: 5px 0 6px;
                  line-height: 1.08; }}
.entete__titre em {{ font-style: normal; color: var(--serie1); }}
.entete__sous {{ font-size: 12.5px; color: var(--ink-2); }}
.entete__meta {{ margin-left: auto; text-align: right; font-size: 11.5px; color: var(--muted);
                 line-height: 1.75; white-space: nowrap; }}
.entete__meta b {{ color: var(--ink-2); font-weight: 600; }}

/* ---------------------------------------------------------- indicateurs --- */
.kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 13px; }}
.kpis + .kpis {{ margin-top: 13px; }}
@media (max-width: 1280px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
.kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: 13px;
        padding: 15px 17px 13px; transition: border-color .2s ease; }}
.kpi:hover {{ border-color: color-mix(in srgb, var(--ink) 16%, transparent); }}
.kpi__label {{ font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
               color: var(--muted); font-weight: 650; }}
.kpi__valeur {{ font-size: 27px; font-weight: 600; letter-spacing: -.016em; margin-top: 8px;
                line-height: 1.05; font-variant-numeric: tabular-nums; }}
.kpi__bas {{ display: flex; align-items: center; gap: 9px; margin-top: 9px; flex-wrap: wrap; }}
.kpi__detail {{ font-size: 11px; color: var(--muted); line-height: 1.4; }}
.puce {{ display: inline-flex; gap: 5px; font-size: 11px; font-weight: 650; padding: 2px 8px;
         border-radius: 999px; white-space: nowrap; }}
.puce--bon {{ background: color-mix(in srgb, var(--bon) 16%, transparent); color: var(--bon); }}
.puce--mauvais {{ background: color-mix(in srgb, var(--mauvais) 16%, transparent); color: var(--mauvais); }}
.puce--neutre {{ background: color-mix(in srgb, var(--ink) 9%, transparent); color: var(--ink-2); }}
.avertissement {{ font-size: 11.5px; color: var(--muted); border-left: 2px solid var(--border);
                  padding-left: 12px; margin: 16px 0 6px; line-height: 1.55; }}

/* ---------------------------------------------- cartes (st.container) ----- */
div[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--surface); border: 1px solid var(--border) !important; border-radius: 14px;
  transition: border-color .2s ease; }}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  border-color: color-mix(in srgb, var(--ink) 16%, transparent) !important; }}
[data-testid="stColumn"] > div,
[data-testid="stColumn"] > div > [data-testid="stVerticalBlock"],
[data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] {{ height: 100%; }}
.carte__titre {{ font-size: 15.5px; font-weight: 620; letter-spacing: -.015em; color: var(--ink); }}
.carte__accroche {{ font-size: 12.5px; color: var(--ink-2); margin: 6px 0 2px; line-height: 1.55; }}
.carte__note {{ font-size: 11px; color: var(--muted); line-height: 1.5; margin-top: 8px;
                padding-top: 9px; border-top: 1px solid var(--border); }}
.section__tete {{ display: flex; align-items: flex-end; gap: 16px; margin: 4px 0 16px; }}
.section__num {{ font-size: 40px; font-weight: 600; letter-spacing: -.04em; line-height: .8;
                 color: color-mix(in srgb, var(--serie1) 60%, var(--muted));
                 font-variant-numeric: tabular-nums; }}
.section__titre {{ font-size: 21px; font-weight: 600; letter-spacing: -.025em; }}
.section__compte {{ margin-left: auto; font-size: 11.5px; color: var(--muted); }}

/* -------------------------------------------------------- barre latérale -- */
[data-testid="stSidebar"] {{ background: color-mix(in srgb, var(--surface) 82%, transparent);
  border-right: 1px solid var(--border); backdrop-filter: blur(14px); }}
[data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
.marque {{ display: flex; align-items: center; gap: 11px; margin-bottom: 4px; }}
.marque__texte {{ font-size: 12.5px; font-weight: 620; letter-spacing: -.01em; line-height: 1.25; }}
.marque__texte span {{ display: block; font-size: 9.5px; letter-spacing: .14em;
  text-transform: uppercase; color: var(--muted); font-weight: 600; margin-top: 3px; }}
.side-titre {{ font-size: 10px; letter-spacing: .13em; text-transform: uppercase; color: var(--muted);
               font-weight: 700; margin: 16px 0 2px; }}
.side-info {{ font-size: 11px; color: var(--muted); line-height: 1.65; }}
.side-info b {{ color: var(--ink-2); font-weight: 600; }}

/* La navigation est un st.radio déguisé : le rond disparaît, la ligne entière
   devient la cible. Les sélecteurs couvrent les deux structures DOM connues
   de Streamlit (récente : data-selected ; ancienne : input:checked). */
[data-testid="stSidebar"] [role="radiogroup"] {{ gap: 1px; }}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  padding: 7px 11px; border-radius: 8px; margin: 0; width: 100%;
  transition: background .18s ease, color .18s ease; cursor: pointer; }}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
  background: color-mix(in srgb, var(--ink) 7%, transparent); }}
[data-testid="stSidebar"] [role="radiogroup"] label > div > div > div:first-child,
[data-testid="stSidebar"] [role="radiogroup"] label > div[data-baseweb="radio"] > div:first-child {{
  display: none !important; }}
[data-testid="stSidebar"] [role="radiogroup"] label p {{
  font-size: 12.5px !important; color: var(--muted) !important; font-weight: 500;
  white-space: pre; }}
[data-testid="stSidebar"] [role="radiogroup"] label[data-selected="true"],
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
  background: color-mix(in srgb, var(--serie1) 16%, transparent); }}
[data-testid="stSidebar"] [role="radiogroup"] label[data-selected="true"] p,
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {{
  color: var(--ink) !important; font-weight: 600; }}

[data-testid="stSidebar"] label p {{ font-size: 12px !important; color: var(--ink-2) !important; }}

/* ------------------------------------------------------------- divers ----- */
[data-testid="stExpander"] details {{ border: none !important; background: transparent; }}
[data-testid="stExpander"] summary {{ font-size: 12px; color: var(--muted); }}
[data-testid="stExpander"] summary:hover {{ color: var(--ink-2); }}
.stDownloadButton button, .stButton button {{ border-radius: 9px; font-size: 12.5px;
  font-weight: 600; border: 1px solid var(--border); background: var(--elevation);
  color: var(--ink); transition: border-color .18s ease, transform .18s ease; }}
.stDownloadButton button:hover, .stButton button:hover {{ transform: translateY(-1px);
  border-color: color-mix(in srgb, var(--serie1) 60%, transparent); color: var(--ink); }}
.stButton button[kind="primary"] {{ background: var(--serie1); border-color: var(--serie1);
  color: #fff; }}
iframe[title="streamlit_components_v1_html"] {{ color-scheme: normal; }}
[data-testid="stAlert"], [data-testid="stAlertContainer"] {{
  background: color-mix(in srgb, var(--ink) 7%, transparent) !important;
  border: 1px solid var(--border); border-radius: 10px; color: var(--ink-2) !important; }}
[data-testid="stAlert"] p, [data-testid="stAlertContainer"] p {{
  font-size: 12px !important; color: var(--ink-2) !important; }}
[data-testid="stDataFrame"] {{ border: 1px solid var(--border); border-radius: 10px; }}
#MainMenu, footer, [data-testid="stAppDeployButton"] {{ display: none; }}
</style>
"""


st.markdown(feuille_de_style(), unsafe_allow_html=True)


# =============================================================================
#  ANIMATIONS — lecteur et données servis depuis assets/, jamais depuis un CDN
# =============================================================================
@st.cache_data(show_spinner=False)
def _html_animation(nom: str, taille: int, boucle: bool = True) -> str:
    """Page minimale hébergeant une animation Lottie, pour components.html.

    Renvoie une chaîne vide si les ressources manquent : l'interface perd son
    animation, jamais son contenu.
    """
    donnees, lecteur = core.animation(nom), core.lecteur_lottie()
    if not donnees or not lecteur:
        return ""
    return (
        f'<div id="a" style="width:{taille}px;height:{taille}px"></div>'
        f"<script>{lecteur}</script>"
        "<script>"
        "var sobre=window.matchMedia('(prefers-reduced-motion: reduce)').matches;"
        f"var anim=lottie.loadAnimation({{container:document.getElementById('a'),"
        f"renderer:'svg',loop:{str(boucle).lower()},autoplay:!sobre,"
        f"animationData:{json.dumps(donnees, separators=(',', ':'))}}});"
        "if(sobre){anim.goToAndStop(anim.totalFrames-1,true);}"
        "</script>"
    )


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
    st.markdown("<div class='entete'><div>"
                "<div class='entete__sur'>Configuration</div>"
                "<div class='entete__titre'>Données inaccessibles</div></div></div>",
                unsafe_allow_html=True)
    st.error(message)
    st.markdown(
        "**Pour brancher le tableau de bord**, ouvrir `core.py` et modifier le bloc "
        "`[BRANCHEMENT PRINCIPAL]` en tête de fichier :\n\n"
        "1. `DATA_PATH` — chemin du classeur Excel ;\n"
        "2. `SHEET_NAME` — nom de l'onglet ;\n"
        "3. `COLUMN_MAP` — nom réel de chaque colonne (la correspondance ignore la casse, "
        "les accents et les espaces) ;\n"
        "4. `USE_FAKE_DATA = False`.\n\n"
        "Repasser `USE_FAKE_DATA = True` restaure immédiatement la démonstration."
    )
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

PERIODES = {
    "6 derniers mois": 6,
    "12 derniers mois": 12,
    "24 derniers mois": 24,
    "Historique complet": None,
    "Personnalisée": "custom",
}


def _reinitialiser() -> None:
    """Remet les filtres à leur valeur par défaut.

    Les clés des widgets portent un numéro de génération : l'incrémenter crée
    des widgets neufs, donc vierges. Supprimer les clés ne suffirait pas —
    Streamlit restaure alors la valeur portée par le widget déjà affiché.
    """
    for cle in [k for k in st.session_state if k.startswith(("dim_", "periode", "bornes"))]:
        st.session_state.pop(cle, None)
    st.session_state["generation"] = st.session_state.get("generation", 0) + 1


# =============================================================================
#  BARRE LATÉRALE — marque, navigation, filtres
# =============================================================================
def barre_laterale() -> tuple[str, core.Filters]:
    generation = st.session_state.setdefault("generation", 0)
    with st.sidebar:
        haut = st.columns([1, 3], gap="small", vertical_alignment="center") \
            if "vertical_alignment" in inspect.signature(st.columns).parameters \
            else st.columns([1, 3], gap="small")
        with haut[0]:
            animation("marque", 44)
        with haut[1]:
            st.markdown("<div class='marque__texte'>Activité RFP / RFI"
                        "<span>Tableau de bord</span></div>", unsafe_allow_html=True)

        st.markdown("<div class='side-titre'>Pages</div>", unsafe_allow_html=True)
        libelles = [f"{i:02d}   {libelle}" for i, (_, libelle) in enumerate(PAGES, start=1)]
        choix_page = st.radio("Navigation", libelles, label_visibility="collapsed", key="page")
        cle_page = PAGES[libelles.index(choix_page)][0]

        st.markdown("<div class='side-titre'>Périmètre</div>", unsafe_allow_html=True)
        choix = st.selectbox("Période", list(PERIODES), index=1, key=f"periode_{generation}")
        mode = PERIODES[choix]
        if mode == "custom":
            bornes = st.date_input("Du — au", value=(DATE_MIN, DATE_MAX),
                                   min_value=DATE_MIN, max_value=DATE_MAX,
                                   format="DD/MM/YYYY", key=f"bornes_{generation}")
            if isinstance(bornes, (tuple, list)) and len(bornes) == 2:
                debut, fin = bornes
            else:                                   # saisie en cours : une seule borne
                debut, fin = (bornes if not isinstance(bornes, (tuple, list)) else bornes[0]), DATE_MAX
        elif mode is None:
            debut, fin = DATE_MIN, DATE_MAX
        else:
            # Alignement sur le 1er du mois : la fenêtre couvre `mode` mois
            # calendaires, dont un seul est partiel — celui en cours.
            fin = DATE_MAX
            ancre = pd.Timestamp(fin).replace(day=1) - pd.DateOffset(months=mode - 1)
            debut = max(DATE_MIN, ancre.date())

        st.markdown("<div class='side-titre'>Filtres</div>", unsafe_allow_html=True)
        dims: dict[str, list[str]] = {}
        for champ, libelle in core.DIMENSIONS.items():
            if champ not in df_complet.columns:
                continue
            options = sorted(v for v in df_complet[champ].dropna().unique().tolist())
            if len(options) < 2:
                continue
            dims[champ] = st.multiselect(libelle, options, default=[],
                                         placeholder="Tous", key=f"dim_{champ}_{generation}")

        st.button("Réinitialiser les filtres", on_click=_reinitialiser, **KW_BOUTON)
        st.divider()
        st.markdown(
            f"<div class='side-info'><b>Source</b><br>{rapport.source}<br><br>"
            f"<b>Profondeur</b><br>{core.fmt_date(DATE_MIN)} → {core.fmt_date(DATE_MAX)}<br><br>"
            f"<b>Lignes exploitables</b><br>{core.fmt_int(rapport.n_lignes_retenues)} sur "
            f"{core.fmt_int(rapport.n_lignes_source)}</div>",
            unsafe_allow_html=True)
        return cle_page, core.Filters(date_min=debut, date_max=fin, dims=dims)


page_active, filtres = barre_laterale()
df = core.filter_data(df_complet, filtres)
df_precedent = core.filter_data(df_complet, filtres.periode_precedente())
analyse = core.build_analysis(df, filtres, rapport, df_precedent)


# =============================================================================
#  EN-TÊTE
# =============================================================================
st.markdown(
    f"""
    <div class="entete">
      <div>
        <div class="entete__sur">Pôle réponse aux appels d'offres · Gestion d'actifs</div>
        <div class="entete__titre">Activité <em>RFP / RFI</em></div>
        <div class="entete__sous">{filtres.describe()}</div>
      </div>
      <div class="entete__meta">
        <b>{core.fmt_int(len(df))}</b> demandes analysées<br>
        Période : {analyse.periode}<br>
        Généré le {core.fmt_date(dt.date.today())}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if analyse.vide:
    st.warning("Aucune demande ne correspond à cette sélection. "
               "Élargissez la période ou retirez un filtre dans la barre latérale.")
    st.stop()


# =============================================================================
#  ÉLÉMENTS RÉUTILISABLES
# =============================================================================
FLECHES = {"hausse": "▲", "baisse": "▼", "plat": ""}


def carte_kpi(kpi: core.Kpi) -> str:
    puce = ""
    if kpi.delta_affichage:
        fleche = FLECHES.get(kpi.delta_direction, "")
        puce = (f"<span class='puce puce--{kpi.delta_sens}'>"
                f"{fleche} {kpi.delta_affichage}</span>")
    return (f"<div class='kpi' title=\"{kpi.aide}\">"
            f"<div class='kpi__label'>{kpi.libelle}</div>"
            f"<div class='kpi__valeur'>{kpi.affichage}</div>"
            f"<div class='kpi__bas'>{puce}<span class='kpi__detail'>{kpi.detail}</span></div>"
            f"</div>")


def bandeau_kpis() -> None:
    for depart in (0, 4):
        ligne = analyse.kpis[depart:depart + 4]
        if ligne:
            st.markdown(f"<div class='kpis'>{''.join(carte_kpi(k) for k in ligne)}</div>",
                        unsafe_allow_html=True)
    fenetre = analyse.stats.get("comparaison")      # absente si rien à comparer
    comparaison = (f" Variations mesurées face à la période précédente de même durée "
                   f"({core.fmt_date(fenetre[0])} → {core.fmt_date(fenetre[1])})." if fenetre else "")
    st.markdown(f"<div class='avertissement'>{core.NOTE_CENSURE}{comparaison}</div>",
                unsafe_allow_html=True)


def afficher_bloc(bloc: core.Block) -> None:
    with st.container(border=True):
        st.markdown(f"<div class='carte__titre'>{bloc.titre}</div>"
                    f"<div class='carte__accroche'>{bloc.accroche}</div>",
                    unsafe_allow_html=True)
        st.plotly_chart(bloc.figure, theme=None, config=core.PLOT_CONFIG, **KW_PLOT)
        with st.expander("Voir les données"):
            st.dataframe(bloc.tableau, hide_index=True, **KW_TABLE)
        if bloc.note:
            st.markdown(f"<div class='carte__note'>{bloc.note}</div>", unsafe_allow_html=True)


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


def tete_section(numero: int, libelle: str, mention: str) -> None:
    st.markdown(f"<div class='section__tete'><span class='section__num'>{numero:02d}</span>"
                f"<span class='section__titre'>{libelle}</span>"
                f"<span class='section__compte'>{mention}</span></div>",
                unsafe_allow_html=True)


# =============================================================================
#  PAGES
# =============================================================================
def page_donnees() -> None:
    tete_section(len(PAGES), "Données & qualité",
                 f"{core.fmt_int(len(df))} ligne(s) dans la sélection")
    gauche, droite = st.columns([3, 2], gap="medium")

    with gauche:
        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Détail des demandes</div>"
                        f"<div class='carte__accroche'>{core.fmt_int(len(df))} ligne(s) "
                        "dans la sélection courante.</div>", unsafe_allow_html=True)
            st.dataframe(core.table_detaillee(df), hide_index=True, height=520, **KW_TABLE)
            st.download_button(
                "Télécharger la sélection (CSV)",
                data=core.table_detaillee(df, formate=False).to_csv(index=False, sep=";")
                     .encode("utf-8-sig"),
                file_name=f"activite_rfp_{dt.date.today():%Y%m%d}.csv",
                mime="text/csv", **_kw_largeur(st.download_button))

    with droite:
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
            if rapport.est_propre:
                st.success("Aucune anomalie détectée.")
            else:
                for alerte in rapport.alertes:
                    st.warning(alerte)
            if analyse.erreurs:
                st.error("Blocs non construits : " + " · ".join(analyse.erreurs))

        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Rapport autonome</div>"
                        "<div class='carte__accroche'>Un fichier HTML unique, paginé, "
                        "graphiques interactifs inclus, qui s'ouvre sans Python ni "
                        "connexion.</div>", unsafe_allow_html=True)
            clair = st.toggle("Version claire, pour impression", value=False,
                              key="rapport_clair") if hasattr(st, "toggle") else False
            if st.button("Générer le rapport", type="primary", **KW_BOUTON):
                import export
                attente = st.empty()
                with attente.container():
                    animation("chargement", 56, boucle=True)
                theme_initial = core.THEME
                try:
                    core.appliquer_theme("clair" if clair else "sombre")
                    # Les figures portent les couleurs du thème : on les
                    # reconstruit pour l'export, sans toucher à l'écran.
                    analyse_export = core.build_analysis(df, filtres, rapport, df_precedent)
                    chemin = export.ecrire_rapport(analyse_export, export.CHEMIN_RAPPORT)
                    st.session_state["rapport_html"] = Path(chemin).read_bytes()
                    st.session_state["rapport_chemin"] = str(chemin)
                finally:
                    core.appliquer_theme(theme_initial)
                attente.empty()
            if "rapport_html" in st.session_state:
                colonnes = st.columns([1, 4], gap="small")
                with colonnes[0]:
                    animation("valide", 46, boucle=False)
                with colonnes[1]:
                    poids = len(st.session_state["rapport_html"]) / 1_048_576
                    st.download_button(
                        f"Télécharger rapport.html ({poids:.1f} Mo)",
                        data=st.session_state["rapport_html"],
                        file_name=f"rapport_activite_rfp_{dt.date.today():%Y%m%d}.html",
                        mime="text/html", **_kw_largeur(st.download_button))
                    st.caption(f"Également écrit sur le disque : "
                               f"`{st.session_state['rapport_chemin']}`")


numero_page = [cle for cle, _ in PAGES].index(page_active) + 1
if page_active == "donnees":
    page_donnees()
else:
    libelle = dict(PAGES)[page_active]
    blocs = analyse.section(page_active)
    tete_section(numero_page, libelle, f"{len(blocs)} analyse(s)")
    if page_active == "apercu":
        bandeau_kpis()
    if blocs:
        afficher_section(page_active)
    else:
        st.info("Cette section n'a pas d'analyse disponible sur la sélection courante : "
                "les colonnes nécessaires sont absentes, ou l'effectif est trop faible.")

st.markdown(
    f"<div class='avertissement' style='margin-top:28px'>Dashboard d'activité RFP / RFI · "
    f"{core.fmt_int(rapport.n_lignes_retenues)} demandes dans la base · "
    f"Données arrêtées au {core.fmt_date(DATE_MAX)}</div>",
    unsafe_allow_html=True)
