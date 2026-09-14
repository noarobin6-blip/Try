# Dashboard d'activité RFP / RFI

Tableau de bord d'un pôle de réponse aux appels d'offres en gestion d'actifs :
flux de demandes, délais de traitement, taux de succès, charge d'équipe et
analyse statistique des facteurs de délai.

Trois fichiers, aucune dépendance lourde, et un rapport HTML autonome que l'on
peut envoyer par courriel.

---

## Démarrer en 2 minutes

```bash
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre sur un jeu de **données synthétiques** (36 mois, ~1 800
demandes, saisonnalité et taux de succès crédibles). Rien à configurer pour la
découvrir.

Deux autres commandes utiles :

```bash
python core.py      # contrôle la chaîne de bout en bout (statistiques comprises)
python export.py    # écrit rapport.html sans passer par l'interface
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
inconnue n'est jamais supprimée : elle reste affichée et remonte dans l'onglet
« Données & qualité », avec l'invitation à l'ajouter à la table.

**Paramètres métier** : délais cibles par type (`SLA_JOURS_OUVRES`), horizon de
projection, seuil de significativité — même bloc.

> Les données réelles ne doivent pas rejoindre le dépôt : `.gitignore` exclut
> déjà `*.xlsx`, `*.csv` et le rapport généré.

---

## Architecture

| Fichier | Rôle | Dépendance à Streamlit |
|---|---|---|
| `core.py` | Configuration, lecture Excel, normalisation, calculs, statistiques, figures Plotly | **aucune** |
| `app.py` | Interface interactive : filtres, indicateurs, onglets | oui |
| `export.py` | Rapport HTML autonome (Plotly embarqué, ouvrable sans Python) | non |
| `requirements.txt` | Dépendances | — |
| `.streamlit/config.toml` | Thème clair de l'interface | — |

`core.py` produit un objet `Analysis` (indicateurs + blocs d'analyse) que
`app.py` et `export.py` consomment **à l'identique** : une analyse ajoutée au
cœur apparaît automatiquement à l'écran *et* dans le rapport.

Ajouter une analyse = écrire une fonction `_bloc_xxx(df, mensuel, stats)` qui
renvoie un `Block`, puis l'inscrire dans le tuple `_CONSTRUCTEURS`. Un bloc qui
échoue est signalé dans l'onglet qualité, il n'interrompt jamais le reste.

---

## Ce que contient le tableau de bord

**8 indicateurs** comparés à la période précédente de même durée : demandes
reçues, questions traitées, délai médian, respect du délai cible, taux de
succès (avec intervalle de confiance), encours remporté, encours en jeu,
dossiers ouverts.

**14 analyses** réparties en quatre sections :

- *Vue d'ensemble* — flux mensuel par type avec tendance, entonnoir de
  conversion, état du portefeuille ;
- *Performance commerciale* — taux de succès par classe d'actifs (IC de
  Wilson), encours en jeu par statut, comptes les plus sollicitants, origine
  géographique ;
- *Efficacité opérationnelle* — distribution des délais par type face au délai
  cible, évolution mensuelle du délai, charge par analyste, saisonnalité ;
- *Analyse statistique* — régression délai / volume de questions, régression
  multiple des facteurs de délai, projection du flux à 6 mois.

Chaque graphique est accompagné d'une phrase de lecture chiffrée, d'une note
méthodologique et de son **jumeau tableau** (« Voir les données »).

---

## Méthodologie

- **Délai de traitement** : jours **ouvrés** entre réception et envoi
  (`numpy.busday_count`). Les dossiers non envoyés n'entrent dans aucune
  statistique de délai.
- **Taux de succès** : gagnées / (gagnées + perdues). Les dossiers en attente
  de décision sont exclus du dénominateur, jamais comptés comme des échecs.
- **Intervalles de confiance** : Wilson à 95 % pour les proportions, Student à
  95 % pour les coefficients de régression.
- **Régressions** : moindres carrés ordinaires, simples et multiples, avec
  erreurs types, statistiques *t* et p-values. La loi de Student est évaluée
  par la fonction bêta incomplète régularisée implémentée dans `core.py` :
  ni SciPy ni statsmodels ne sont nécessaires, et `python core.py` vérifie les
  valeurs contre les tables de référence.
- **Mois en cours** : toujours exclu des ajustements de tendance, et signalé
  comme partiel sur les graphiques de volume.
- **Censure à droite** : les clients tranchent plusieurs mois après l'envoi.
  Sur une période récente, le taux de succès et l'encours remporté sont donc
  mécaniquement sous-évalués, et l'encours en jeu surévalué. L'avertissement
  est affiché sous les indicateurs.

---

## Rapport HTML

Le bouton « Générer le rapport HTML » (onglet *Données & qualité*) produit un
fichier unique d'environ 4 Mo, reprenant le périmètre filtré : indicateurs,
synthèse, les 14 analyses interactives, les tableaux de données et une annexe
méthodologique. Plotly y est embarqué : le fichier s'ouvre d'un double-clic,
sans Python, sans serveur et sans connexion réseau. Il est aussi mis en page
pour l'impression.

---

## Accessibilité et lisibilité des graphiques

La palette est validée sur les critères de séparation daltonisme et de
contraste. L'identité d'une série n'est jamais portée par la seule couleur :
légende systématique, libellés directs, et tableau équivalent sous chaque
graphique. Les couleurs d'état (gagné / perdu / abandonné) s'accompagnent
toujours du libellé et de la valeur.
