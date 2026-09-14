# =============================================================================
#  app.py — Interface Streamlit du dashboard d'activité RFP / RFI
# -----------------------------------------------------------------------------
#  Lancement :  streamlit run app.py
#  Ce fichier ne contient AUCUN calcul métier : il filtre, il met en page,
#  il déclenche l'export. Tout le reste vit dans core.py.
# =============================================================================
from __future__ import annotations

import datetime as dt
import inspect
from pathlib import Path

import pandas as pd
import streamlit as st

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
# récentes ; on choisit le bon mot-clé au lieu de parier sur la version.
def _kw_largeur(fonction) -> dict[str, object]:
    params = inspect.signature(fonction).parameters
    return {"width": "stretch"} if "width" in params else {"use_container_width": True}


KW_PLOT = _kw_largeur(st.plotly_chart)
KW_TABLE = _kw_largeur(st.dataframe)

# =============================================================================
#  HABILLAGE — palette et typographie reprises de core.py, source unique
# =============================================================================
CSS = f"""
<style>
  :root {{
    --surface: {core.SURFACE};
    --plane: {core.PLANE};
    --ink: {core.INK};
    --ink-2: {core.INK_2};
    --muted: {core.INK_MUTED};
    --grid: {core.GRID};
    --border: {core.BORDER};
    --accent: #0d366b;
  }}
  html, body, [data-testid="stAppViewContainer"] {{
    background: var(--plane);
    color: var(--ink);
    font-family: {core.FONT_STACK};
  }}
  [data-testid="stHeader"] {{ background: transparent; }}
  [data-testid="stToolbar"] {{ right: 1rem; }}
  .block-container {{ padding: 1.4rem 2.2rem 4rem; max-width: 1560px; }}

  /* ---- En-tête ---- */
  .entete {{ display: flex; align-items: flex-start; gap: 18px;
             border-bottom: 1px solid var(--grid); padding-bottom: 18px; margin-bottom: 22px; }}
  .entete__barre {{ width: 4px; align-self: stretch; background: var(--accent); border-radius: 2px; }}
  .entete__sur {{ font-size: 11px; letter-spacing: .10em; text-transform: uppercase;
                  color: var(--muted); font-weight: 600; }}
  .entete__titre {{ font-size: 27px; font-weight: 640; letter-spacing: -.015em;
                    color: var(--ink); margin: 2px 0 4px; line-height: 1.15; }}
  .entete__sous {{ font-size: 13px; color: var(--ink-2); }}
  .entete__meta {{ margin-left: auto; text-align: right; font-size: 11.5px; color: var(--muted);
                   line-height: 1.7; padding-top: 4px; }}
  .entete__meta b {{ color: var(--ink-2); font-weight: 600; }}

  /* ---- Cartes d'indicateurs ---- */
  .kpis {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px;
           margin-bottom: 4px; }}
  .kpis + .kpis {{ margin-top: 12px; }}
  @media (max-width: 1250px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
  .kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
          padding: 15px 17px 13px; height: 100%; box-shadow: 0 1px 2px rgba(11,11,11,.035); }}
  .kpi__label {{ font-size: 11px; letter-spacing: .07em; text-transform: uppercase;
                 color: var(--muted); font-weight: 600; margin-bottom: 7px; }}
  .kpi__valeur {{ font-size: 27px; font-weight: 620; color: var(--ink); line-height: 1.05;
                  letter-spacing: -.02em; }}
  .kpi__bas {{ display: flex; align-items: center; gap: 8px; margin-top: 9px; flex-wrap: wrap; }}
  .kpi__detail {{ font-size: 11.5px; color: var(--muted); line-height: 1.35; }}
  .puce {{ display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600;
           padding: 2px 7px; border-radius: 999px; white-space: nowrap; }}
  .puce--bon {{ background: rgba(12,163,12,.10); color: {core.SUCCESS_TEXT}; }}
  .puce--mauvais {{ background: rgba(208,59,59,.10); color: #a82f2f; }}
  .puce--neutre {{ background: rgba(11,11,11,.05); color: var(--ink-2); }}
  .avertissement {{ font-size: 11.5px; color: var(--muted); margin: 12px 2px 4px;
                    padding-left: 10px; border-left: 2px solid var(--grid); line-height: 1.5; }}

  /* ---- Cartes de graphiques (st.container(border=True)) ---- */
  [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) {{
      background: var(--surface); border-radius: 12px; }}
  div[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--border) !important; }}
  .carte__titre {{ font-size: 15.5px; font-weight: 620; color: var(--ink); letter-spacing: -.01em; }}
  .carte__accroche {{ font-size: 12.5px; color: var(--ink-2); margin: 5px 0 2px; line-height: 1.5; }}
  .carte__note {{ font-size: 11px; color: var(--muted); line-height: 1.5; margin-top: 6px;
                  padding-top: 8px; border-top: 1px solid var(--grid); }}

  /* ---- Onglets ---- */
  [data-testid="stTabs"] [role="tablist"] {{ gap: 6px; border-bottom: 1px solid var(--grid); }}
  [data-testid="stTabs"] [role="tab"] {{ font-size: 13.5px; font-weight: 550; color: var(--muted);
                                          padding: 8px 4px; }}
  [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ color: var(--ink); }}

  /* ---- Barre latérale ---- */
  [data-testid="stSidebar"] {{ background: #f2f1ec; border-right: 1px solid var(--grid); }}
  [data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
  .side-titre {{ font-size: 11px; letter-spacing: .10em; text-transform: uppercase;
                 color: var(--muted); font-weight: 700; margin: 6px 0 2px; }}
  [data-testid="stSidebar"] label {{ font-size: 12px !important; color: var(--ink-2) !important; }}
  .side-info {{ font-size: 11px; color: var(--muted); line-height: 1.6; }}

  /* ---- Divers ---- */
  [data-testid="stExpander"] details {{ border: none; background: transparent; }}
  [data-testid="stExpander"] summary {{ font-size: 12px; color: var(--muted); }}
  .stDownloadButton button, .stButton button {{ border-radius: 8px; font-size: 12.5px;
                                                font-weight: 600; border-color: var(--border); }}
  /* Deux cartes côte à côte : même hauteur */
  [data-testid="stColumn"] > div,
  [data-testid="stColumn"] > div > [data-testid="stVerticalBlock"],
  [data-testid="stColumn"] div[data-testid="stVerticalBlockBorderWrapper"] {{ height: 100%; }}
  #MainMenu, footer, [data-testid="stAppDeployButton"] {{ display: none; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# =============================================================================
#  DONNÉES
# =============================================================================
@st.cache_data(show_spinner="Chargement des données…")
def charger() -> tuple[pd.DataFrame, core.LoadReport]:
    return core.load_data()


def ecran_erreur(message: str) -> None:
    st.markdown("<div class='entete'><div class='entete__barre'></div><div>"
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


# =============================================================================
#  BARRE LATÉRALE — filtres
# =============================================================================
def _reinitialiser() -> None:
    """Remet les filtres à leur valeur par défaut.

    Les clés des widgets portent un numéro de génération : l'incrémenter crée
    des widgets neufs, donc vierges. Supprimer les clés ne suffirait pas —
    Streamlit restaure alors la valeur portée par le widget déjà affiché.
    """
    for cle in [k for k in st.session_state if k.startswith(("dim_", "periode", "bornes"))]:
        st.session_state.pop(cle, None)
    st.session_state["generation"] = st.session_state.get("generation", 0) + 1


def barre_laterale() -> core.Filters:
    generation = st.session_state.setdefault("generation", 0)
    with st.sidebar:
        st.markdown("<div class='side-titre'>Périmètre d'analyse</div>", unsafe_allow_html=True)
        choix = st.selectbox("Période", list(PERIODES), index=1, key=f"periode_{generation}")
        st.caption("Périodes alignées sur les mois calendaires.")
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

        st.markdown("<div class='side-titre' style='margin-top:14px'>Filtres</div>",
                    unsafe_allow_html=True)
        dims: dict[str, list[str]] = {}
        for champ, libelle in core.DIMENSIONS.items():
            if champ not in df_complet.columns:
                continue
            options = sorted(v for v in df_complet[champ].dropna().unique().tolist())
            if len(options) < 2:
                continue
            dims[champ] = st.multiselect(libelle, options, default=[],
                                         placeholder="Tous", key=f"dim_{champ}_{generation}")

        st.button("Réinitialiser les filtres", on_click=_reinitialiser,
                  **_kw_largeur(st.button))

        st.divider()
        st.markdown(
            f"<div class='side-info'><b>Source</b><br>{rapport.source}<br><br>"
            f"<b>Profondeur</b><br>{core.fmt_date(DATE_MIN)} → {core.fmt_date(DATE_MAX)}<br><br>"
            f"<b>Lignes exploitables</b><br>{core.fmt_int(rapport.n_lignes_retenues)} sur "
            f"{core.fmt_int(rapport.n_lignes_source)}</div>",
            unsafe_allow_html=True)
        return core.Filters(date_min=debut, date_max=fin, dims=dims)


filtres = barre_laterale()
df = core.filter_data(df_complet, filtres)
df_precedent = core.filter_data(df_complet, filtres.periode_precedente())
analyse = core.build_analysis(df, filtres, rapport, df_precedent)


# =============================================================================
#  EN-TÊTE
# =============================================================================
st.markdown(
    f"""
    <div class="entete">
      <div class="entete__barre"></div>
      <div>
        <div class="entete__sur">Pôle réponse aux appels d'offres · Gestion d'actifs</div>
        <div class="entete__titre">Activité RFP / RFI</div>
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
#  INDICATEURS
# =============================================================================
FLECHES = {"hausse": "▲", "baisse": "▼", "plat": "—"}


def carte_kpi(kpi: core.Kpi) -> str:
    puce = ""
    if kpi.delta_affichage:
        fleche = FLECHES.get(kpi.delta_direction, "")
        puce = (f"<span class='puce puce--{kpi.delta_sens}'>"
                f"{fleche + ' ' if fleche and kpi.delta_direction != 'plat' else ''}"
                f"{kpi.delta_affichage}</span>")
    return (f"<div class='kpi' title=\"{kpi.aide}\">"
            f"<div class='kpi__label'>{kpi.libelle}</div>"
            f"<div class='kpi__valeur'>{kpi.affichage}</div>"
            f"<div class='kpi__bas'>{puce}<span class='kpi__detail'>{kpi.detail}</span></div>"
            f"</div>")


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


# =============================================================================
#  BLOCS D'ANALYSE
# =============================================================================
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


onglets = st.tabs([libelle for _, libelle in analyse.sections] + ["Données & qualité"])
for onglet, (cle, _) in zip(onglets, analyse.sections):
    with onglet:
        afficher_section(cle)


# =============================================================================
#  ONGLET DONNÉES & QUALITÉ
# =============================================================================
with onglets[-1]:
    gauche, droite = st.columns([3, 2], gap="medium")

    with gauche:
        with st.container(border=True):
            st.markdown("<div class='carte__titre'>Détail des demandes</div>"
                        f"<div class='carte__accroche'>{core.fmt_int(len(df))} ligne(s) "
                        "dans la sélection courante.</div>", unsafe_allow_html=True)
            table = core.table_detaillee(df)
            st.dataframe(table, hide_index=True, height=460, **KW_TABLE)
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
                        "<div class='carte__accroche'>Un fichier HTML unique, graphiques "
                        "interactifs inclus, qui s'ouvre sans Python ni connexion.</div>",
                        unsafe_allow_html=True)
            if st.button("Générer le rapport HTML", type="primary",
                         **_kw_largeur(st.button)):
                import export
                with st.spinner("Construction du rapport…"):
                    chemin = export.ecrire_rapport(analyse, export.CHEMIN_RAPPORT)
                st.session_state["rapport_html"] = Path(chemin).read_bytes()
                st.session_state["rapport_chemin"] = str(chemin)
            if "rapport_html" in st.session_state:
                poids = len(st.session_state["rapport_html"]) / 1_048_576
                st.download_button(
                    f"Télécharger rapport.html ({poids:.1f} Mo)",
                    data=st.session_state["rapport_html"],
                    file_name=f"rapport_activite_rfp_{dt.date.today():%Y%m%d}.html",
                    mime="text/html", **_kw_largeur(st.download_button))
                st.caption(f"Également écrit sur le disque : "
                           f"`{st.session_state['rapport_chemin']}`")

st.markdown(
    f"<div class='avertissement' style='margin-top:26px'>Dashboard d'activité RFP / RFI · "
    f"{core.fmt_int(rapport.n_lignes_retenues)} demandes dans la base · "
    f"Données arrêtées au {core.fmt_date(DATE_MAX)}</div>",
    unsafe_allow_html=True)
