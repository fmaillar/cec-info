# CEC → GNU Info

Convertit le **Catéchisme de l'Église catholique** publié par le Vatican
(IntraText, version française) en un manuel **GNU Texinfo / Info** lisible dans
Emacs.

## Dépendances (Debian)

```sh
sudo apt install python3-bs4 texinfo
```

`pandoc` n'est pas nécessaire.

La génération PDF demande également une installation TeX fournissant
`texi2dvi` et un convertisseur DVI vers PDF (par exemple `texlive` sur Debian).

## Utilisation

```sh
make
```

Le script crée :

- `.cec-cache/` : cache local des pages HTML ;
- `catechisme.texi` : source Texinfo ;
- `catechisme.info` : manuel GNU Info ;
- `catechisme.pdf` : version PDF ;
- `catechisme.epub` : livre EPUB 3.

Pour ne produire qu'un format :

```sh
make info
make pdf
make epub
```

Les tests locaux se lancent avec `make test`.

Pour forcer un nouveau téléchargement :

```sh
python3 cec2info.py --refresh --compile --pdf --epub
```

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

## Droits

Ce projet ne contient pas le texte du Catéchisme. Il ne contient que le
convertisseur. Le texte est téléchargé depuis le site officiel du Vatican au
moment de la génération et reste soumis aux droits indiqués par son éditeur.
