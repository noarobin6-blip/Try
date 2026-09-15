# RFP Intelligence

Produit de pilotage de l'activité **RFP / Due Diligence** d'une société de
gestion d'actifs. Il répond aux six questions qui structurent le pilotage du
pôle : combien de demandes arrivent, dans quelle proportion RFP / due diligence,
à quelle vitesse l'équipe les traite, ce que deviennent les appels d'offres,
quel encours ils rapportent, et comment tout cela évolue sur dix ans.

Trois fichiers Python, neuf pages, un rapport HTML autonome.

---

## Démarrer en 2 minutes

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur **http://localhost:8501**. Port occupé ?
`streamlit run app.py --server.port 8502`. `Ctrl + C` arrête le serveur.

Elle démarre sur un jeu de **données de démonstration** couvrant 2014 → aujourd'hui
(~1 700 questionnaires). Rien à configurer pour la découvrir.

```bash
python core.py                # contrôle la chaîne de bout en bout
python export.py              # écrit rapport.html (thème institutionnel)
python export.py --clair      # variante claire, pour l'impression
```

---

## Architecture

| Fichier | Rôle | Dépendance à Streamlit |
|---|---|---|
| `core.py` | Configuration, lecture Excel, normalisation, **couche métrique**, statistiques, thèmes, figures Plotly, moteur d'insights | **aucune** |
| `app.py` | Interface : navigation, filtres globaux, drill-down, explorateur, export | oui |
| `export.py` | Rapport HTML autonome, paginé | non |
| `assets/` | Police Inter (OFL), lecteur Lottie (MIT), 4 animations | — |

`core.py` produit un objet `Analysis` — indicateurs, blocs d'analyse, constats —
que `app.py` et `export.py` consomment **à l'identique**. Un chiffre affiché à
l'écran est le même que dans le rapport, par construction.

**Couche métrique.** Chaque indicateur est défini une fois, dans une fonction
documentée (`taux_succes_rfp`, `aum_gagne`, `cadence_mensuelle`, `croissance`…).
Deux graphiques ne peuvent pas compter la même chose différemment.

**Ajouter une analyse** : écrire `_bloc_xxx(df, mensuel, stats)` qui renvoie un
`Block`, puis l'inscrire dans `_CONSTRUCTEURS`. Elle apparaît automatiquement
dans la page de sa section **et** dans le rapport. Un bloc qui échoue est
signalé dans la page qualité ; il n'interrompt jamais l'écran.

---

## Les neuf pages

| Page | Question à laquelle elle répond |
|---|---|
| **Vue d'ensemble** | Où en est l'activité, qu'est-ce qui demande une action aujourd'hui ? |
| **Activité** | La charge augmente-t-elle ? À quelle vitesse la traite-t-on ? |
| **Pipeline RFP** | Que deviennent les appels d'offres, et où gagne-t-on ? |
| **Due diligence** | Quelles expertises et quels pays absorbent la charge ? |
| **Encours & gains** | Combien l'effort commercial rapporte-t-il réellement ? |
| **ESG** | Quel poids prend la composante ESG, et chez qui ? |
| **Insights** | Que faut-il retenir, et qu'est-ce qui explique les délais ? |
| **Explorateur** | Du chiffre agrégé au dossier individuel. |
| **Qualité & export** | D'où viennent les données, que valent-elles, comment les diffuser ? |

### Drill-down

Le produit ne laisse jamais dans une impasse analytique :

- **une carte d'indicateur est un lien** — « Appels d'offres » ouvre le pipeline
  RFP, « Encours remporté » ouvre la page des gains ;
- **un clic sur une barre filtre tout le tableau de bord** — cliquer
  « Investment Solutions » sur la charge par expertise recalcule l'ensemble des
  pages sur cette expertise ;
- **un clic sur une ligne de l'explorateur ouvre la fiche du dossier**, sans
  perdre les filtres ni la position dans la liste ;
- **la page vit dans l'URL** (`?page=rfp`) : le lien est partageable et le
  bouton « précédent » du navigateur fonctionne.

### Filtres

Une seule barre, au-dessus de tout ce qu'elle porte : période, puis les quatre
dimensions de premier niveau, les autres derrière « Plus de filtres ». Les
filtres actifs sont affichés en permanence sous le titre — on ne lit jamais un
chiffre sans savoir sur quoi il porte.

---

## Brancher vos données (5 minutes)

Tout se passe dans le bloc **`[BRANCHEMENT PRINCIPAL]`**, en tête de `core.py`.

1. `USE_FAKE_DATA = False`
2. `DATA_PATH` — chemin du classeur ; `SHEET_NAME` — onglet
3. `COLUMN_MAP` — nom réel de chaque colonne

**La correspondance est tolérante** : casse, accents, espaces, tirets et
underscores sont ignorés, et `COLUMN_ALIASES` reconnaît les intitulés courants
(`"Date de réception"`, `"Sub asset class"`, `"ESG %"`…).

**Colonnes indispensables** : date de réception, type de demande, statut. Toutes
les autres sont facultatives — si `Expertise` manque, la page due diligence
perd son classement par expertise et conserve le reste. Rien ne casse, et la
page « Qualité » dit précisément ce qui manque.

**Vocabulaire métier** — paramétrable dans le même bloc :

- `FAMILLE_PAR_TYPE` regroupe les types fins (RFP / RFI / DDQ) dans les deux
  familles du pilotage : **RFP** et **Due Diligence** ;
- `STATUS_NORMALIZATION` ramène les variantes d'écriture (`gagne`, `GAGNÉ`,
  `won`) à une valeur unique ; une modalité inconnue reste visible et remonte
  dans la page qualité ;
- la **part ESG** est acceptée sous trois formes : fraction (`0,45`),
  pourcentage (`45 %`) ou tranche écrite (`> 75 % ESG`). Une tranche écrite
  donne une tranche, jamais un pourcentage inventé ;
- `SLA_JOURS_OUVRES`, `HORIZONS_CROISSANCE`, `ESG_SEUIL_FORT`, `THEME_DEFAUT`.

> Les données réelles ne doivent pas rejoindre le dépôt : `.gitignore` exclut
> `*.xlsx`, `*.csv` et le rapport généré.

---

## Définitions qui engagent

- **Famille** — RFP d'un côté, toute la due diligence de l'autre. C'est la
  lecture du pôle ; le type fin reste disponible en filtre.
- **Résultat** — n'existe **que** pour un appel d'offres. Une due diligence ne
  se gagne pas : son résultat est « sans objet », pas « perdu ».
- **Taux de succès** — gagnés / (gagnés + perdus). Les dossiers en attente de
  décision sont exclus du dénominateur ; les compter comme des échecs
  fabriquerait un effondrement sur les périodes récentes.
- **Encours remporté** — encours des RFP gagnés, rattaché à l'année de
  réception du dossier.
- **Délai de traitement** — jours **calendaires** entre réception et envoi,
  comme au comité. Le respect du délai cible se mesure, lui, en jours ouvrés.
- **Cadence** — dossiers **terminés** par mois : la capacité de production de
  l'équipe, à distinguer de la charge qui lui arrive.
- **Croissance sur N ans** — dernière année civile **complète** contre celle
  d'il y a N ans. L'année en cours est exclue : la comparer à une année pleine
  afficherait un effondrement qui n'existe pas.
- **Limite de lecture** — les clients tranchent plusieurs mois après l'envoi.
  Sur une période récente, le taux de succès et l'encours remporté sont
  mécaniquement sous-évalués. L'avertissement est affiché sous les indicateurs.

Les **insights** sont calculés, jamais rédigés d'avance : chaque phrase provient
d'une fonction analytique, et disparaît si la donnée ne permet pas de
l'établir. Aucun chiffre n'est produit par un modèle de langage.

---

## Design

**Trois thèmes** définis une seule fois dans `core.py` et partagés par l'écran
et le rapport : *Institutionnel* (par défaut), *Sombre*, *Clair* pour
l'impression. Le sélecteur est en bas de la barre latérale.

**Palette validée** sur sa propre surface : bande de clarté, plancher de chroma,
séparation sous daltonisme et contraste — les huit teintes passent les
contrôles. L'ordre des teintes est le mécanisme de sécurité, pas une
préférence : ne pas permuter sans revalider. L'identité d'une série n'est jamais
portée par la seule couleur (légende, libellés directs, tableau équivalent), et
les couleurs d'état s'accompagnent toujours du libellé et de la valeur.

**Choix de formes assumés** : pas de camembert à vingt parts pour la répartition
par expertise — un classement en barres, queue regroupée dans « Autres ». Au-delà
de sept catégories, aucune part d'un disque n'est comparable à l'œil.

**Typographie** : Inter variable (SIL OFL) embarquée en base64 — même rendu hors
ligne et dans un rapport transmis par courriel. Chiffres tabulaires partout où
des valeurs s'alignent.

**Animations Lottie** jouées en local (lecteur `lottie_light`, MIT, servi depuis
`assets/`, jamais un CDN) : identité dans la barre latérale, tracé de couverture
du rapport, état de chargement, confirmation. Le mouvement sert un état ou un
moment de lecture. `prefers-reduced-motion` coupe tout.

Si `assets/` est absent, l'interface perd ses animations et sa police — jamais
son contenu.

---

## Rapport HTML

Le bouton « Générer le rapport » (page *Qualité & export*) produit un fichier
unique d'environ 4,7 Mo reprenant le périmètre filtré : couverture avec les
chiffres clés, constats calculés, sept pages navigables (clic, flèches ← →,
touches 0-7), les 24 analyses interactives, leurs tableaux et une annexe
méthodologique. Plotly, Lottie, les animations et la police y sont embarqués :
il s'ouvre d'un double-clic, sans Python, sans serveur, sans réseau.

---

## Données de démonstration

Le jeu par défaut est **explicitement synthétique** — la source est libellée
comme telle partout. Sa forme reproduit celle d'un pôle réel : due diligence
multipliée par quatre en dix ans à effectif RFP constant, creux d'août, délais
corrélés au volume de questions, collecte très concentrée sur quelques mandats.

Les volumes annuels sont paramétrés (`VOLUMES_ANNUELS`) de sorte que les trois
indicateurs de croissance du produit tombent sur ceux que publie le pôle :
**+49 % sur 3 ans, +149 % sur 5 ans, +158 % sur 10 ans**. `python core.py`
vérifie cette concordance à chaque exécution — c'est ainsi que les définitions
de métriques sont validées, et non par leur seul intitulé.
