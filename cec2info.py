#!/usr/bin/env python3
"""
cec2info.py — Convertit le Catéchisme de l'Église catholique (Vatican/IntraText)
en un manuel GNU Texinfo / Info.

Source officielle par défaut :
https://www.vatican.va/archive/FRA0013/_INDEX.HTM

Principe :
- lit le sommaire officiel pour reconstruire l'arbre du CEC ;
- utilise les pages "__P*.HTM", variantes IntraText sans concordances ;
- crée un @node GNU Info par entrée du sommaire ;
- indexe les numéros de paragraphes du CEC ;
- peut appeler makeinfo/texi2dvi pour produire Info, PDF et EPUB 3.

Dépendance Python : BeautifulSoup 4 (paquet Debian python3-bs4).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_INDEX = "https://www.vatican.va/archive/FRA0013/_INDEX.HTM"
USER_AGENT = "cec2info/3.3 (+GNU Info + TeX structured conversion)"
PARA_RE = re.compile(r'^\s*(\d{1,4})(?:\s+|(?=["«]))(.+)$')
SPACE_RE = re.compile(r"[ \t\xa0]+")
MULTIBLANK_RE = re.compile(r"\n[ \t]*\n(?:[ \t]*\n)+")
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class Entry:
    title: str
    href: str | None
    depth: int
    parent: "Entry | None" = None
    children: list["Entry"] = field(default_factory=list)
    node: str = ""
    body: str = ""

    @property
    def up_node(self) -> str:
        return self.parent.node if self.parent else "Top"


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def texi_escape(text: str) -> str:
    return text.replace("@", "@@").replace("{", "@{").replace("}", "@}")


def normalize_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = SPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = MULTIBLANK_RE.sub("\n\n", text)
    return text.strip()


def direct_li_title(li: Tag) -> str:
    clone = BeautifulSoup(str(li), "html.parser")
    root = clone.find("li")
    if root is None:
        return ""
    for nested in root.find_all(["ul", "ol"]):
        nested.decompose()
    return normalize_text(root.get_text(" ", strip=True))


def first_direct_link(li: Tag) -> str | None:
    for child in li.children:
        if isinstance(child, Tag) and child.name == "a" and child.get("href"):
            return str(child["href"])
        if isinstance(child, Tag) and child.name not in {"ul", "ol"}:
            a = child.find("a", href=True)
            if a is not None:
                return str(a["href"])
    return None


def flatten_entries(roots: Iterable[Entry]) -> Iterable[Entry]:
    for entry in roots:
        yield entry
        yield from flatten_entries(entry.children)


def parse_index(data: bytes) -> list[Entry]:
    soup = BeautifulSoup(data, "html.parser")
    lists = soup.find_all(["ul", "ol"])
    if not lists:
        raise RuntimeError("Aucune liste trouvée dans le sommaire Vatican.")

    root_list = max(lists, key=lambda tag: len(tag.find_all("li")))
    roots: list[Entry] = []

    def walk(list_tag: Tag, parent: Entry | None, depth: int) -> None:
        direct_items = list(list_tag.find_all("li", recursive=False))

        # Le sommaire IntraText contient quelques wrappers invalides du type
        # ``ul > ul > li`` (notamment tout le prologue et la fin du CEC).  Ils
        # ne représentent pas un niveau logique supplémentaire : les traverser
        # en conservant le même parent et la même profondeur.
        if not direct_items:
            for nested in list_tag.find_all(["ul", "ol"], recursive=False):
                walk(nested, parent, depth)
            return

        for li in direct_items:
            title = direct_li_title(li)
            if not title:
                continue
            entry = Entry(
                title=title,
                href=first_direct_link(li),
                depth=depth,
                parent=parent,
            )
            if parent is None:
                roots.append(entry)
            else:
                parent.children.append(entry)
            for nested in li.find_all(["ul", "ol"], recursive=False):
                walk(nested, entry, depth + 1)

    walk(root_list, None, 1)
    if len(list(flatten_entries(roots))) < 20:
        raise RuntimeError(
            "Le sommaire détecté semble anormalement petit ; "
            "la structure HTML du Vatican a peut-être changé."
        )
    return roots


def assign_nodes(roots: list[Entry]) -> list[Entry]:
    entries = list(flatten_entries(roots))
    for i, entry in enumerate(entries, 1):
        entry.node = f"CEC-{i:04d}"
    return entries


def clean_page_url(index_url: str, href: str) -> str | None:
    absolute = urllib.parse.urljoin(index_url, href)
    parsed = urllib.parse.urlsplit(absolute)
    name = Path(parsed.path).name

    if re.fullmatch(r"_P[A-Za-z0-9]+\.HTM?", name, re.IGNORECASE):
        clean_name = "_" + name
        path = str(Path(parsed.path).with_name(clean_name))
        return urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
        )
    if re.fullmatch(r"__P[A-Za-z0-9]+\.HTM?", name, re.IGNORECASE):
        return absolute
    return None


def cache_filename(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    name = Path(parsed.path).name or "index.html"
    safe_name = SAFE_FILENAME_RE.sub("_", name)

    # Conserver les noms historiques pour la source officielle afin de ne pas
    # invalider le cache existant. Pour toute autre URL, inclure une empreinte
    # de l'URL complète : deux corpus utilisant les mêmes noms IntraText ne
    # peuvent ainsi plus partager silencieusement les mêmes fichiers.
    default = urllib.parse.urlsplit(DEFAULT_INDEX)
    if (
        parsed.scheme == default.scheme
        and parsed.netloc == default.netloc
        and Path(parsed.path).parent == Path(default.path).parent
        and not parsed.query
    ):
        return safe_name

    normalized = urllib.parse.urlunsplit(parsed._replace(fragment=""))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{digest}-{safe_name}"


def fetch(url: str, cache_dir: Path, refresh: bool, delay: float) -> bytes:
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / cache_filename(url)
    if target.exists() and not refresh:
        return target.read_bytes()

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Échec du téléchargement de {url}: {exc}") from exc

    target.write_bytes(data)
    if delay > 0:
        time.sleep(delay)
    return data


def text_regions_from_html(data: bytes) -> list[str]:
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    marker = "<<<CEC-HR>>>"
    for hr in soup.find_all("hr"):
        hr.replace_with(NavigableString(f"\n\n{marker}\n\n"))
    for br in soup.find_all("br"):
        br.replace_with(NavigableString("\n"))

    for tag in soup.find_all(
        ["p", "div", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "center"]
    ):
        tag.insert_before(NavigableString("\n"))
        tag.insert_after(NavigableString("\n"))

    body = soup.body or soup
    raw = body.get_text(" ", strip=False)
    parts = raw.split(marker)
    return [normalize_text(p) for p in parts if normalize_text(p)]


def boilerplate_penalty(text: str) -> int:
    low = text.casefold()
    penalty = 0
    for phrase in (
        "intratext - lecture du texte",
        "copyright © libreria editrice vaticana",
        "précédent",
        "suivant",
        "aide",
        "le saint-siège",
    ):
        if phrase in low:
            penalty += 5000
    return penalty


def content_score(text: str) -> int:
    numbered = len(re.findall(r"(?m)^\s*\d{1,4}\s+", text))
    return len(text) + numbered * 1000 - boilerplate_penalty(text)


def extract_main_text(data: bytes) -> str:
    regions = text_regions_from_html(data)
    if not regions:
        return ""
    candidate = max(regions, key=content_score)

    lines: list[str] = []
    for line in candidate.splitlines():
        stripped = line.strip()
        folded = stripped.casefold()
        if not stripped:
            lines.append("")
            continue
        if folded in {
            "catéchisme de l'église catholique",
            "intratext - lecture du texte",
            "précédent - suivant",
            "précédent",
            "suivant",
        }:
            continue
        if folded.startswith("copyright © libreria editrice vaticana"):
            continue
        lines.append(stripped)
    return normalize_text("\n".join(lines))


def looks_like_subheading(line: str, next_line: str | None) -> bool:
    if not line or len(line) > 100:
        return False
    if PARA_RE.match(line):
        return False
    if line[-1:] in ".;:!?»":
        return False
    if next_line and PARA_RE.match(next_line):
        return True
    return False


def heading_key(text: str) -> str:
    """Normalise un titre pour comparer les en-têtes Vatican et le sommaire."""
    text = unicodedata.normalize("NFKD", html.unescape(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def entry_path_titles(entry: Entry) -> list[str]:
    titles: list[str] = []
    cur: Entry | None = entry
    while cur is not None:
        titles.append(cur.title)
        cur = cur.parent
    titles.reverse()
    return titles


def is_repeated_path_heading(text: str, path_titles: list[str]) -> bool:
    """Détecte un morceau de titre déjà représenté par la structure du sommaire."""
    key = heading_key(text)
    if not key or len(key) < 3:
        return False
    for title in path_titles:
        tkey = heading_key(title)
        if key == tkey or (len(key) >= 8 and key in tkey) or (len(tkey) >= 8 and tkey in key):
            return True
    return False


def body_to_texinfo(text: str, path_titles: list[str] | None = None) -> str:
    if not text:
        return ""

    paragraphs = [
        normalize_text(p) for p in re.split(r"\n\s*\n", text) if normalize_text(p)
    ]
    out: list[str] = []
    before_first_number = True
    path_titles = path_titles or []

    for para in paragraphs:
        # Les retours simples du vieux HTML IntraText sont de la mise en page,
        # pas des frontières de paragraphe. GNU Info fera lui-même le reflow.
        part = normalize_text(" ".join(para.splitlines()))
        match = PARA_RE.match(part)
        if match:
            number, rest = match.groups()
            # Une référence biblique coupée par la mise en page peut donner un
            # faux paragraphe tel que ``1 P 3, 21`` ou ``2 S 7, 14``.
            if not re.match(r"^[A-ZÀ-ÖØ-Þ]{1,3}\s+\d", rest):
                before_first_number = False
                out.append(f"@cindex {number}")
                out.append(f"@cindex CEC {number}")
                out.append(f"@strong{{{number}}} {texi_escape(rest)}")
                out.append("")
                continue

        escaped = texi_escape(part)
        # Le HTML Vatican répète souvent au début d'une page les titres du
        # chapitre/article courant. Info peut les garder comme contexte ; en
        # sortie TeX ils seraient redondants avec @chapter/@section/... .
        if before_first_number and is_repeated_path_heading(part, path_titles):
            out.extend(["@ifinfo", escaped, "@end ifinfo", ""])
        else:
            out.extend([escaped, ""])

    return "\n".join(out).rstrip()

def sibling_pointers(entry: Entry, roots: list[Entry]) -> tuple[str, str]:
    siblings = entry.parent.children if entry.parent else roots
    idx = siblings.index(entry)
    prev_node = siblings[idx - 1].node if idx > 0 else ""
    next_node = siblings[idx + 1].node if idx + 1 < len(siblings) else ""
    return next_node, prev_node


def menu_label(title: str) -> str:
    # ':' sépare le libellé du nom de nœud dans la syntaxe @menu.
    # On le remplace seulement dans l'affichage du menu.
    return texi_escape(title.replace(":", " —"))


def emit_menu(children: list[Entry]) -> str:
    if not children:
        return ""
    lines = ["@menu"]
    for child in children:
        lines.append(f"* {menu_label(child.title)}: {child.node}.")
    lines.append("@end menu")
    return "\n".join(lines)


PART_RE = re.compile(r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+PARTIE\b", re.IGNORECASE)
SECTION_RE = re.compile(r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+SECTION\b", re.IGNORECASE)
CHAPTER_RE = re.compile(r"^CHAPITRE\b", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^ARTICLE\s+\d+\b", re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"^PARAGRAPHE\s+\d+\b", re.IGNORECASE)
ROMAN_RE = re.compile(r"^[IVXLCDM]+[.]\s+", re.IGNORECASE)


def has_ancestor_matching(entry: Entry, pattern: re.Pattern[str]) -> bool:
    cur = entry.parent
    while cur is not None:
        if pattern.search(cur.title.strip()):
            return True
        cur = cur.parent
    return False


def tex_semantic_level(title: str) -> int | None:
    """Niveau TeX souhaité: 0=part, 1=chapter, ..., 4=subsubsection."""
    title = title.strip()
    if PART_RE.search(title):
        return 0
    if SECTION_RE.search(title):
        return 1
    if CHAPTER_RE.search(title):
        return 2
    if ARTICLE_RE.search(title):
        return 3
    if PARAGRAPH_RE.search(title):
        return 4
    if ROMAN_RE.search(title):
        return 4
    return None


def effective_tex_level(entry: Entry) -> int | None:
    """Niveau Texinfo réellement utilisé pour cette entrée.

    La structure Vatican peut omettre certains niveaux sémantiques.  Le niveau
    effectif est donc calculé récursivement à partir du niveau effectivement
    utilisé par le parent, et non du niveau théorique de son titre.  Cela évite
    les numérotations Texinfo du type 2.0.1.
    """
    title = entry.title.strip()
    folded = heading_key(title)
    desired = tex_semantic_level(title)

    # Titres non numérotés / intertitres : ils ne participent pas à la chaîne
    # de compteurs.
    if folded in {"liste des sigles", "prologue", "en bref"} or desired is None:
        return None

    # @part ne fait pas partie de la numérotation chapter/section/...
    if desired == 0:
        return 0

    # Cherche le premier ancêtre qui possède lui-même un niveau effectif.
    parent = entry.parent
    parent_level: int | None = None
    while parent is not None:
        level = effective_tex_level(parent)
        if level is not None:
            parent_level = level
            break
        parent = parent.parent

    # À la racine, le premier niveau numéroté est toujours @chapter.
    if parent_level is None or parent_level == 0:
        return 1

    # Ne jamais sauter de niveau.  Si le niveau sémantique demandé est plus
    # profond que ce que la chaîne réelle permet, on le remonte juste sous le
    # parent effectif.
    return min(desired, parent_level + 1)


def tex_section_command(entry: Entry) -> str:
    """Commande de sectionnement TeX fondée sur le niveau effectif de l'arbre."""
    title = entry.title.strip()
    escaped = texi_escape(title)
    folded = heading_key(title)

    if folded in {"liste des sigles", "prologue"}:
        return f"@unnumbered {escaped}"
    if folded == "en bref":
        return f"@subsubheading {escaped}"

    level = effective_tex_level(entry)
    if level is None:
        return f"@subsubheading {escaped}"
    if level == 0:
        # @part ne peut pas être associé à un @node et provoque des
        # avertissements dans les sorties HTML/EPUB. @unnumbered conserve un
        # titre de premier niveau sans casser la navigation commune.
        return f"@unnumbered {escaped}"

    commands = {
        1: "chapter",
        2: "section",
        3: "subsection",
        4: "subsubsection",
    }
    return f"@{commands[level]} {escaped}"


def conditional_entry_heading(entry: Entry) -> str:
    """Info utilise @heading ; les autres formats utilisent la vraie sectionisation."""
    return "\n".join(
        [
            "@ifinfo",
            f"@heading {texi_escape(entry.title)}",
            "@end ifinfo",
            "@ifnotinfo",
            tex_section_command(entry),
            "@end ifnotinfo",
        ]
    )


def render_texinfo(roots: list[Entry], source_url: str) -> str:
    entries = list(flatten_entries(roots))
    chunks: list[str] = []
    top_menu = emit_menu(roots)
    if top_menu:
        top_menu = top_menu[:-len("@end menu")] + "* Index::\n@end menu"
    else:
        top_menu = "@menu\n* Index::\n@end menu"

    chunks.append(
        "\\input texinfo\n"
        "@documentencoding UTF-8\n"
        "@documentlanguage fr\n"
        "@setfilename catechisme.info\n"
        "@settitle Catéchisme de l'Église catholique\n\n"
        "@dircategory Religion\n"
        "@direntry\n"
        "* Catéchisme: (catechisme). Catéchisme de l'Église catholique.\n"
        "@end direntry\n\n"
        "@copying\n"
        "Conversion personnelle au format GNU Info à partir du texte publié par\n"
        "le Saint-Siège / Libreria Editrice Vaticana.\n"
        f"Source : @uref{{{texi_escape(source_url)}}}.\n"
        "Le texte source demeure soumis aux droits indiqués par son éditeur.\n"
        "@end copying\n\n"
        "@titlepage\n"
        "@title Catéchisme de l'Église catholique\n"
        "@subtitle Édition GNU Info générée depuis le corpus officiel du Vatican\n"
        "@page\n@vskip 0pt plus 1filll\n@insertcopying\n@end titlepage\n\n"
        "@iftex\n@headings off\n@contents\n@page\n@end iftex\n\n"
        "@node Top\n"
        "@top Catéchisme de l'Église catholique\n\n"
        "Cette édition est générée automatiquement depuis le sommaire et les pages\n"
        "de lecture IntraText du Vatican.\n\n"
        "Navigation : utilisez @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} pour un menu,\n"
        "@kbd{i} pour l'index des numéros du CEC, et @kbd{s} pour une recherche\n"
        "plein texte.\n\n"
        f"{top_menu}\n"
    )

    for entry in entries:
        next_node, prev_node = sibling_pointers(entry, roots)
        chunks.append(
            "\n".join(
                [
                    "",
                    f"@node {entry.node}, {next_node}, {prev_node}, {entry.up_node}",
                    conditional_entry_heading(entry),
                    "",
                    emit_menu(entry.children),
                    "",
                    entry.body,
                    "",
                ]
            )
        )

    chunks.append(
        "\n@node Index\n"
        "@unnumbered Index des paragraphes du CEC\n"
        "@printindex cp\n\n"
        "@bye\n"
    )
    return "\n".join(chunks)

def strip_leading_duplicate_title(text: str, title: str) -> str:
    text = text.lstrip()
    target = normalize_text(title).casefold()
    lines = text.splitlines()
    for n in range(1, min(5, len(lines)) + 1):
        candidate = normalize_text(" ".join(lines[:n])).casefold()
        if candidate == target:
            return "\n".join(lines[n:]).lstrip()
        if not target.startswith(candidate):
            break
    return text


def next_page_url(data: bytes, current_url: str) -> str | None:
    """Retourne la page de lecture indiquée par le lien IntraText « Suivant »."""
    soup = BeautifulSoup(data, "html.parser")
    for link in soup.find_all("a", href=True):
        if normalize_text(link.get_text(" ", strip=True)).casefold() == "suivant":
            return clean_page_url(current_url, str(link["href"]))
    return None


def append_page_body(entry: Entry, data: bytes) -> None:
    text = extract_main_text(data)
    text = strip_leading_duplicate_title(text, entry.title)
    body = body_to_texinfo(text, entry_path_titles(entry))
    if body:
        entry.body = "\n\n".join(part for part in (entry.body, body) if part)

def load_bodies(
    roots: list[Entry],
    index_url: str,
    cache_dir: Path,
    refresh: bool,
    delay: float,
) -> int:
    entries = list(flatten_entries(roots))
    downloadable = [(e, clean_page_url(index_url, e.href)) for e in entries if e.href]
    downloadable = [(e, u) for e, u in downloadable if u]
    entry_positions = {id(entry): i for i, entry in enumerate(entries)}
    url_entries = {url: entry for entry, url in downloadable}
    page_data: dict[str, bytes] = {}

    total = len(downloadable)
    for i, (entry, url) in enumerate(downloadable, 1):
        assert url is not None
        eprint(f"[{i:3d}/{total}] {entry.title}")
        data = fetch(url, cache_dir, refresh=refresh, delay=delay)
        page_data[url] = data
        append_page_body(entry, data)

    # Certaines pages de lecture existent dans la chaîne Précédent/Suivant
    # mais sont absentes du sommaire (_P15 et _P74 dans le corpus français).
    # Suivre ces liens comble les trous sans supposer le système de numérotation
    # interne d'IntraText.
    orphan_urls: set[str] = set()
    for source_entry, source_url in downloadable:
        assert source_url is not None
        current_url = source_url
        current_data = page_data[source_url]
        orphan_chain: list[tuple[str, bytes]] = []
        seen_chain = {source_url}

        while True:
            following = next_page_url(current_data, current_url)
            if following is None or following in seen_chain:
                break
            if following in url_entries:
                break
            if following in orphan_urls:
                break

            eprint(f"[page orpheline] {following}")
            orphan_data = fetch(
                following,
                cache_dir,
                refresh=refresh,
                delay=delay,
            )
            orphan_urls.add(following)
            orphan_chain.append((following, orphan_data))
            seen_chain.add(following)
            current_url, current_data = following, orphan_data

        if not orphan_chain:
            continue

        following = next_page_url(current_data, current_url)
        next_known_entry = url_entries.get(following) if following else None
        source_pos = entry_positions[id(source_entry)]
        next_pos = (
            entry_positions[id(next_known_entry)]
            if next_known_entry is not None
            else len(entries)
        )
        empty_entries = [
            entry
            for entry in entries[source_pos + 1 : next_pos]
            if entry.href is None and not entry.body
        ]

        for _, orphan_data in orphan_chain:
            # Une entrée sans lien située exactement dans le trou reçoit la
            # page (cas de la deuxième section, § 185). Sinon la page complète
            # logiquement l'entrée précédente (cas de l'EN BREF, § 2075).
            target = empty_entries.pop(0) if empty_entries else source_entry
            append_page_body(target, orphan_data)

    return len(orphan_urls)


def paragraph_index_numbers(texi: str) -> list[int]:
    return [
        int(number)
        for number in re.findall(r"(?m)^@cindex (\d+)$", texi)
    ]


def validate_paragraph_indexes(texi: str, expected_last: int) -> None:
    if expected_last <= 0:
        return

    numbers = paragraph_index_numbers(texi)
    counts: dict[int, int] = {}
    for number in numbers:
        counts[number] = counts.get(number, 0) + 1

    missing = [number for number in range(1, expected_last + 1) if number not in counts]
    duplicates = [number for number, count in counts.items() if count > 1]
    unexpected = [number for number in counts if not 1 <= number <= expected_last]
    if missing or duplicates or unexpected:
        details = []
        if missing:
            details.append(f"absents: {missing}")
        if duplicates:
            details.append(f"doublons: {duplicates}")
        if unexpected:
            details.append(f"hors plage: {unexpected}")
        raise RuntimeError("Index des paragraphes incomplet ou invalide (" + "; ".join(details) + ")")

    eprint(f"Paragraphes 1 à {expected_last} présents une fois chacun.")


def build_generation_report(
    *,
    source_url: str,
    entry_count: int,
    linked_pages: int,
    orphan_pages: int,
    texi: str,
    outputs: dict[str, Path],
) -> dict[str, object]:
    numbers = paragraph_index_numbers(texi)
    unique_numbers = set(numbers)
    output_details: dict[str, object] = {}
    for name, path in outputs.items():
        if path.exists():
            output_details[name] = {
                "path": str(path),
                "bytes": path.stat().st_size,
            }

    return {
        "source_url": source_url,
        "entries": entry_count,
        "pages": {
            "linked": linked_pages,
            "orphan": orphan_pages,
            "total": linked_pages + orphan_pages,
        },
        "paragraphs": {
            "count": len(numbers),
            "unique": len(unique_numbers),
            "first": min(unique_numbers) if unique_numbers else None,
            "last": max(unique_numbers) if unique_numbers else None,
        },
        "outputs": output_details,
    }


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("o", "Kio", "Mio", "Gio"):
        if value < 1024 or unit == "Gio":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def emit_generation_report(
    report: dict[str, object],
    json_path: Path | None = None,
) -> None:
    pages = report["pages"]
    paragraphs = report["paragraphs"]
    outputs = report["outputs"]
    assert isinstance(pages, dict)
    assert isinstance(paragraphs, dict)
    assert isinstance(outputs, dict)

    eprint("\nRapport de génération")
    eprint(f"  Entrées du sommaire : {report['entries']}")
    eprint(
        "  Pages HTML          : "
        f"{pages['total']} ({pages['linked']} liées, {pages['orphan']} orphelines)"
    )
    eprint(
        "  Paragraphes        : "
        f"{paragraphs['unique']} uniques, plage {paragraphs['first']}–{paragraphs['last']}"
    )
    for name, details in outputs.items():
        assert isinstance(details, dict)
        eprint(
            f"  {str(name).upper():<18}: "
            f"{human_size(int(details['bytes']))} — {details['path']}"
        )

    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        eprint(f"  Rapport JSON        : {json_path}")


def compile_info(texi_path: Path, info_path: Path) -> None:
    makeinfo = shutil.which("makeinfo")
    if makeinfo is None:
        raise RuntimeError("makeinfo est introuvable. Installez le paquet Debian 'texinfo'.")
    info_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [makeinfo, "--no-split", "--output", str(info_path), str(texi_path)],
        check=True,
    )


def compile_pdf(texi_path: Path, pdf_path: Path) -> None:
    texi2dvi = shutil.which("texi2dvi")
    if texi2dvi is None:
        raise RuntimeError("texi2dvi est introuvable. Installez Texinfo/TeX.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            texi2dvi,
            "--batch",
            "--build=clean",
            "--dvipdf",
            "--output",
            str(pdf_path.resolve()),
            texi_path.name,
        ],
        check=True,
        cwd=texi_path.parent,
    )


def compile_epub(texi_path: Path, epub_path: Path) -> None:
    makeinfo = shutil.which("makeinfo")
    if makeinfo is None:
        raise RuntimeError("makeinfo est introuvable. Installez le paquet Debian 'texinfo'.")
    epub_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [makeinfo, "--epub3", "--output", str(epub_path), str(texi_path)],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convertit le Catéchisme officiel du Vatican en GNU Texinfo/Info."
    )
    parser.add_argument("--index-url", default=DEFAULT_INDEX)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cec-cache"))
    parser.add_argument("-o", "--output", type=Path, default=Path("catechisme.texi"))
    parser.add_argument(
        "--info",
        type=Path,
        default=Path("catechisme.info"),
        help="fichier Info produit avec --compile",
    )
    parser.add_argument("--compile", action="store_true", help="appelle makeinfo après génération du .texi")
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="appelle texi2dvi en mode PDF après génération du .texi",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=Path("catechisme.pdf"),
        help="fichier PDF produit avec --pdf",
    )
    parser.add_argument("--epub", action="store_true", help="appelle makeinfo pour générer un EPUB 3")
    parser.add_argument(
        "--epub-output",
        type=Path,
        default=Path("catechisme.epub"),
        help="fichier EPUB produit avec --epub",
    )
    parser.add_argument("--refresh", action="store_true", help="retélécharge les pages même si elles sont en cache")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="pause entre téléchargements (secondes, défaut: 0.05)",
    )
    parser.add_argument(
        "--expected-last-paragraph",
        type=int,
        default=2865,
        help="dernier paragraphe attendu pour la validation (0 pour désactiver)",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="écrit aussi le rapport de génération au format JSON",
    )
    args = parser.parse_args()

    eprint(f"Téléchargement du sommaire : {args.index_url}")
    index_data = fetch(args.index_url, args.cache_dir, refresh=args.refresh, delay=args.delay)
    roots = parse_index(index_data)
    entries = assign_nodes(roots)
    eprint(f"{len(entries)} entrées de sommaire détectées.")
    linked_pages = sum(
        clean_page_url(args.index_url, entry.href) is not None
        for entry in entries
        if entry.href
    )
    orphan_pages = load_bodies(
        roots,
        args.index_url,
        args.cache_dir,
        refresh=args.refresh,
        delay=args.delay,
    )

    texi = render_texinfo(roots, args.index_url)
    validate_paragraph_indexes(texi, args.expected_last_paragraph)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(texi, encoding="utf-8")
    eprint(f"Texinfo écrit : {args.output}")
    outputs = {"texinfo": args.output}

    if args.compile:
        compile_info(args.output, args.info)
        eprint(f"Info écrit : {args.info}")
        outputs["info"] = args.info

    if args.pdf:
        compile_pdf(args.output, args.pdf_output)
        eprint(f"PDF écrit : {args.pdf_output}")
        outputs["pdf"] = args.pdf_output

    if args.epub:
        compile_epub(args.output, args.epub_output)
        eprint(f"EPUB écrit : {args.epub_output}")
        outputs["epub"] = args.epub_output

    report = build_generation_report(
        source_url=args.index_url,
        entry_count=len(entries),
        linked_pages=linked_pages,
        orphan_pages=orphan_pages,
        texi=texi,
        outputs=outputs,
    )
    emit_generation_report(report, args.report_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
