# =============================================================================
#  export.py — Rapport HTML autonome, paginé et animé
# -----------------------------------------------------------------------------
#  Produit un fichier unique qui embarque tout ce dont il a besoin : la
#  bibliothèque Plotly, le lecteur Lottie, les animations et la police. Il
#  s'ouvre d'un double-clic, sans Python, sans serveur et sans réseau — donc
#  transmissible par courriel à un comité d'investissement.
#
#  Usage :  python export.py              rapport sombre (écran)
#           python export.py --clair      variante claire (impression)
#           python export.py --sortie X   chemin de sortie
#           bouton « Générer le rapport » dans app.py (périmètre filtré)
# =============================================================================
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import pandas as pd
import plotly.io as pio

import core

CHEMIN_RAPPORT = Path("rapport.html")

# Blocs retenus pour la synthèse de couverture, dans l'ordre de lecture
CLES_SYNTHESE = ("flux", "entonnoir", "succes_classe", "delai_type",
                 "facteurs", "projection")
# Indicateurs mis en avant sur la couverture
CLES_HEROS = ("volume", "succes", "delai", "gagne")


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
#  FEUILLE DE STYLE
#  Les couleurs passent par des variables CSS alimentées par le thème actif de
#  core.py : une seule source, l'écran et le rapport ne peuvent pas diverger.
# =============================================================================
def _variables_css() -> str:
    return (
        ":root{"
        f"--plane:{core.PLANE};--surface:{core.SURFACE};--elevation:{core.ELEVATION};"
        f"--ink:{core.INK};--ink-2:{core.INK_2};--muted:{core.INK_MUTED};"
        f"--grid:{core.GRID};--axis:{core.AXIS};--border:{core.BORDER};"
        f"--accent:{core.ACCENT};--bon:{core.TEXTE_BON};--mauvais:{core.TEXTE_MAUVAIS};"
        f"--serie1:{core.SERIES[0]};"
        f"--font:{core.FONT_STACK};"
        "}"
    )


CSS = r"""
*,*::before,*::after{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--plane);color:var(--ink);font-family:var(--font);
     font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased;
     font-feature-settings:"cv05","ss01";overflow:hidden}

/* Halo d'ambiance : une seule source lumineuse, très basse intensité. */
.ambiance{position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(900px 520px at 78% -8%,color-mix(in srgb,var(--serie1) 13%,transparent),transparent 62%),
             radial-gradient(700px 420px at -6% 104%,color-mix(in srgb,var(--serie1) 8%,transparent),transparent 60%)}

/* ---------------------------------------------------------------- rail --- */
.rail{position:fixed;left:0;top:0;bottom:0;width:224px;z-index:3;
  display:flex;flex-direction:column;gap:22px;padding:26px 20px 22px;
  border-right:1px solid var(--border);background:color-mix(in srgb,var(--surface) 72%,transparent);
  backdrop-filter:blur(14px)}
.rail__tete{display:flex;align-items:center;gap:11px}
.rail__marque{width:38px;height:38px;flex:none}
.rail__titre{font-size:12.5px;font-weight:620;letter-spacing:-.01em;line-height:1.25}
.rail__titre span{display:block;font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--muted);font-weight:600;margin-top:3px}
.rail nav{display:flex;flex-direction:column;gap:1px;margin-top:6px}
.lien{display:flex;align-items:baseline;gap:10px;padding:8px 10px;border-radius:8px;
  color:var(--muted);text-decoration:none;font-size:12.5px;cursor:pointer;
  border:0;background:none;text-align:left;width:100%;font-family:inherit;
  transition:color .18s ease,background .18s ease}
.lien .num{font-size:10px;font-weight:700;letter-spacing:.08em;opacity:.75;
  font-variant-numeric:tabular-nums}
.lien:hover{color:var(--ink);background:color-mix(in srgb,var(--ink) 6%,transparent)}
.lien[aria-current="page"]{color:var(--ink);background:color-mix(in srgb,var(--serie1) 15%,transparent)}
.lien[aria-current="page"] .num{color:var(--serie1);opacity:1}
.rail__pied{margin-top:auto;font-size:10.5px;color:var(--muted);line-height:1.6;
  border-top:1px solid var(--border);padding-top:14px}

/* --------------------------------------------------------------- pages --- */
main{position:relative;z-index:1;margin-left:224px;height:100vh;overflow-y:auto;
  overflow-x:hidden;scroll-behavior:smooth}
.page{display:none;padding:46px 54px 72px;max-width:1420px;margin:0 auto}
.page.actif{display:block}
.page.actif>*{animation:monte .42s cubic-bezier(.22,.61,.36,1) both}
.page.actif>*:nth-child(2){animation-delay:.05s}
.page.actif>*:nth-child(3){animation-delay:.09s}
@keyframes monte{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}

/* ---------------------------------------------------------- couverture --- */
.page.couverture.actif{display:flex;flex-direction:column;justify-content:center}
.couverture{min-height:calc(100vh - 92px);padding:56px 54px 40px;position:relative}
.sur{font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--muted);
  font-weight:650}
.couverture h1{font-size:clamp(44px,5.4vw,78px);font-weight:600;letter-spacing:-.035em;
  line-height:1.02;margin:16px 0 0;max-width:15ch}
.couverture h1 em{font-style:normal;color:var(--serie1)}
.couverture .accroche{margin-top:22px;font-size:16.5px;color:var(--ink-2);max-width:62ch;
  line-height:1.6;font-variant-numeric:tabular-nums}
.couverture .portee{margin-top:10px;font-size:12.5px;color:var(--muted);max-width:70ch;
  padding-left:12px;border-left:2px solid var(--border)}
.heros{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;margin-top:46px;
  background:var(--border);border:1px solid var(--border);border-radius:14px;overflow:hidden}
.heros .h{background:var(--surface);padding:20px 22px 18px}
.heros .h__label{font-size:10px;letter-spacing:.11em;text-transform:uppercase;
  color:var(--muted);font-weight:650}
.heros .h__valeur{font-size:38px;font-weight:600;letter-spacing:-.018em;margin-top:9px;
  line-height:1;font-variant-numeric:tabular-nums}
.heros .h__detail{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}
.flux{position:absolute;left:0;right:0;bottom:-10px;height:230px;opacity:.5;
  pointer-events:none;z-index:-1}
.entrer{margin-top:40px;display:inline-flex;align-items:center;gap:10px;align-self:flex-start;
  background:var(--serie1);color:#fff;border:0;border-radius:999px;padding:12px 22px;
  font-family:inherit;font-size:13px;font-weight:600;cursor:pointer;
  transition:transform .18s ease,box-shadow .18s ease}
.entrer:hover{transform:translateY(-1px);box-shadow:0 8px 26px color-mix(in srgb,var(--serie1) 38%,transparent)}

/* ------------------------------------------------------------- section --- */
.tete{display:flex;align-items:flex-end;gap:18px;padding-bottom:16px;margin-bottom:24px;
  border-bottom:1px solid var(--border)}
.tete .num{font-size:52px;font-weight:600;letter-spacing:-.04em;line-height:.85;
  color:color-mix(in srgb,var(--serie1) 55%,var(--muted));font-variant-numeric:tabular-nums}
.tete h2{font-size:26px;font-weight:600;letter-spacing:-.025em;margin:0}
.tete .compte{margin-left:auto;font-size:11.5px;color:var(--muted);white-space:nowrap}

.grille{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:18px}
.carte{grid-column:span 6;background:var(--surface);border:1px solid var(--border);
  border-radius:14px;padding:20px 22px 16px;opacity:0;transform:translateY(16px);
  transition:opacity .5s ease,transform .5s cubic-bezier(.22,.61,.36,1),border-color .2s ease}
.carte.vue{opacity:1;transform:none}
.carte:hover{border-color:color-mix(in srgb,var(--ink) 18%,transparent)}
.carte--large{grid-column:span 12}
.carte__titre{font-size:15.5px;font-weight:620;letter-spacing:-.015em}
.carte__accroche{font-size:12.5px;color:var(--ink-2);margin:6px 0 14px;line-height:1.55}
.carte__note{font-size:11px;color:var(--muted);margin-top:12px;padding-top:10px;
  border-top:1px solid var(--border);line-height:1.5}

/* ------------------------------------------------------------ tableaux --- */
details{margin-top:10px}
summary{font-size:11.5px;color:var(--muted);cursor:pointer;list-style:none;padding:4px 0;
  display:inline-flex;align-items:center;gap:7px;transition:color .18s ease}
summary::-webkit-details-marker{display:none}
summary::before{content:"";width:5px;height:5px;border-right:1.5px solid currentColor;
  border-bottom:1.5px solid currentColor;transform:rotate(-45deg);transition:transform .2s ease}
details[open] summary::before{transform:rotate(45deg)}
summary:hover{color:var(--ink-2)}
.tableau{overflow-x:auto;margin-top:10px;border:1px solid var(--border);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:11.5px;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:7px 12px;border-bottom:1px solid var(--border);white-space:nowrap}
th{color:var(--muted);font-weight:650;font-size:10px;letter-spacing:.06em;text-transform:uppercase;
  position:sticky;top:0;background:var(--elevation)}
tbody tr:last-child td{border-bottom:0}
th:first-child,td:first-child{text-align:left}
tbody tr:hover td{background:color-mix(in srgb,var(--serie1) 7%,transparent)}

/* ----------------------------------------------------------- indicateurs -- */
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:22px}
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:13px;
  padding:16px 18px 14px}
.kpi__label{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  font-weight:650}
.kpi__valeur{font-size:27px;font-weight:600;letter-spacing:-.016em;margin-top:8px;
  line-height:1.05;font-variant-numeric:tabular-nums}
.kpi__bas{display:flex;align-items:center;gap:9px;margin-top:9px;flex-wrap:wrap}
.kpi__detail{font-size:11px;color:var(--muted);line-height:1.4}
.puce{display:inline-flex;gap:5px;font-size:11px;font-weight:650;padding:2px 8px;
  border-radius:999px;white-space:nowrap}
.puce--bon{background:color-mix(in srgb,var(--bon) 16%,transparent);color:var(--bon)}
.puce--mauvais{background:color-mix(in srgb,var(--mauvais) 16%,transparent);color:var(--mauvais)}
.puce--neutre{background:color-mix(in srgb,var(--ink) 8%,transparent);color:var(--ink-2)}
.avertissement{font-size:11.5px;color:var(--muted);border-left:2px solid var(--border);
  padding-left:12px;margin:0 0 26px;line-height:1.55;max-width:104ch}

/* ------------------------------------------------------------- synthèse -- */
.synthese{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:22px 26px;margin-bottom:22px}
.synthese h3{margin:0 0 14px;font-size:15px;font-weight:620;letter-spacing:-.015em}
.synthese ul{margin:0;padding:0;list-style:none;display:grid;gap:11px}
.synthese li{font-size:12.5px;color:var(--ink-2);line-height:1.55;padding-left:16px;
  position:relative}
.synthese li::before{content:"";position:absolute;left:0;top:8px;width:5px;height:5px;
  border-radius:50%;background:var(--serie1)}
.synthese li b{color:var(--ink);font-weight:620}

/* ------------------------------------------------------------- annexe ---- */
.annexe{background:var(--surface);border:1px solid var(--border);border-radius:14px;
  padding:24px 28px;font-size:12.5px;color:var(--ink-2)}
.annexe h3{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);
  margin:26px 0 10px;font-weight:650}
.annexe h3:first-of-type{margin-top:0}
.annexe dt{font-weight:620;color:var(--ink);margin-top:11px}
.annexe dd{margin:3px 0 0}
.annexe code{background:color-mix(in srgb,var(--ink) 8%,transparent);padding:1px 5px;
  border-radius:4px;font-size:11.5px}
.annexe ul{margin:8px 0 0;padding-left:18px}
.alerte{color:var(--mauvais)}
.fin{display:flex;align-items:center;gap:14px;margin-top:22px;padding-top:18px;
  border-top:1px solid var(--border);font-size:12px;color:var(--muted)}
.fin__coche{width:42px;height:42px;flex:none}

/* ---------------------------------------------------------- navigation --- */
.barre{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-top:14px;
  border:1px solid var(--border);border-radius:999px;padding:4px 6px}
.barre button{width:32px;height:32px;border-radius:50%;border:0;background:transparent;
  color:var(--ink-2);cursor:pointer;font-size:15px;line-height:1;transition:background .18s ease,color .18s ease}
.barre button:hover:not(:disabled){background:color-mix(in srgb,var(--ink) 10%,transparent);color:var(--ink)}
.barre button:disabled{opacity:.3;cursor:default}
.barre .compteur{font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums;
  padding:0 8px;letter-spacing:.04em}

/* --------------------------------------------------------- adaptations --- */
@media (max-width:1180px){
  .heros{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .carte{grid-column:span 12}
}
@media (max-width:820px){
  .rail{position:static;width:auto;flex-direction:row;align-items:center;gap:14px;
    border-right:0;border-bottom:1px solid var(--border);overflow-x:auto}
  .rail nav{flex-direction:row;margin-top:0}
  .rail__pied{display:none}
  main{margin-left:0;height:auto}
  .page{padding:26px 18px 110px}
  .couverture{padding:34px 18px}
}

/* Mouvement : coupé net si le système le demande. */
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important;
    scroll-behavior:auto!important}
  .carte{opacity:1;transform:none}
}

/* Impression : toutes les pages à la suite, sur fond blanc.
   Pour un vrai rendu papier, préférer « python export.py --clair ». */
@media print{
  body{background:#fff;color:#111;overflow:visible}
  .ambiance,.rail,.barre,.entrer,.flux{display:none!important}
  main{margin:0;height:auto;overflow:visible}
  .page{display:block!important;page-break-after:always;padding:0 0 24px;max-width:none}
  .carte,.synthese,.annexe,.kpi{break-inside:avoid;opacity:1;transform:none;
    background:#fff;border-color:#ddd}
  .couverture{min-height:auto}
}
"""


# =============================================================================
#  FRAGMENTS
# =============================================================================
def _e(texte: object) -> str:
    return html.escape(str(texte), quote=True)


FLECHES = {"hausse": "▲", "baisse": "▼", "plat": ""}


def _puce(kpi: core.Kpi) -> str:
    if not kpi.delta_affichage:
        return ""
    fleche = FLECHES.get(kpi.delta_direction, "")
    return (f'<span class="puce puce--{_e(kpi.delta_sens)}">'
            f'{fleche} {_e(kpi.delta_affichage)}</span>')


def _kpi_html(kpi: core.Kpi) -> str:
    return (f'<div class="kpi" title="{_e(kpi.aide)}">'
            f'<div class="kpi__label">{_e(kpi.libelle)}</div>'
            f'<div class="kpi__valeur">{_e(kpi.affichage)}</div>'
            f'<div class="kpi__bas">{_puce(kpi)}'
            f'<span class="kpi__detail">{_e(kpi.detail)}</span></div></div>')


def _heros_html(analyse: core.Analysis) -> str:
    """Les quatre chiffres de couverture, animés au chargement."""
    par_cle = {k.cle: k for k in analyse.kpis}
    choisis = [par_cle[c] for c in CLES_HEROS if c in par_cle] or analyse.kpis[:4]
    cases = []
    for kpi in choisis:
        cases.append(
            f'<div class="h"><div class="h__label">{_e(kpi.libelle)}</div>'
            f'<div class="h__valeur" data-compteur="{_e(kpi.valeur if kpi.valeur is not None else "")}">'
            f'{_e(kpi.affichage)}</div>'
            f'<div class="h__detail">{_e(kpi.detail)}</div></div>')
    return f'<div class="heros">{"".join(cases)}</div>'


def _tableau_html(tableau: pd.DataFrame) -> str:
    if tableau is None or tableau.empty:
        return ""
    return tableau.to_html(index=False, escape=True, border=0, na_rep="—",
                           classes="donnees", justify="right")


def _carte_html(bloc: core.Block, indice: int) -> str:
    classe = "carte carte--large" if bloc.large else "carte"
    note = f'<div class="carte__note">{_e(bloc.note)}</div>' if bloc.note else ""
    tableau = _tableau_html(bloc.tableau)
    details = (f'<details><summary>Voir les données ({len(bloc.tableau)} ligne(s))</summary>'
               f'<div class="tableau">{tableau}</div></details>' if tableau else "")
    figure = pio.to_html(bloc.figure, include_plotlyjs=False, full_html=False,
                         config=core.PLOT_CONFIG, div_id=f"graphique-{indice}",
                         default_width="100%")
    return (f'<section class="{classe}" id="bloc-{_e(bloc.cle)}">'
            f'<div class="carte__titre">{_e(bloc.titre)}</div>'
            f'<div class="carte__accroche">{_e(bloc.accroche)}</div>'
            f'{figure}{details}{note}</section>')


def _synthese_html(analyse: core.Analysis) -> str:
    points = [b for cle in CLES_SYNTHESE for b in analyse.blocs if b.cle == cle]
    if not points:
        points = analyse.blocs[:5]
    items = "".join(f"<li><b>{_e(b.titre)}</b> — {_e(b.accroche)}</li>" for b in points)
    return f'<div class="synthese"><h3>Ce qu\'il faut retenir</h3><ul>{items}</ul></div>'


def _annexe_html(analyse: core.Analysis) -> str:
    rapport, stats = analyse.rapport, analyse.stats
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
                  "régression. Deux intervalles qui se recouvrent ne permettent pas de conclure "
                  "à une différence.</dd>")
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
        detail = " ; ".join(
            f"{_e(c.nom)} : {core.fmt_dec(c.valeur, 2)} j ({core.fmt_p(c.p_value)})"
            for c in modele.explicatives)
        lignes.append(
            f"<dt>Facteurs du délai (régression multiple)</dt><dd>R² ajusté = "
            f"{core.fmt_dec(modele.r2_ajuste, 2)}, n = {core.fmt_int(modele.n)}. {detail}.</dd>")
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
            lignes.append("<ul>" + "".join(f"<li>{_e(a)}</li>" for a in rapport.alertes) + "</ul>")
        else:
            lignes.append("<p>Aucune anomalie détectée à l'import.</p>")
    if analyse.erreurs:
        lignes.append('<h3 class="alerte">Blocs non construits</h3><ul>'
                      + "".join(f"<li>{_e(e)}</li>" for e in analyse.erreurs) + "</ul>")

    coche = ('<div class="fin__coche" id="lottie-valide"></div>'
             if core.animation("valide") else "")
    lignes.append(
        f'<div class="fin">{coche}'
        '<div>Rapport complet. Graphiques interactifs, aucune connexion requise.<br>'
        'Pour une impression papier : <code>python export.py --clair</code>.</div></div>')
    return f'<div class="annexe">{"".join(lignes)}</div>'


# =============================================================================
#  SCRIPT EMBARQUÉ — pagination, animations, révélation
# =============================================================================
SCRIPT = r"""
(function () {
  const pages = [...document.querySelectorAll('.page')];
  const liens = [...document.querySelectorAll('.lien')];
  const compteur = document.getElementById('compteur');
  const precedent = document.getElementById('precedent');
  const suivant = document.getElementById('suivant');
  const sobre = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let courante = 0;

  function redimensionner(page) {
    if (!window.Plotly) return;
    page.querySelectorAll('.js-plotly-plot').forEach(function (d) {
      try { window.Plotly.Plots.resize(d); } catch (e) {}
    });
  }

  function reveler(page) {
    const cartes = [...page.querySelectorAll('.carte')];
    if (sobre || !('IntersectionObserver' in window)) {
      cartes.forEach(c => c.classList.add('vue'));
      return;
    }
    const obs = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('vue'); obs.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    cartes.forEach(c => obs.observe(c));
  }

  function afficher(i) {
    courante = Math.max(0, Math.min(pages.length - 1, i));
    pages.forEach((p, k) => p.classList.toggle('actif', k === courante));
    liens.forEach((l, k) => l.setAttribute('aria-current', k === courante ? 'page' : 'false'));
    const main = document.querySelector('main');
    if (main) main.scrollTop = 0;
    compteur.textContent = String(courante).padStart(2, '0') + ' / '
                         + String(pages.length - 1).padStart(2, '0');
    precedent.disabled = courante === 0;
    suivant.disabled = courante === pages.length - 1;
    const page = pages[courante];
    reveler(page);
    // Plotly mesure à zéro dans un conteneur masqué : on redimensionne à
    // l'affichage, sinon les graphiques sortent écrasés.
    requestAnimationFrame(() => redimensionner(page));
    setTimeout(() => redimensionner(page), 260);
    if (history.replaceState) history.replaceState(null, '', '#page-' + courante);
  }

  liens.forEach((l, k) => l.addEventListener('click', () => afficher(k)));
  precedent.addEventListener('click', () => afficher(courante - 1));
  suivant.addEventListener('click', () => afficher(courante + 1));
  const entrer = document.getElementById('entrer');
  if (entrer) entrer.addEventListener('click', () => afficher(1));

  document.addEventListener('keydown', function (e) {
    if (e.target.matches('input,textarea')) return;
    if (e.key === 'ArrowRight' || e.key === 'PageDown') { afficher(courante + 1); e.preventDefault(); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { afficher(courante - 1); e.preventDefault(); }
    else if (e.key === 'Home') { afficher(0); e.preventDefault(); }
    else if (e.key === 'End') { afficher(pages.length - 1); e.preventDefault(); }
    else if (/^[0-9]$/.test(e.key)) { afficher(parseInt(e.key, 10)); }
  });
  window.addEventListener('resize', () => redimensionner(pages[courante]));

  /* ---- Animations Lottie (lecteur et données embarqués) ---- */
  if (window.lottie && window.ANIMATIONS) {
    const monter = function (id, nom, boucle) {
      const hote = document.getElementById(id);
      if (!hote || !window.ANIMATIONS[nom]) return null;
      const a = window.lottie.loadAnimation({
        container: hote, renderer: 'svg', loop: boucle, autoplay: !sobre,
        animationData: window.ANIMATIONS[nom],
        rendererSettings: { progressiveLoad: true }
      });
      if (sobre) a.goToAndStop(a.totalFrames - 1, true);
      return a;
    };
    monter('lottie-marque', 'marque', true);
    monter('lottie-flux', 'flux', false);
    const coche = monter('lottie-valide', 'valide', false);
    if (coche && !sobre) { coche.stop(); }
    // La coche ne se joue qu'une fois la page méthodologie ouverte.
    const pageFin = document.querySelector('.page:last-of-type');
    if (coche && pageFin) {
      const jouer = new MutationObserver(function () {
        if (pageFin.classList.contains('actif') && !sobre) { coche.goToAndPlay(0, true); }
      });
      jouer.observe(pageFin, { attributes: true, attributeFilter: ['class'] });
    }
  }

  /* ---- Compteurs de couverture : la valeur finale reste la vérité ---- */
  document.querySelectorAll('[data-compteur]').forEach(function (el) {
    const cible = parseFloat(el.getAttribute('data-compteur'));
    const final = el.textContent;
    if (sobre || !isFinite(cible) || cible === 0) return;
    const duree = 900, debut = performance.now();
    const chiffres = final.replace(/[0-9]/g, '0');
    el.textContent = chiffres;
    function pas(t) {
      const p = Math.min(1, (t - debut) / duree);
      const doux = 1 - Math.pow(1 - p, 3);
      if (p < 1) {
        const v = cible * doux;
        el.textContent = final.replace(/[0-9][0-9 ,.]*/, function (m) {
          const dec = (m.split(',')[1] || '').length;
          return v.toLocaleString('fr-FR', { minimumFractionDigits: dec,
                                             maximumFractionDigits: dec });
        });
        requestAnimationFrame(pas);
      } else { el.textContent = final; }
    }
    requestAnimationFrame(pas);
  });

  const depart = (location.hash.match(/^#page-(\d+)$/) || [])[1];
  afficher(depart ? parseInt(depart, 10) : 0);
})();
"""


# =============================================================================
#  ASSEMBLAGE
# =============================================================================
def construire_rapport(analyse: core.Analysis, titre: str = "Activité RFP / RFI") -> str:
    """Retourne le document HTML complet sous forme de chaîne."""
    if analyse.vide:
        raise ValueError("Aucune donnée à exporter : la sélection est vide.")

    sections = analyse.sections
    pages: list[str] = []
    liens: list[str] = []
    indice_figure = 0

    # ---- Page 0 : couverture --------------------------------------------
    flux = ('<div class="flux" id="lottie-flux"></div>' if core.animation("flux") else "")
    liens.append('<button class="lien" type="button"><span class="num">00</span>'
                 'Couverture</button>')
    # Le périmètre ne s'affiche que s'il restreint quelque chose : sur
    # l'historique complet, il répéterait la période déjà indiquée.
    portee = (f'<div class="portee">{_e(analyse.filtres.describe())}</div>'
              if analyse.filtres.actif else "")
    pages.append(
        '<section class="page couverture">'
        f'{flux}'
        '<div class="sur">Pôle réponse aux appels d\'offres · Gestion d\'actifs</div>'
        '<h1>Activité <em>RFP / RFI</em></h1>'
        f'<p class="accroche">{core.fmt_int(len(analyse.df))} demandes analysées'
        f'&#8239;·&#8239;{len(analyse.blocs)} analyses'
        f'&#8239;·&#8239;{_e(analyse.periode)}</p>'
        f'{portee}'
        f'{_heros_html(analyse)}'
        '<button class="entrer" id="entrer" type="button">Ouvrir le rapport →</button>'
        '</section>')

    # ---- Pages 1..n : une par section ------------------------------------
    for numero, (cle, libelle) in enumerate(sections, start=1):
        blocs = analyse.section(cle)
        cartes = []
        for bloc in blocs:
            cartes.append(_carte_html(bloc, indice_figure))
            indice_figure += 1
        entete = (f'<div class="tete"><span class="num">{numero:02d}</span>'
                  f'<h2>{_e(libelle)}</h2>'
                  f'<span class="compte">{len(blocs)} analyse(s)</span></div>')
        # Les indicateurs et la synthèse ouvrent la première section.
        ouverture = ""
        if numero == 1:
            comparaison = ""
            fenetre = analyse.stats.get("comparaison")
            if fenetre:
                comparaison = (f" Les variations sont mesurées face à la période précédente de "
                               f"même durée ({core.fmt_date(fenetre[0])} → "
                               f"{core.fmt_date(fenetre[1])}).")
            ouverture = (f'<div class="kpis">{"".join(_kpi_html(k) for k in analyse.kpis)}</div>'
                         f'<p class="avertissement">{_e(core.NOTE_CENSURE)}{_e(comparaison)}</p>'
                         f'{_synthese_html(analyse)}')
        liens.append(f'<button class="lien" type="button"><span class="num">{numero:02d}</span>'
                     f'{_e(libelle)}</button>')
        pages.append(f'<section class="page">{entete}{ouverture}'
                     f'<div class="grille">{"".join(cartes)}</div></section>')

    # ---- Dernière page : méthodologie ------------------------------------
    numero = len(sections) + 1
    liens.append(f'<button class="lien" type="button"><span class="num">{numero:02d}</span>'
                 f'Méthodologie</button>')
    pages.append(
        f'<section class="page"><div class="tete"><span class="num">{numero:02d}</span>'
        f'<h2>Méthodologie &amp; qualité des données</h2></div>'
        f'{_annexe_html(analyse)}</section>')

    animations = {nom: core.animation(nom) for nom in ("marque", "flux", "valide")}
    animations = {k: v for k, v in animations.items() if v}
    lecteur = core.lecteur_lottie()
    bloc_lottie = (f'<script>{lecteur}</script>'
                   f'<script>window.ANIMATIONS={json.dumps(animations, separators=(",", ":"))};</script>'
                   if lecteur and animations else "")
    marque = ('<div class="rail__marque" id="lottie-marque"></div>'
              if animations.get("marque") else "")
    genere = analyse.genere_le.strftime("%d/%m/%Y à %H:%M")

    return f"""<!doctype html>
<html lang="fr" data-theme="{core.THEME}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_e(titre)} — rapport du {analyse.genere_le:%d/%m/%Y}</title>
<style>{core.police_css()}{_variables_css()}{CSS}</style>
<!-- Plotly doit précéder les graphiques : chaque figure s'initialise par un
     script en ligne posé dans la page. -->
<script>{bibliotheque_plotly()}</script>
</head>
<body>
<div class="ambiance"></div>

<aside class="rail">
  <div class="rail__tete">
    {marque}
    <div class="rail__titre">{_e(titre)}<span>Rapport d'activité</span></div>
  </div>
  <nav>{"".join(liens)}</nav>
  <div class="barre">
    <button id="precedent" type="button" title="Page précédente (←)">‹</button>
    <span class="compteur" id="compteur">00 / 00</span>
    <button id="suivant" type="button" title="Page suivante (→)">›</button>
  </div>
  <div class="rail__pied">
    <b>{core.fmt_int(len(analyse.df))}</b> demandes<br>
    {_e(analyse.periode)}<br>
    Édité le {genere}
  </div>
</aside>

<main>{"".join(pages)}</main>

{bloc_lottie}
<script>{SCRIPT}</script>
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
    parseur = argparse.ArgumentParser(description="Rapport d'activité RFP / RFI autonome.")
    parseur.add_argument("--clair", action="store_true",
                         help="thème clair, adapté à l'impression papier")
    parseur.add_argument("--sortie", default=str(CHEMIN_RAPPORT),
                         help="chemin du fichier HTML produit")
    options = parseur.parse_args()

    core.appliquer_theme("clair" if options.clair else "sombre")
    print(f"Thème : {core.THEME}")
    print("Chargement des données…")
    df, rapport = core.load_data()
    # Aucune borne : le rapport en ligne de commande couvre tout l'historique,
    # et la couverture n'a pas à répéter une période déjà affichée.
    filtres = core.Filters()
    print(f"Analyse de {core.fmt_int(len(df))} demandes…")
    analyse = core.build_analysis(df, filtres, rapport)
    if analyse.erreurs:
        print("Avertissements :", *analyse.erreurs, sep="\n  - ")
    chemin = ecrire_rapport(analyse, options.sortie)
    poids = chemin.stat().st_size / 1_048_576
    print(f"Rapport écrit : {chemin.resolve()}  ({poids:.1f} Mo, "
          f"{len(analyse.blocs)} graphiques, {len(analyse.kpis)} indicateurs)")
    print("Ouvrable d'un double-clic, sans Python ni connexion réseau.")


if __name__ == "__main__":
    main()
