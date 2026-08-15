# Contribuer à cec2info

Merci de contribuer à `cec2info`. Les corrections ciblées, accompagnées de
tests et compatibles avec Python 3.10 ou ultérieur, sont privilégiées.

## Préparer l'environnement

```sh
git clone https://github.com/fmaillar/cec-info.git
cd cec-info
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Sous Windows PowerShell, activez l'environnement avec :

```powershell
.venv\Scripts\Activate.ps1
```

Les outils Texinfo et TeX sont facultatifs pour les tests Python, mais requis
pour valider réellement les sorties Info, PDF et EPUB.

## Proposer une modification

1. Ouvrez d'abord une issue pour une évolution importante.
2. Limitez chaque commit à une modification cohérente.
3. Ajoutez ou adaptez les tests correspondant au comportement modifié.
4. Exécutez les contrôles locaux :

   ```sh
   make check
   python -m build
   ```

5. Ouvrez une pull request en décrivant le problème, la solution et les
   vérifications effectuées.

Ne commitez ni le cache du Vatican, ni les documents générés, ni les
environnements virtuels.
En contribuant, vous acceptez que votre contribution soit distribuée sous la
licence GPL-3.0-or-later du projet.
