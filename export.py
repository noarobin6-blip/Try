# =============================================================================
#  export.py — Rapport HTML autonome
# -----------------------------------------------------------------------------
#  Produit un fichier unique qui embarque la bibliothèque Plotly : il s'ouvre
#  d'un double-clic, sans Python, sans serveur et sans connexion réseau —
#  donc transmissible par courriel à un comité d'investissement.
#
#  Usage :  python export.py            (rapport sur l'historique complet)
#           bouton « Générer le rapport HTML » dans app.py (périmètre filtré)
# =============================================================================
from __future__ import annotations

import html
from pathlib import Path

import pandas as pd
import plotly.io as pio

import core

CHEMIN_RAPPORT = Path("rapport.html")

# Blocs retenus pour la synthèse exécutive, dans l'ordre de lecture
CLES_SYNTHESE = ("flux", "entonnoir", "succes_classe", "delai_type",
                 "facteurs", "projection")


def bibliotheque_plotly() -> str:
    """Code source de plotly.js, embarqué dans le rapport.

    L'emplacement de la bibliothèque a changé au fil des versions de Plotly :
    on essaie les trois points d'accès connus plutôt que d'en supposer un.
    """
    try:                                  # Plotly <= 6
        return pio.get_plotlyjs()
    except AttributeError:
        pass
    try:                                  # Plotly >= 7
        from plotly.offline import get_plotlyjs
        return get_plotlyjs()
    except Exception:
        pass
    import plotly                         # dernier recours : le fichier livré
    fichier = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    if fichier.exists():
        return fichier.read_text(encoding="utf-8")
    raise RuntimeError(
        "Impossible de localiser plotly.min.js dans l'installation de Plotly ; "
        "le rapport autonome ne peut pas être généré. Réinstaller le paquet plotly."
    )


# =============================================================================
#  FEUILLE DE STYLE — document imprimable, lisible à l'écran comme sur papier
# =============================================================================
def _styles() -> str:
    return f"""
    :root {{
      --surface: {core.SURFACE}; --plane: {core.PLANE};
      --ink: {core.INK}; --ink-2: {core.INK_2}; --muted: {core.INK_MUTED};
      --grid: {core.GRID}; --border: rgba(11,11,11,.10); --accent: #0d366b;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--plane); color: var(--ink);
            font-family: {core.FONT_STACK}; font-size: 14px; line-height: 1.55;
            -webkit-font-smoothing: antialiased; }}
    .page {{ max-width: 1180px; margin: 0 auto; padding: 0 28px 72px; }}

    /* --- Couverture --- */
    header.couverture {{ display: flex; gap: 20px; align-items: flex-start;
                          padding: 44px 0 22px; border-bottom: 1px solid var(--grid); }}
    .barre {{ width: 5px; align-self: stretch; background: var(--accent); border-radius: 3px; }}
    .sur {{ font-size: 11px; letter-spacing: .11em; text-transform: uppercase;
            color: var(--muted); font-weight: 700; }}
    h1 {{ font-size: 30px; font-weight: 640; letter-spacing: -.02em; margin: 4px 0 6px;
          line-height: 1.12; }}
    .sous {{ font-size: 13.5px; color: var(--ink-2); max-width: 720px; }}
    .meta {{ margin-left: auto; text-align: right; font-size: 11.5px; color: var(--muted);
             line-height: 1.8; white-space: nowrap; }}
    .meta b {{ color: var(--ink-2); font-weight: 600; }}

    /* --- Sommaire --- */
    nav.sommaire {{ display: flex; flex-wrap: wrap; gap: 6px 18px; padding: 14px 0 0;
                    font-size: 12px; }}
    nav.sommaire a {{ color: var(--ink-2); text-decoration: none; padding: 3px 0;
                      border-bottom: 1px solid transparent; }}
    nav.sommaire a:hover {{ border-bottom-color: var(--accent); color: var(--ink); }}

    /* --- Indicateurs --- */
    .kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 26px 0 10px; }}
    .kpi {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
            padding: 14px 16px 12px; }}
    .kpi__label {{ font-size: 10.5px; letter-spacing: .07em; text-transform: uppercase;
                   color: var(--muted); font-weight: 700; margin-bottom: 6px; }}
    .kpi__valeur {{ font-size: 25px; font-weight: 620; letter-spacing: -.02em; line-height: 1.05; }}
    .kpi__bas {{ display: flex; align-items: center; gap: 8px; margin-top: 8px; flex-wrap: wrap; }}
    .kpi__detail {{ font-size: 11px; color: var(--muted); line-height: 1.35; }}
    .puce {{ display: inline-flex; gap: 4px; font-size: 11px; font-weight: 700;
             padding: 2px 7px; border-radius: 999px; white-space: nowrap; }}
    .puce--bon {{ background: rgba(12,163,12,.10); color: {core.SUCCESS_TEXT}; }}
    .puce--mauvais {{ background: rgba(208,59,59,.10); color: #a82f2f; }}
    .puce--neutre {{ background: rgba(11,11,11,.05); color: var(--ink-2); }}
    .note-lecture {{ font-size: 11.5px; color: var(--muted); border-left: 2px solid var(--grid);
                     padding-left: 11px; margin: 14px 0 0; }}

    /* --- Synthèse --- */
    .synthese {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
                 padding: 20px 24px; margin: 28px 0 8px; }}
    .synthese h2 {{ margin: 0 0 12px; }}
    .synthese ul {{ margin: 0; padding-left: 18px; }}
    .synthese li {{ margin-bottom: 8px; font-size: 13px; color: var(--ink-2); }}
    .synthese li b {{ color: var(--ink); font-weight: 600; }}

    /* --- Sections & cartes --- */
    h2.section {{ font-size: 12px; letter-spacing: .11em; text-transform: uppercase;
                  color: var(--muted); font-weight: 700; margin: 40px 0 14px;
                  padding-bottom: 8px; border-bottom: 1px solid var(--grid); }}
    h2 {{ font-size: 16px; font-weight: 620; letter-spacing: -.01em; }}
    .grille {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .carte {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
              padding: 18px 20px 14px; break-inside: avoid; }}
    .carte--large {{ grid-column: 1 / -1; }}
    .carte__titre {{ font-size: 15px; font-weight: 620; letter-spacing: -.01em; }}
    .carte__accroche {{ font-size: 12.5px; color: var(--ink-2); margin: 5px 0 12px; }}
    .carte__note {{ font-size: 11px; color: var(--muted); margin-top: 10px; padding-top: 9px;
                    border-top: 1px solid var(--grid); }}
    .graphique {{ width: 100%; }}

    /* --- Tableaux (le jumeau accessible de chaque graphique) --- */
    details {{ margin-top: 10px; }}
    summary {{ font-size: 11.5px; color: var(--muted); cursor: pointer; outline: none;
               padding: 3px 0; }}
    summary:hover {{ color: var(--ink-2); }}
    .tableau {{ overflow-x: auto; margin-top: 8px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 11.5px;
             font-variant-numeric: tabular-nums; }}
    th, td {{ text-align: right; padding: 6px 10px; border-bottom: 1px solid var(--grid);
              white-space: nowrap; }}
    th {{ color: var(--muted); font-weight: 600; text-align: right; font-size: 10.5px;
          letter-spacing: .04em; text-transform: uppercase; }}
    th:first-child, td:first-child {{ text-align: left; }}
    tbody tr:hover {{ background: rgba(42,120,214,.04); }}

    /* --- Annexe --- */
    .annexe {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
               padding: 20px 24px; margin-top: 16px; font-size: 12.5px; color: var(--ink-2); }}
    .annexe h3 {{ font-size: 12.5px; color: var(--ink); margin: 18px 0 6px; }}
    .annexe h3:first-of-type {{ margin-top: 0; }}
    .annexe dl {{ margin: 0; }} .annexe dt {{ font-weight: 600; color: var(--ink); margin-top: 8px; }}
    .annexe dd {{ margin: 2px 0 0; }}
    .alerte {{ color: #a82f2f; }}
    footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--grid);
              font-size: 11px; color: var(--muted); display: flex; justify-content: space-between;
              gap: 16px; flex-wrap: wrap; }}

    /* --- Écran étroit --- */
    @media (max-width: 900px) {{
      .page {{ padding: 0 16px 48px; }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
      .grille {{ grid-template-columns: 1fr; }}
      header.couverture {{ flex-wrap: wrap; }} .meta {{ margin-left: 0; text-align: left; }}
    }}

    /* --- Impression --- */
    @media print {{
      body {{ background: #fff; }}
      nav.sommaire, summary {{ display: none; }}
      details[open] > summary {{ display: none; }}
      .carte, .synthese, .annexe {{ break-inside: avoid; border-color: #ddd; }}
      h2.section {{ break-before: page; }}
      .page {{ max-width: none; padding: 0; }}
    }}
    """


# =============================================================================
#  FRAGMENTS
# =============================================================================
def _e(texte: object) -> str:
    return html.escape(str(texte), quote=True)


FLECHES = {"hausse": "▲", "baisse": "▼", "plat": ""}


def _kpi_html(kpi: core.Kpi) -> str:
    puce = ""
    if kpi.delta_affichage:
        fleche = FLECHES.get(kpi.delta_direction, "")
        puce = (f'<span class="puce puce--{_e(kpi.delta_sens)}">'
                f'{fleche} {_e(kpi.delta_affichage)}</span>')
    return (f'<div class="kpi" title="{_e(kpi.aide)}">'
            f'<div class="kpi__label">{_e(kpi.libelle)}</div>'
            f'<div class="kpi__valeur">{_e(kpi.affichage)}</div>'
            f'<div class="kpi__bas">{puce}'
            f'<span class="kpi__detail">{_e(kpi.detail)}</span></div></div>')


def _tableau_html(tableau: pd.DataFrame) -> str:
    if tableau is None or tableau.empty:
        return ""
    return tableau.to_html(index=False, escape=True, border=0, na_rep="—",
                           classes="donnees", justify="right")


def _figure_html(bloc: core.Block, indice: int) -> str:
    """Un div Plotly sans la bibliothèque : celle-ci est chargée une seule fois
    dans l'en-tête du document."""
    return pio.to_html(bloc.figure, include_plotlyjs=False, full_html=False,
                       config=core.PLOT_CONFIG, div_id=f"graphique-{indice}",
                       default_width="100%")


def _carte_html(bloc: core.Block, indice: int) -> str:
    classe = "carte carte--large" if bloc.large else "carte"
    note = (f'<div class="carte__note">{_e(bloc.note)}</div>' if bloc.note else "")
    tableau = _tableau_html(bloc.tableau)
    details = (f'<details><summary>Voir les données ({len(bloc.tableau)} ligne(s))</summary>'
               f'<div class="tableau">{tableau}</div></details>' if tableau else "")
    return (f'<section class="{classe}" id="bloc-{_e(bloc.cle)}">'
            f'<div class="carte__titre">{_e(bloc.titre)}</div>'
            f'<div class="carte__accroche">{_e(bloc.accroche)}</div>'
            f'<div class="graphique">{_figure_html(bloc, indice)}</div>'
            f'{details}{note}</section>')


def _synthese_html(analyse: core.Analysis) -> str:
    points = [b for cle in CLES_SYNTHESE for b in analyse.blocs if b.cle == cle]
    if not points:
        points = analyse.blocs[:5]
    items = "".join(f"<li><b>{_e(b.titre)}</b> — {_e(b.accroche)}</li>" for b in points)
    return (f'<div class="synthese"><h2>Ce qu\'il faut retenir</h2><ul>{items}</ul></div>')


def _annexe_html(analyse: core.Analysis) -> str:
    rapport = analyse.rapport
    stats = analyse.stats
    lignes: list[str] = ["<h3>Définitions</h3><dl>"]
    lignes.append("<dt>Délai de traitement</dt><dd>Nombre de jours <b>ouvrés</b> entre la date de "
                  "réception de la demande et la date d'envoi de la réponse. Les dossiers non "
                  "envoyés n'entrent dans aucune statistique de délai.</dd>")
    cibles = ", ".join(f"{k} : {v} jours" for k, v in core.SLA_JOURS_OUVRES.items())
    lignes.append(f"<dt>Délai cible</dt><dd>Engagement interne par type de demande "
                  f"({cibles}). Paramétrable dans <code>core.py</code>.</dd>")
    lignes.append("<dt>Taux de succès</dt><dd>Mandats gagnés rapportés aux dossiers tranchés "
                  "(gagnés + perdus). Les dossiers en attente de décision sont exclus du "
                  "dénominateur, jamais comptés comme des échecs.</dd>")
    lignes.append("<dt>Intervalle de confiance</dt><dd>Méthode de Wilson à 95 % pour les "
                  "proportions ; intervalle de Student à 95 % pour les coefficients de "
                  "régression. Deux intervalles qui se recouvrent ne permettent pas de "
                  "conclure à une différence.</dd>")
    lignes.append(f"<dt>Limite de lecture</dt><dd>{_e(core.NOTE_CENSURE)}</dd></dl>")

    lignes.append("<h3>Modèles statistiques</h3><dl>")
    tendance = stats.get("tendance_volume")
    if tendance is not None:
        lignes.append(
            f"<dt>Tendance du flux mensuel</dt><dd>Moindres carrés ordinaires du volume mensuel "
            f"sur le rang du mois (mois en cours exclu) : pente "
            f"{core.fmt_dec(tendance.pente, 2)} demande(s) par mois, "
            f"R² = {core.fmt_dec(tendance.r2, 2)}, {core.fmt_p(tendance.p_value)}, "
            f"n = {core.fmt_int(tendance.n)} mois.</dd>")
    reg_q = stats.get("regression_questions")
    if reg_q is not None:
        lignes.append(
            f"<dt>Délai et volume de questions</dt><dd>Pente {core.fmt_dec(reg_q.pente, 4)} jour "
            f"par question (IC 95 % : {core.fmt_dec(reg_q.ic_pente[0], 4)} à "
            f"{core.fmt_dec(reg_q.ic_pente[1], 4)}), R² = {core.fmt_dec(reg_q.r2, 2)}, "
            f"{core.fmt_p(reg_q.p_value)}, n = {core.fmt_int(reg_q.n)} dossiers.</dd>")
    modele = stats.get("modele_delai")
    if modele is not None:
        détail = " ; ".join(
            f"{_e(c.nom)} : {core.fmt_dec(c.valeur, 2)} j ({core.fmt_p(c.p_value)})"
            for c in modele.explicatives)
        lignes.append(
            f"<dt>Facteurs du délai (régression multiple)</dt><dd>R² ajusté = "
            f"{core.fmt_dec(modele.r2_ajuste, 2)}, n = {core.fmt_int(modele.n)}. {détail}.</dd>")
    lignes.append("<dt>Calcul des p-values</dt><dd>Loi de Student bilatérale évaluée par la "
                  "fonction bêta incomplète régularisée, sans dépendance externe ; valeurs "
                  "vérifiées contre les tables de référence à l'exécution de "
                  "<code>python core.py</code>.</dd></dl>")

    if rapport is not None:
        lignes.append("<h3>Qualité des données</h3>")
        lignes.append(
            f"<p>Source : <b>{_e(rapport.source)}</b>. "
            f"{core.fmt_int(rapport.n_lignes_source)} ligne(s) lue(s), "
            f"<b>{core.fmt_int(rapport.n_lignes_retenues)}</b> retenue(s) après normalisation.</p>")
        if rapport.alertes:
            puces = "".join(f"<li>{_e(a)}</li>" for a in rapport.alertes)
            lignes.append(f"<ul>{puces}</ul>")
        else:
            lignes.append("<p>Aucune anomalie détectée à l'import.</p>")
    if analyse.erreurs:
        puces = "".join(f"<li>{_e(e)}</li>" for e in analyse.erreurs)
        lignes.append(f'<h3 class="alerte">Blocs non construits</h3><ul>{puces}</ul>')
    return f'<div class="annexe">{"".join(lignes)}</div>'


# =============================================================================
#  ASSEMBLAGE
# =============================================================================
def construire_rapport(analyse: core.Analysis, titre: str = "Activité RFP / RFI") -> str:
    """Retourne le document HTML complet sous forme de chaîne."""
    if analyse.vide:
        raise ValueError("Aucune donnée à exporter : la sélection est vide.")

    plotlyjs = bibliotheque_plotly()
    kpis = "".join(_kpi_html(k) for k in analyse.kpis)

    corps: list[str] = []
    ancres: list[str] = []
    indice = 0
    for cle, libelle in analyse.sections:
        ancres.append(f'<a href="#section-{cle}">{_e(libelle)}</a>')
        corps.append(f'<h2 class="section" id="section-{cle}">{_e(libelle)}</h2><div class="grille">')
        for bloc in analyse.section(cle):
            corps.append(_carte_html(bloc, indice))
            indice += 1
        corps.append("</div>")
    ancres.append('<a href="#annexe">Méthodologie &amp; qualité des données</a>')

    comparaison = ""
    fenetre = analyse.stats.get("comparaison")     # absente si la période précédente est vide
    if fenetre:
        comparaison = (f" Les variations sont mesurées face à la période précédente de même durée "
                       f"({core.fmt_date(fenetre[0])} → {core.fmt_date(fenetre[1])}).")

    genere = analyse.genere_le.strftime("%d/%m/%Y à %H:%M")
    source = _e(analyse.rapport.source) if analyse.rapport else "—"

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(titre)} — rapport du {analyse.genere_le:%d/%m/%Y}</title>
<style>{_styles()}</style>
<script>{plotlyjs}</script>
</head>
<body>
<div class="page">
  <header class="couverture">
    <div class="barre"></div>
    <div>
      <div class="sur">Pôle réponse aux appels d'offres · Gestion d'actifs</div>
      <h1>{_e(titre)}</h1>
      <div class="sous">{_e(analyse.filtres.describe())}</div>
    </div>
    <div class="meta">
      <b>{core.fmt_int(len(analyse.df))}</b> demandes analysées<br>
      Période : {_e(analyse.periode)}<br>
      Édité le {genere}
    </div>
  </header>
  <nav class="sommaire">{"".join(ancres)}</nav>

  <div class="kpis">{kpis}</div>
  <p class="note-lecture">{_e(core.NOTE_CENSURE)}{_e(comparaison)}</p>

  {_synthese_html(analyse)}
  {"".join(corps)}

  <h2 class="section" id="annexe">Méthodologie &amp; qualité des données</h2>
  {_annexe_html(analyse)}

  <footer>
    <span>Rapport autonome — graphiques interactifs, aucune connexion requise.</span>
    <span>Source : {source}</span>
  </footer>
</div>
</body>
</html>"""


def ecrire_rapport(analyse: core.Analysis, chemin: str | Path = CHEMIN_RAPPORT,
                   titre: str = "Activité RFP / RFI") -> Path:
    """Écrit le rapport sur le disque et retourne son chemin."""
    chemin = Path(chemin)
    chemin.write_text(construire_rapport(analyse, titre), encoding="utf-8")
    return chemin


def main() -> None:
    """Génération en ligne de commande, sur l'historique complet."""
    print("Chargement des données…")
    df, rapport = core.load_data()
    filtres = core.Filters(date_min=df["date_reception"].min().date(),
                           date_max=df["date_reception"].max().date())
    print(f"Analyse de {core.fmt_int(len(df))} demandes…")
    analyse = core.build_analysis(df, filtres, rapport)
    if analyse.erreurs:
        print("Avertissements :", *analyse.erreurs, sep="\n  - ")
    chemin = ecrire_rapport(analyse)
    poids = chemin.stat().st_size / 1_048_576
    print(f"Rapport écrit : {chemin.resolve()}  ({poids:.1f} Mo, "
          f"{len(analyse.blocs)} graphiques, {len(analyse.kpis)} indicateurs)")
    print("Ouvrable d'un double-clic, sans Python ni connexion réseau.")


if __name__ == "__main__":
    main()
