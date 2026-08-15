# Journal des modifications

Les changements notables du projet sont documentés dans ce fichier.

Le format suit les principes de *Keep a Changelog* et les versions suivent le
versionnage sémantique.

## [Non publié]

### Ajouté

- README anglais utilisé comme présentation principale sur GitHub et PyPI,
  avec conservation de la documentation française dans `README.fr.md`.
- liens du projet, des issues et du journal des modifications dans les
  métadonnées du paquet.

### Modifié

- description courte du paquet traduite en anglais pour améliorer sa
  découvrabilité internationale.
- commentaires et docstrings du code source traduits en anglais, sans modifier
  les messages de l'interface française.

## [3.5.0] - 2026-08-15

### Ajouté

- contrôle statique progressif des types avec mypy sur tous les modules.
- mini-corpus IntraText local et test d'intégration déterministe de la chaîne
  complète jusqu'au rapport JSON.
- politique de sécurité et canal GitHub de signalement privé des vulnérabilités.
- épinglage par SHA des actions GitHub, avec suivi hebdomadaire par Dependabot.

## [3.4.0] - 2026-08-15

### Ajouté

- reprises réseau avec délai progressif et écritures atomiques du cache ;
- tests du CLI, des erreurs réseau, des pages dupliquées et cycliques, de
  l'extraction HTML et des outils système absents ;
- analyse Ruff et seuil minimal de 95 % de couverture de branches dans la CI ;
- tests de compatibilité sous macOS et Windows ;
- guide de contribution, code de conduite, formulaires d'issues et modèle de
  pull request.

### Modifié

- séparation de l'analyse des arguments et de l'exécution du convertisseur ;
- découpage du téléchargement, de la découverte et de l'affectation des pages ;
- version de l'agent HTTP issue des métadonnées du paquet ;
- séparation du réseau, de l'analyse HTML, de la génération et du modèle dans
  des modules spécialisés, avec maintien de l'interface publique historique.

### Corrigé

- construction des chemins d'URL avec des séparateurs POSIX sous Windows.
- rejet des délais négatifs lors d'un appel direct à l'API de téléchargement.
- appels aux compilateurs avec des exécutables statiques après contrôle de leur
  présence, sans interprétation par un shell.

## [3.3.1] - 2026-08-15

### Ajouté

- publication automatique des GitHub Releases à partir des tags `vX.Y.Z` ;
- construction automatique du wheel et du paquet source ;
- préparation de la publication PyPI sans secret avec Trusted Publishing ;
- mises à jour hebdomadaires Dependabot pour Python et GitHub Actions ;
- badges CI, release et licence dans le README.

### Modifié

- suppression des doubles exécutions CI sur les branches de pull request ;
- annulation automatique d'une ancienne CI lorsqu'un nouveau commit arrive ;
- métadonnées de licence migrées vers l'expression SPDX
  `GPL-3.0-or-later`.

## [3.3.0] - 2026-08-15

### Ajouté

- génération complète des formats GNU Info, PDF et EPUB 3 ;
- commande installable `cec2info` et métadonnées `pyproject.toml` ;
- rapports de génération lisible et JSON ;
- tests de compilation réels pour les trois formats ;
- intégration continue sur Python 3.10 et 3.13 ;
- licence GNU GPL version 3 ou ultérieure pour le convertisseur.

### Corrigé

- conservation unique de tous les paragraphes numérotés de 1 à 2865 ;
- récupération des pages orphelines absentes de la navigation principale ;
- séparation des caches lorsque la source utilisée n'est pas la source
  officielle ;
- dépendance `Archive::Zip` nécessaire à la génération EPUB dans la CI.

### Modifié

- génération rendue déterministe et validée avant la création des sorties ;
- documentation de l'installation, de la CI et des rapports de génération.

[3.5.0]: https://github.com/fmaillar/cec-info/compare/v3.4.0...v3.5.0
[3.4.0]: https://github.com/fmaillar/cec-info/compare/v3.3.1...v3.4.0
[3.3.1]: https://github.com/fmaillar/cec-info/compare/v3.3.0...v3.3.1
[3.3.0]: https://github.com/fmaillar/cec-info/releases/tag/v3.3.0
