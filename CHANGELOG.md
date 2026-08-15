# Journal des modifications

Les changements notables du projet sont documentés dans ce fichier.

Le format suit les principes de *Keep a Changelog* et les versions suivent le
versionnage sémantique.

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

[3.3.0]: https://github.com/fmaillar/cec-info/releases/tag/v3.3.0
