# CEC → GNU Info

[![CI](https://github.com/fmaillar/cec-info/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/fmaillar/cec-info/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/fmaillar/cec-info)](https://github.com/fmaillar/cec-info/releases/latest)
[![Licence GPL-3.0-or-later](https://img.shields.io/badge/licence-GPL--3.0--or--later-blue.svg)](LICENSE)

Convertit le **Catéchisme de l'Église catholique** publié par le Vatican
(IntraText, version française) en manuel **GNU Texinfo / Info**, PDF et EPUB 3.
La sortie Info est directement lisible dans Emacs.

## Dépendances (Debian)

```sh
sudo apt install python3-bs4 texinfo
```

`pandoc` n'est pas nécessaire.

La génération PDF demande également une installation TeX fournissant
`texi2dvi` et un convertisseur DVI vers PDF (par exemple `texlive` sur Debian).

Le projet peut aussi être installé dans un environnement Python :

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cec2info --help
```

## Utilisation

```sh
make
```

Le script crée :

- `.cec-cache/` : cache local des pages HTML ;
- `catechisme.texi` : source Texinfo ;
- `catechisme.info` : manuel GNU Info ;
- `catechisme.pdf` : version PDF ;
- `catechisme.epub` : livre EPUB 3 ;
- `generation-report.json` : rapport de génération exploitable par un outil.

Pour ne produire qu'un format :

```sh
make info
make pdf
make epub
```

Les tests locaux se lancent avec `make test`.

La génération vérifie que les paragraphes 1 à 2865 sont tous présents une
seule fois avant de compiler les formats finaux. Les pages IntraText absentes
du sommaire sont récupérées automatiquement grâce aux liens `Suivant`.
Pour un autre corpus, adaptez la borne avec
`--expected-last-paragraph`, ou utilisez la valeur `0` pour désactiver ce
contrôle.

Un rapport lisible est toujours affiché à la fin. Pour demander explicitement
un rapport JSON avec la commande installée :

```sh
cec2info --compile --pdf --epub --report-json generation-report.json
```

Le JSON contient la source, le nombre d'entrées, les pages liées et orphelines,
la couverture des paragraphes, ainsi que le chemin et la taille de chaque
sortie.

## Architecture

Le point d'entrée `cec2info.py` conserve l'interface publique et orchestre la
commande. Les responsabilités internes sont séparées sans modifier son usage :

- `cec2info_network.py` : téléchargement, reprises et cache atomique ;
- `cec2info_parser.py` : analyse du sommaire et des pages HTML IntraText ;
- `cec2info_output.py` : Texinfo, validation, rapports et compilation ;
- `cec2info_model.py` : arbre du document et normalisation partagée.

Les fonctions historiquement importables depuis `cec2info` y restent
réexportées pour préserver la compatibilité.

Pour forcer un nouveau téléchargement :

```sh
make refresh
```

`make clean` retire les sorties et auxiliaires de compilation ;
`make distclean` retire aussi le cache HTML et les caches Python.

## Intégration continue

Le workflow GitHub Actions `.github/workflows/ci.yml` teste Python 3.10 et
3.13 sous Ubuntu, ainsi que Python 3.13 sous macOS et Windows. Il vérifie le
code avec Ruff et mypy, contrôle la commande `cec2info` et construit une wheel sans
télécharger le corpus du Vatican. Ubuntu impose en plus au moins 95 % de
couverture de branches et compile réellement les sorties Info/PDF/EPUB ; les
autres plateformes exécutent les tests Python et ignorent ces tests lorsque
les outils Texinfo/TeX ne sont pas installés. Localement, `make check`
reproduit les contrôles de qualité Python.

Un mini-corpus HTML local exerce aussi toute la chaîne déterministe : sommaire,
page orpheline, paragraphes, Texinfo et rapport JSON. La CI ne dépend donc pas
du réseau pour détecter une régression d'intégration.

Le typage statique progressif peut aussi être exécuté séparément avec
`make typecheck`.

Les actions tierces sont épinglées par empreinte Git complète. Dependabot
surveille ces références chaque semaine et propose leurs mises à jour.

## Publication

Un tag `vX.Y.Z` correspondant à la version de `pyproject.toml` déclenche les
tests, construit le wheel et le paquet source, puis publie une GitHub Release.

La publication PyPI utilise Trusted Publishing (OIDC), sans secret permanent.
Le publisher PyPI doit cibler le propriétaire `fmaillar`, le dépôt `cec-info`,
le workflow `release.yml` et l'environnement GitHub `pypi`. La variable de
dépôt `PYPI_PUBLISH` active cette étape lorsqu'elle vaut `true`.

## Lecture dans Emacs

```elisp
(info "/chemin/vers/catechisme.info")
```

## Installation dans le répertoire Info utilisateur

```sh
mkdir -p ~/.local/share/info
cp catechisme.info ~/.local/share/info/
install-info ~/.local/share/info/catechisme.info ~/.local/share/info/dir
```

Puis, si ce répertoire n'est pas déjà connu d'Emacs :

```elisp
(add-to-list 'Info-default-directory-list
             (expand-file-name "~/.local/share/info/"))
```

Ensuite : `M-x info`, puis `m Catéchisme`.

## Navigation

- `n`, `p`, `u` : suivant, précédent, parent ;
- `m` : sélectionner une entrée du menu ;
- `i RET 2270 RET` : aller à l'entrée d'index du § 2270 ;
- `s RET eucharistie RET` : recherche plein texte.

Le script utilise automatiquement les pages `__P*.HTM` du système IntraText :
ce sont les variantes de lecture sans les milliers de liens de concordance.

## Licence et droits sur le texte

Le convertisseur est distribué sous la licence GNU GPL version 3 ou toute
version ultérieure. Consultez le fichier `LICENSE`.

Cette licence ne couvre pas le texte du Catéchisme. Le projet ne distribue que
le convertisseur ; le texte est téléchargé depuis le site officiel du Vatican
au moment de la génération et reste soumis aux droits indiqués par son éditeur.

Les vulnérabilités doivent être signalées de manière privée conformément à la
[politique de sécurité](SECURITY.md), et non dans une issue publique.
