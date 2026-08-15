"""Texinfo transformation, validation, reporting, and output compilation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from cec2info_model import Entry, flatten_entries, heading_key, normalize_text

PARA_RE = re.compile(r'^\s*(\d{1,4})(?:\s+|(?=["«]))(.+)$')
PART_RE = re.compile(
    r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+PARTIE\b", re.IGNORECASE
)
SECTION_RE = re.compile(
    r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+SECTION\b", re.IGNORECASE
)
CHAPTER_RE = re.compile(r"^CHAPITRE\b", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^ARTICLE\s+\d+\b", re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"^PARAGRAPHE\s+\d+\b", re.IGNORECASE)
ROMAN_RE = re.compile(r"^[IVXLCDM]+[.]\s+", re.IGNORECASE)


def eprint(*args: object) -> None:
    import sys

    print(*args, file=sys.stderr)


def texi_escape(text: str) -> str:
    return text.replace("@", "@@").replace("{", "@{").replace("}", "@}")


def is_repeated_path_heading(text: str, path_titles: list[str]) -> bool:
    """Detect a title fragment already represented by the table-of-contents tree."""
    key = heading_key(text)
    if not key or len(key) < 3:
        return False
    for title in path_titles:
        title_key = heading_key(title)
        if (
            key == title_key
            or (len(key) >= 8 and key in title_key)
            or (len(title_key) >= 8 and title_key in key)
        ):
            return True
    return False


def body_to_texinfo(text: str, path_titles: list[str] | None = None) -> str:
    if not text:
        return ""

    paragraphs = [
        normalize_text(part)
        for part in re.split(r"\n\s*\n", text)
        if normalize_text(part)
    ]
    output: list[str] = []
    before_first_number = True
    path_titles = path_titles or []

    for paragraph in paragraphs:
        part = normalize_text(" ".join(paragraph.splitlines()))
        match = PARA_RE.match(part)
        if match:
            number, rest = match.groups()
            # A Bible reference split by the page layout can look like a false
            # paragraph, such as ``1 P 3, 21`` or ``2 S 7, 14``.
            if not re.match(r"^[A-ZÀ-ÖØ-Þ]{1,3}\s+\d", rest):
                before_first_number = False
                output.append(f"@cindex {number}")
                output.append(f"@cindex CEC {number}")
                output.append(f"@strong{{{number}}} {texi_escape(rest)}")
                output.append("")
                continue

        escaped = texi_escape(part)
        if before_first_number and is_repeated_path_heading(part, path_titles):
            output.extend(["@ifinfo", escaped, "@end ifinfo", ""])
        else:
            output.extend([escaped, ""])

    return "\n".join(output).rstrip()


def sibling_pointers(entry: Entry, roots: list[Entry]) -> tuple[str, str]:
    siblings = entry.parent.children if entry.parent else roots
    index = siblings.index(entry)
    previous_node = siblings[index - 1].node if index > 0 else ""
    next_node = siblings[index + 1].node if index + 1 < len(siblings) else ""
    return next_node, previous_node


def menu_label(title: str) -> str:
    return texi_escape(title.replace(":", " —"))


def emit_menu(children: list[Entry]) -> str:
    if not children:
        return ""
    lines = ["@menu"]
    for child in children:
        lines.append(f"* {menu_label(child.title)}: {child.node}.")
    lines.append("@end menu")
    return "\n".join(lines)


def tex_semantic_level(title: str) -> int | None:
    """Return the desired TeX level: 0=part, 1=chapter, ..., 4=subsubsection."""
    title = title.strip()
    if PART_RE.search(title):
        return 0
    if SECTION_RE.search(title):
        return 1
    if CHAPTER_RE.search(title):
        return 2
    if ARTICLE_RE.search(title):
        return 3
    if PARAGRAPH_RE.search(title) or ROMAN_RE.search(title):
        return 4
    return None


def effective_tex_level(entry: Entry) -> int | None:
    """Compute a usable Texinfo level without gaps in the actual tree."""
    folded = heading_key(entry.title.strip())
    desired = tex_semantic_level(entry.title.strip())
    if folded in {"liste des sigles", "prologue", "en bref"} or desired is None:
        return None
    if desired == 0:
        return 0

    parent = entry.parent
    parent_level: int | None = None
    while parent is not None:
        level = effective_tex_level(parent)
        if level is not None:
            parent_level = level
            break
        parent = parent.parent

    if parent_level is None or parent_level == 0:
        return 1
    return min(desired, parent_level + 1)


def tex_section_command(entry: Entry) -> str:
    """Return the sectioning command derived from the effective tree."""
    escaped = texi_escape(entry.title.strip())
    folded = heading_key(entry.title.strip())
    if folded in {"liste des sigles", "prologue"}:
        return f"@unnumbered {escaped}"
    if folded == "en bref":
        return f"@subsubheading {escaped}"

    level = effective_tex_level(entry)
    if level is None:
        return f"@subsubheading {escaped}"
    if level == 0:
        return f"@unnumbered {escaped}"
    commands = {1: "chapter", 2: "section", 3: "subsection", 4: "subsubsection"}
    return f"@{commands[level]} {escaped}"


def conditional_entry_heading(entry: Entry) -> str:
    """Use @heading for Info and sectioning commands for other formats."""
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
        top_menu = top_menu[: -len("@end menu")] + "* Index::\n@end menu"
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
        next_node, previous_node = sibling_pointers(entry, roots)
        chunks.append(
            "\n".join(
                [
                    "",
                    f"@node {entry.node}, {next_node}, {previous_node}, {entry.up_node}",
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


def paragraph_index_numbers(texi: str) -> list[int]:
    return [int(number) for number in re.findall(r"(?m)^@cindex (\d+)$", texi)]


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
        raise RuntimeError(
            "Index des paragraphes incomplet ou invalide (" + "; ".join(details) + ")"
        )
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
            output_details[name] = {"path": str(path), "bytes": path.stat().st_size}
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
    if shutil.which("makeinfo") is None:
        raise RuntimeError("makeinfo est introuvable. Installez le paquet Debian 'texinfo'.")
    info_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["makeinfo", "--no-split", "--output", str(info_path), str(texi_path)],
        check=True,
    )


def compile_pdf(texi_path: Path, pdf_path: Path) -> None:
    if shutil.which("texi2dvi") is None:
        raise RuntimeError("texi2dvi est introuvable. Installez Texinfo/TeX.")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "texi2dvi",
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
    if shutil.which("makeinfo") is None:
        raise RuntimeError("makeinfo est introuvable. Installez le paquet Debian 'texinfo'.")
    epub_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["makeinfo", "--epub3", "--output", str(epub_path), str(texi_path)],
        check=True,
    )
