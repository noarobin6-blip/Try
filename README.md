# Dashboard d'activité RFP / RFI

Tableau de bord d'un pôle de réponse aux appels d'offres en gestion d'actifs :
flux de demandes, délais de traitement, taux de succès, charge d'équipe et
analyse statistique des facteurs de délai.

Trois fichiers Python, un thème sombre, cinq pages à l'écran, et un rapport HTML
autonome paginé que l'on peut envoyer par courriel.

---

## Démarrer en 2 minutes

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur **http://localhost:8501** (le navigateur démarre seul ;
sinon, coller l'adresse). Port déjà pris ? `streamlit run app.py --server.port 8502`.
`Ctrl + C` arrête le serveur.

Elle démarre sur un jeu de **données synthétiques** (36 mois, ~1 800 demandes,
saisonnalité et taux de succès crédibles) : rien à configurer pour la découvrir.

Deux autres commandes :

```bash
python core.py                # contrôle la chaîne de bout en bout, statistiques comprises
python export.py              # écrit rapport.html (thème sombre, écran)
python export.py --clair      # même rapport en thème clair, pour l'impression
```

---

## Brancher les vraies données (5 minutes)

Tout se passe dans le bloc **`[BRANCHEMENT PRINCIPAL]`**, en tête de `core.py`.
Aucun autre fichier n'est à modifier.

1. `USE_FAKE_DATA = False`
2. `DATA_PATH = "chemin/vers/le/classeur.xlsx"`
3. `SHEET_NAME = "nom de l'onglet"`
4. `COLUMN_MAP` : à droite, le nom réel de chaque colonne du classeur.

**La correspondance est tolérante** : casse, accents, espaces, tirets et
underscores sont ignorés — `"Date Réception"`, `"date_reception"` et
`"DATE-RECEPTION"` désignent la même colonne. Une table `COLUMN_ALIASES`
reconnaît en plus les intitulés courants (`"Date de réception"`,
`"Nombre de questions"`, `"Asset class"`…). Si un intitulé maison n'est pas
reconnu, il suffit de l'ajouter à cette liste.

**Colonnes indispensables** : date de réception, type de demande, statut.
Toutes les autres sont facultatives : si elles manquent, les analyses
correspondantes disparaissent proprement, l'application ne casse pas.

**Modalités** : `STATUS_NORMALIZATION`, `TYPE_NORMALIZATION`,
`CLIENT_TYPE_NORMALIZATION` et `LANGUE_NORMALIZATION` ramènent les variantes
d'écriture (`"gagne"`, `"GAGNÉ"`, `"won"`) à une valeur unique. Une modalité
inconnue n'est jamais supprimée : elle reste affichée et remonte dans la page
« Données & qualité », avec l'invitation à l'ajouter à la table.

**Paramètres métier** : délais cibles par type (`SLA_JOURS_OUVRES`), horizon de
projection, seuil de significativité, thème par défaut — même bloc.

> Les données réelles ne doivent pas rejoindre le dépôt : `.gitignore` exclut
> déjà `*.xlsx`, `*.csv` et le rapport généré.

---

## Architecture

| Fichier | Rôle | Dépendance à Streamlit |
|---|---|---|
| `core.py` | Configuration, lecture Excel, normalisation, calculs, statistiques, thèmes et figures Plotly | **aucune** |
| `app.py` | Interface : 5 pages, filtres, indicateurs | oui |
| `export.py` | Rapport HTML autonome, paginé | non |
| `assets/` | Police Inter (OFL), lecteur Lottie (MIT), 4 animations | — |
| `.streamlit/config.toml` | Thème sombre des widgets Streamlit | — |

`core.py` produit un objet `Analysis` (indicateurs + blocs d'analyse) que
`app.py` et `export.py` consomment **à l'identique** : une analyse ajoutée au
cœur apparaît automatiquement à l'écran *et* dans le rapport.

Ajouter une analyse = écrire une fonction `_bloc_xxx(df, mensuel, stats)` qui
renvoie un `Block`, puis l'inscrire dans le tuple `_CONSTRUCTEURS`. Un bloc qui
échoue est signalé dans la page qualité, il n'interrompt jamais le reste.

---

## Ce que contient le tableau de bord

**8 indicateurs** comparés à la période précédente de même durée : demandes
reçues, questions traitées, délai médian, respect du délai cible, taux de succès
(avec intervalle de confiance), encours remporté, encours en jeu, dossiers
ouverts.

**14 analyses** réparties en cinq pages :

- *01 Vue d'ensemble* — flux mensuel par type avec tendance, entonnoir de
  conversion, état du portefeuille ;
- *02 Performance commerciale* — taux de succès par classe d'actifs (IC de
  Wilson), encours en jeu par statut, comptes les plus sollicitants, origine
  géographique ;
- *03 Efficacité opérationnelle* — distribution des délais par type face au
  délai cible, évolution mensuelle du délai, charge par analyste, saisonnalité ;
- *04 Analyse statistique* — régression délai / volume de questions, régression
  multiple des facteurs de délai, projection du flux à 6 mois ;
- *05 Données & qualité* — table détaillée, export CSV, journal d'import,
  génération du rapport.

Chaque graphique est accompagné d'une phrase de lecture chiffrée, d'une note
méthodologique et de son **jumeau tableau** (« Voir les données »).

---

## Design

**Thème sombre** par défaut, défini une seule fois dans `core.py` (`THEMES`) et
consommé par l'écran comme par le rapport : les deux ne peuvent pas diverger.
`core.appliquer_theme("clair")` bascule l'ensemble, y compris les figures.

**Palette validée** sur sa propre surface (`#14181e`) : bande de clarté, plancher
de chroma, séparation sous daltonisme et contraste ≥ 3:1 — les huit teintes
passent, et les trois premières restent valides en toutes-paires pour les nuages
de points. L'ordre des teintes est le mécanisme de sécurité, pas une préférence :
ne pas permuter sans revalider. L'identité d'une série n'est jamais portée par la
seule couleur (légende, libellés directs, tableau équivalent), et les couleurs
d'état (gagné / perdu / abandonné) s'accompagnent toujours du libellé et de la
valeur.

**Typographie** : Inter variable (licence SIL OFL), embarquée en base64 — même
rendu sur un poste hors ligne et dans un rapport transmis par courriel. Chiffres
tabulaires partout où des valeurs s'alignent.

**Animations Lottie**, jouées en local (lecteur `lottie_light`, MIT, servi depuis
`assets/` — jamais un CDN) :

| Animation | Où | Rôle |
|---|---|---|
| `marque` | barre latérale, rail du rapport | identité : les barres et leur tendance |
| `flux` | couverture du rapport | la courbe se trace à l'ouverture |
| `chargement` | pendant la génération du rapport | état d'attente |
| `valide` | rapport prêt, fin de la méthodologie | confirmation |

Elles sont générées depuis la palette du tableau de bord, pas récupérées toutes
faites. Le mouvement sert un état ou un moment de lecture ; il n'y a aucune
boucle décorative à côté d'un graphique. `prefers-reduced-motion` coupe tout et
affiche l'image finale.

Si `assets/` est absent, l'interface perd ses animations et sa police — jamais
son contenu.

---

## Méthodologie

- **Délai de traitement** : jours **ouvrés** entre réception et envoi
  (`numpy.busday_count`). Les dossiers non envoyés n'entrent dans aucune
  statistique de délai.
- **Taux de succès** : gagnées / (gagnées + perdues). Les dossiers en attente de
  décision sont exclus du dénominateur, jamais comptés comme des échecs.
- **Intervalles de confiance** : Wilson à 95 % pour les proportions, Student à
  95 % pour les coefficients de régression.
- **Régressions** : moindres carrés ordinaires, simples et multiples, avec
  erreurs types, statistiques *t* et p-values. La loi de Student est évaluée par
  la fonction bêta incomplète régularisée implémentée dans `core.py` : ni SciPy
  ni statsmodels ne sont nécessaires, et `python core.py` vérifie les valeurs
  contre les tables de référence.
- **Mois en cours** : toujours exclu des ajustements de tendance, et signalé
  comme partiel sur les graphiques de volume.
- **Censure à droite** : les clients tranchent plusieurs mois après l'envoi. Sur
  une période récente, le taux de succès et l'encours remporté sont donc
  mécaniquement sous-évalués, et l'encours en jeu surévalué. L'avertissement est
  affiché sous les indicateurs.

---

## Rapport HTML

Le bouton « Générer le rapport » (page *Données & qualité*) produit un fichier
unique d'environ 4,5 Mo reprenant le périmètre filtré :

- une **couverture** avec les quatre chiffres clés et la courbe qui se trace ;
- **cinq pages** navigables au clic, aux flèches ← →, aux touches 0-5, avec
  `Début` / `Fin` ;
- les 14 analyses interactives, leurs tableaux de données et une annexe
  méthodologique.

Plotly, Lottie, les animations et la police y sont embarqués : le fichier
s'ouvre d'un double-clic, sans Python, sans serveur et sans connexion réseau.

Pour l'impression papier, préférer `python export.py --clair` : le thème sombre
est fait pour l'écran, et imprimer un aplat foncé gaspille de l'encre pour un
résultat moins lisible.
