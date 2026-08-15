#!/usr/bin/env python3
"""Interface publique et ligne de commande de cec2info.

Les responsabilités internes sont réparties entre ``cec2info_network`` pour
le téléchargement, ``cec2info_parser`` pour l'analyse HTML et
``cec2info_output`` pour la génération. Les imports historiques restent
disponibles depuis ce module pour préserver la compatibilité.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cec2info_model import (
    Entry,
    assign_nodes,
    entry_path_titles,
    flatten_entries,
    heading_key,
    normalize_text,
)
from cec2info_network import (
    DEFAULT_INDEX,
    USER_AGENT,
    VERSION,
    cache_filename,
    clean_page_url,
    fetch,
    write_cache_atomically,
)
from cec2info_output import (
    body_to_texinfo,
    build_generation_report,
    compile_epub,
    compile_info,
    compile_pdf,
    conditional_entry_heading,
    effective_tex_level,
    emit_generation_report,
    emit_menu,
    human_size,
    is_repeated_path_heading,
    menu_label,
    paragraph_index_numbers,
    render_texinfo,
    sibling_pointers,
    tex_section_command,
    tex_semantic_level,
    texi_escape,
    validate_paragraph_indexes,
)
from cec2info_parser import (
    append_page_body,
    assign_orphan_chain,
    boilerplate_penalty,
    content_score,
    direct_li_title,
    discover_orphan_chain,
    download_linked_pages,
    downloadable_entries,
    extract_main_text,
    first_direct_link,
    load_bodies,
    next_page_url,
    parse_index,
    strip_leading_duplicate_title,
    text_regions_from_html,
)

# Ces noms constituent l'API historique du module monolithique.
__all__ = [
    "DEFAULT_INDEX",
    "USER_AGENT",
    "VERSION",
    "Entry",
    "append_page_body",
    "assign_nodes",
    "assign_orphan_chain",
    "body_to_texinfo",
    "boilerplate_penalty",
    "build_generation_report",
    "build_parser",
    "cache_filename",
    "clean_page_url",
    "compile_epub",
    "compile_info",
    "compile_pdf",
    "conditional_entry_heading",
    "content_score",
    "direct_li_title",
    "discover_orphan_chain",
    "download_linked_pages",
    "downloadable_entries",
    "effective_tex_level",
    "emit_generation_report",
    "emit_menu",
    "entry_path_titles",
    "extract_main_text",
    "fetch",
    "first_direct_link",
    "flatten_entries",
    "heading_key",
    "human_size",
    "is_repeated_path_heading",
    "load_bodies",
    "main",
    "menu_label",
    "next_page_url",
    "nonnegative_float",
    "nonnegative_int",
    "normalize_text",
    "paragraph_index_numbers",
    "parse_index",
    "render_texinfo",
    "run",
    "sibling_pointers",
    "strip_leading_duplicate_title",
    "tex_section_command",
    "tex_semantic_level",
    "texi_escape",
    "text_regions_from_html",
    "validate_paragraph_indexes",
    "write_cache_atomically",
]


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def nonnegative_float(value: str) -> float:
    result = float(value)
    if result < 0:
        raise argparse.ArgumentTypeError("la valeur doit être positive ou nulle")
    return result


def nonnegative_int(value: str) -> int:
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError("la valeur doit être positive ou nulle")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convertit le Catéchisme officiel du Vatican en GNU Texinfo/Info."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--index-url", default=DEFAULT_INDEX)
    parser.add_argument("--cache-dir", type=Path, default=Path(".cec-cache"))
    parser.add_argument("-o", "--output", type=Path, default=Path("catechisme.texi"))
    parser.add_argument(
        "--info",
        type=Path,
        default=Path("catechisme.info"),
        help="fichier Info produit avec --compile",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="appelle makeinfo après génération du .texi",
    )
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
    parser.add_argument(
        "--epub",
        action="store_true",
        help="appelle makeinfo pour générer un EPUB 3",
    )
    parser.add_argument(
        "--epub-output",
        type=Path,
        default=Path("catechisme.epub"),
        help="fichier EPUB produit avec --epub",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="retélécharge les pages même si elles sont en cache",
    )
    parser.add_argument(
        "--delay",
        type=nonnegative_float,
        default=0.05,
        help="pause entre téléchargements (secondes, défaut: 0.05)",
    )
    parser.add_argument(
        "--expected-last-paragraph",
        type=nonnegative_int,
        default=2865,
        help="dernier paragraphe attendu pour la validation (0 pour désactiver)",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        help="écrit aussi le rapport de génération au format JSON",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    eprint(f"Téléchargement du sommaire : {args.index_url}")
    index_data = fetch(
        args.index_url,
        args.cache_dir,
        refresh=args.refresh,
        delay=args.delay,
    )
    roots = parse_index(index_data)
    entries = assign_nodes(roots)
    eprint(f"{len(entries)} entrées de sommaire détectées.")
    linked_pages = len(downloadable_entries(entries, args.index_url))
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        eprint(f"Erreur: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
