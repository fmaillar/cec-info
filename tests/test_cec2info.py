import argparse
import contextlib
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from bs4 import BeautifulSoup

from cec2info import (
    DEFAULT_INDEX,
    USER_AGENT,
    VERSION,
    Entry,
    append_page_body,
    assign_nodes,
    body_to_texinfo,
    build_generation_report,
    build_parser,
    cache_filename,
    clean_page_url,
    compile_epub,
    compile_info,
    compile_pdf,
    direct_li_title,
    emit_generation_report,
    extract_main_text,
    fetch,
    first_direct_link,
    flatten_entries,
    human_size,
    is_repeated_path_heading,
    load_bodies,
    main,
    next_page_url,
    nonnegative_float,
    nonnegative_int,
    parse_index,
    render_texinfo,
    run,
    strip_leading_duplicate_title,
    tex_section_command,
    validate_paragraph_indexes,
)


class ParseIndexTests(unittest.TestCase):
    def test_list_helpers_handle_wrappers_and_missing_li(self) -> None:
        soup = BeautifulSoup(
            '<li><span><a href="__P1.HTM">Titre</a></span><ul><li>Enfant</li></ul></li>',
            "html.parser",
        )
        li = soup.find("li")
        assert li is not None

        self.assertEqual(direct_li_title(li), "Titre")
        self.assertEqual(first_direct_link(li), "__P1.HTM")
        div = BeautifulSoup("<div>Sans liste</div>", "html.parser").find("div")
        assert div is not None
        self.assertEqual(direct_li_title(div), "")

    def test_missing_list_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Aucune liste"):
            parse_index(b"<html><body>Sommaire absent</body></html>")

    def test_suspiciously_small_index_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "anormalement petit"):
            parse_index("<ul><li>Une seule entrée</li></ul>".encode())

    def test_transparent_nested_list_wrapper(self) -> None:
        data = b"""
        <html><body><ul>
          <li><a href="__P1.HTM">Prologue</a><ul><ul>
            <li><a href="__P2.HTM">Section enfant</a></li>
          </ul></ul></li>
          <li><a href="__P3.HTM">Partie</a></li>
          <li>3</li><li>4</li><li>5</li><li>6</li><li>7</li><li>8</li>
          <li>9</li><li>10</li><li>11</li><li>12</li><li>13</li><li>14</li>
          <li>15</li><li>16</li><li>17</li><li>18</li><li>19</li><li>20</li>
        </ul></body></html>
        """
        roots = parse_index(data)
        entries = list(flatten_entries(roots))
        self.assertEqual(entries[1].title, "Section enfant")
        self.assertIs(entries[1].parent, entries[0])
        self.assertEqual(entries[1].depth, 2)

    def test_empty_li_wrapper_keeps_nested_entries(self) -> None:
        filler = "".join(f"<li>Entrée {i}</li>" for i in range(2, 21))
        data = (
            "<ul><li><ul><li><a href='__P1.HTM'>Entrée 1</a></li></ul></li>"
            f"{filler}</ul>"
        ).encode()

        entries = list(flatten_entries(parse_index(data)))

        self.assertEqual(len(entries), 20)
        self.assertEqual(entries[0].title, "Entrée 1")
        self.assertEqual(entries[0].depth, 1)


class TexinfoConversionTests(unittest.TestCase):
    def test_empty_body_and_empty_document_are_supported(self) -> None:
        self.assertEqual(body_to_texinfo(""), "")
        self.assertEqual(extract_main_text(b""), "")
        self.assertIn("@menu\n* Index::", render_texinfo([], "https://example.test"))

    def test_real_paragraph_is_indexed(self) -> None:
        result = body_to_texinfo(
            '1 Dieu nous appelle.\n\n26" Nous croyons. "'
        )
        self.assertIn("@cindex 1", result)
        self.assertIn("@cindex 26", result)

    def test_split_biblical_reference_is_not_indexed(self) -> None:
        result = body_to_texinfo("128 Un texte (cf.\n\n1 P 3, 21).")
        self.assertIn("@cindex 128", result)
        self.assertNotIn("@cindex 1\n", result)
        self.assertIn("1 P 3, 21", result)

    def test_boilerplate_is_removed_from_main_text(self) -> None:
        data = b"""
        <html><body>
          <script>contenu ind\xc3\xa9sirable</script>
          <div>IntraText - Lecture du texte<br>Pr\xc3\xa9c\xc3\xa9dent - Suivant</div>
          <hr>
          <div><h2>Titre utile</h2><p>1 Contenu principal.</p></div>
          <hr>
          <div>Copyright \xc2\xa9 Libreria Editrice Vaticana</div>
        </body></html>
        """

        text = extract_main_text(data)

        self.assertIn("1 Contenu principal.", text)
        self.assertNotIn("IntraText", text)
        self.assertNotIn("Copyright", text)

    def test_exact_navigation_lines_are_removed(self) -> None:
        data = """
        <body>
          <p>Catéchisme de l'Église catholique</p>
          <p>Précédent</p><p>Suivant</p>
          <p>Copyright © Libreria Editrice Vaticana 2026</p>
          <p>1 Texte conservé.</p>
        </body>
        """.encode()

        self.assertEqual(extract_main_text(data), "1 Texte conservé.")

    def test_repeated_heading_is_limited_to_info_output(self) -> None:
        result = body_to_texinfo(
            "ARTICLE 1\n\n1 Texte avec @ et {accolades}.",
            ["ARTICLE 1"],
        )

        self.assertIn("@ifinfo\nARTICLE 1\n@end ifinfo", result)
        self.assertIn("Texte avec @@ et @{accolades@}", result)

    def test_heading_comparison_handles_short_and_partial_titles(self) -> None:
        self.assertFalse(is_repeated_path_heading("I", ["Introduction"]))
        self.assertTrue(
            is_repeated_path_heading(
                "La transmission de la foi",
                ["Article 2 — La transmission de la foi divine"],
            )
        )
        self.assertFalse(is_repeated_path_heading("Titre distinct", ["Autre titre"]))

    def test_semantic_levels_do_not_skip_texinfo_levels(self) -> None:
        part = Entry(title="PREMIERE PARTIE", href=None, depth=1)
        section = Entry(
            title="PREMIERE SECTION",
            href=None,
            depth=2,
            parent=part,
        )
        article = Entry(title="ARTICLE 1", href=None, depth=3, parent=section)

        self.assertTrue(tex_section_command(part).startswith("@unnumbered"))
        self.assertTrue(tex_section_command(section).startswith("@chapter"))
        self.assertTrue(tex_section_command(article).startswith("@section"))

    def test_special_and_deep_semantic_headings(self) -> None:
        chapter = Entry(title="CHAPITRE PREMIER", href=None, depth=1)
        paragraph = Entry(
            title="PARAGRAPHE 1",
            href=None,
            depth=2,
            parent=chapter,
        )
        roman = Entry(title="IV. Conclusion", href=None, depth=3, parent=paragraph)

        self.assertTrue(tex_section_command(chapter).startswith("@chapter"))
        self.assertTrue(tex_section_command(paragraph).startswith("@section"))
        self.assertTrue(tex_section_command(roman).startswith("@subsection"))
        self.assertEqual(tex_section_command(Entry("EN BREF", None, 1)), "@subsubheading EN BREF")
        self.assertEqual(
            tex_section_command(Entry("LISTE DES SIGLES", None, 1)),
            "@unnumbered LISTE DES SIGLES",
        )

        intertitle = Entry("Intertitre libre", None, 2, parent=chapter)
        nested_article = Entry("ARTICLE 2", None, 3, parent=intertitle)
        self.assertTrue(tex_section_command(nested_article).startswith("@section"))

    def test_duplicate_title_stripping_handles_match_and_mismatch(self) -> None:
        self.assertEqual(
            strip_leading_duplicate_title("Titre sur\ndeux lignes\n1 Corps", "Titre sur deux lignes"),
            "1 Corps",
        )
        self.assertEqual(
            strip_leading_duplicate_title("Autre titre\n1 Corps", "Titre attendu"),
            "Autre titre\n1 Corps",
        )


class NavigationAndValidationTests(unittest.TestCase):
    def test_clean_page_url_rejects_non_reading_page(self) -> None:
        index = "https://example.test/book/_INDEX.HTM"
        self.assertEqual(
            clean_page_url(index, "_P12.HTM"),
            "https://example.test/book/__P12.HTM",
        )
        self.assertIsNone(clean_page_url(index, "notes.html"))

    def test_next_page_url_finds_orphan_page(self) -> None:
        data = '<a href="__P15.HTM">Suivant</a>'.encode()
        self.assertEqual(
            next_page_url(data, "https://example.test/book/__P14.HTM"),
            "https://example.test/book/__P15.HTM",
        )
        self.assertIsNone(next_page_url(b"<p>Fin</p>", "https://example.test/book/__P15.HTM"))

    def test_cache_is_namespaced_outside_official_source(self) -> None:
        first = cache_filename("https://one.test/book/__P1.HTM")
        second = cache_filename("https://two.test/book/__P1.HTM")
        self.assertNotEqual(first, second)
        self.assertTrue(first.endswith("-__P1.HTM"))

    def test_official_cache_keeps_readable_filename(self) -> None:
        self.assertEqual(
            cache_filename("https://www.vatican.va/archive/FRA0013/__P1.HTM"),
            "__P1.HTM",
        )
        self.assertEqual(cache_filename(DEFAULT_INDEX), "_INDEX.HTM")

    def test_validation_rejects_missing_and_duplicate_numbers(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "absents.*doublons"):
            validate_paragraph_indexes(
                "@cindex 1\n@cindex 1\n@cindex 3\n",
                expected_last=3,
            )

    def test_validation_reports_out_of_range_and_can_be_disabled(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "hors plage"):
            validate_paragraph_indexes(
                "@cindex 1\n@cindex 2\n@cindex 3\n",
                expected_last=2,
            )
        validate_paragraph_indexes("texte sans index", expected_last=0)

    def test_empty_page_does_not_modify_existing_body(self) -> None:
        entry = Entry(title="Titre", href=None, depth=1, body="contenu existant")
        append_page_body(entry, b"")
        self.assertEqual(entry.body, "contenu existant")

    def test_orphan_page_is_assigned_to_unlinked_entry(self) -> None:
        source = Entry(title="Source", href="__P1.HTM", depth=1)
        orphan_entry = Entry(title="Section orpheline", href=None, depth=1)
        following = Entry(title="Suite", href="__P3.HTM", depth=1)
        roots = [source, orphan_entry, following]
        pages = {
            "https://example.test/book/__P1.HTM": (
                '<body>1 Début.<a href="__P2.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P2.HTM": (
                '<body>2 Milieu.<a href="__P3.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P3.HTM": (
                "<body>3 Fin.</body>".encode()
            ),
        }

        with patch(
            "cec2info_parser.fetch",
            side_effect=lambda url, *_args, **_kwargs: pages[url],
        ):
            orphan_count = load_bodies(
                roots,
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 1)
        self.assertIn("@cindex 1", source.body)
        self.assertIn("@cindex 2", orphan_entry.body)
        self.assertIn("@cindex 3", following.body)

    def test_duplicate_page_url_is_downloaded_and_assigned_once(self) -> None:
        first = Entry(title="Première entrée", href="__P1.HTM", depth=1)
        duplicate = Entry(title="Entrée dupliquée", href="__P1.HTM", depth=1)
        page = b"<body>1 Contenu unique.</body>"

        with patch("cec2info_parser.fetch", return_value=page) as mocked_fetch:
            orphan_count = load_bodies(
                [first, duplicate],
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 0)
        mocked_fetch.assert_called_once()
        self.assertIn("@cindex 1", first.body)
        self.assertEqual(duplicate.body, "")

    def test_orphan_cycle_stops_without_duplicate_download(self) -> None:
        source = Entry(title="Source", href="__P1.HTM", depth=1)
        pages = {
            "https://example.test/book/__P1.HTM": (
                '<body>1 Début.<a href="__P2.HTM">Suivant</a></body>'.encode()
            ),
            "https://example.test/book/__P2.HTM": (
                '<body>2 Suite.<a href="__P1.HTM">Suivant</a></body>'.encode()
            ),
        }

        with patch(
            "cec2info_parser.fetch",
            side_effect=lambda url, *_args, **_kwargs: pages[url],
        ) as mocked_fetch:
            orphan_count = load_bodies(
                [source],
                "https://example.test/book/_INDEX.HTM",
                Path("unused-cache"),
                refresh=False,
                delay=0,
            )

        self.assertEqual(orphan_count, 1)
        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(source.body.count("@cindex 1"), 1)
        self.assertEqual(source.body.count("@cindex 2"), 1)


class FetchTests(unittest.TestCase):
    url = "https://example.test/book/__P1.HTM"

    def test_nonempty_cache_avoids_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"cached")

            with patch("cec2info_network.urllib.request.urlopen") as urlopen:
                data = fetch(self.url, cache_dir, refresh=False, delay=0)

            self.assertEqual(data, b"cached")
            urlopen.assert_not_called()

    def test_empty_cache_is_replaced_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"")

            with patch(
                "cec2info_network.urllib.request.urlopen",
                return_value=io.BytesIO(b"<html>contenu</html>"),
            ):
                data = fetch(self.url, cache_dir, refresh=False, delay=0)

            self.assertEqual(data, b"<html>contenu</html>")
            self.assertEqual(target.read_bytes(), data)
            self.assertFalse(any(cache_dir.glob(f".{target.name}.*")))

    def test_temporary_error_is_retried_with_backoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "cec2info_network.urllib.request.urlopen",
                    side_effect=[URLError("temporaire"), io.BytesIO(b"ok")],
                ) as urlopen,
                patch("cec2info_network.time.sleep") as sleep,
            ):
                data = fetch(
                    self.url,
                    Path(directory),
                    refresh=True,
                    delay=0,
                    retries=1,
                    retry_backoff=0.25,
                )

            self.assertEqual(data, b"ok")
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(0.25)

    def test_retryable_http_error_then_success(self) -> None:
        error = HTTPError(self.url, 503, "indisponible", {}, None)
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "cec2info_network.urllib.request.urlopen",
                    side_effect=[error, io.BytesIO(b"ok")],
                ),
                patch("cec2info_network.time.sleep") as sleep,
            ):
                data = fetch(
                    self.url,
                    Path(directory),
                    refresh=True,
                    delay=0.1,
                    retries=1,
                    retry_backoff=0,
                )

            self.assertEqual(data, b"ok")
            sleep.assert_called_once_with(0.1)

    def test_permanent_http_error_is_not_retried(self) -> None:
        error = HTTPError(self.url, 404, "introuvable", {}, None)
        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "cec2info_network.urllib.request.urlopen",
                side_effect=error,
            ) as urlopen:
                with self.assertRaisesRegex(RuntimeError, "1 tentative"):
                    fetch(
                        self.url,
                        Path(directory),
                        refresh=True,
                        delay=0,
                        retries=3,
                    )

            urlopen.assert_called_once()

    def test_failed_refresh_preserves_previous_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            target = cache_dir / cache_filename(self.url)
            target.write_bytes(b"ancien contenu")

            with patch(
                "cec2info_network.urllib.request.urlopen",
                return_value=io.BytesIO(b""),
            ):
                with self.assertRaisesRegex(RuntimeError, "réponse vide"):
                    fetch(
                        self.url,
                        cache_dir,
                        refresh=True,
                        delay=0,
                        retries=0,
                    )

            self.assertEqual(target.read_bytes(), b"ancien contenu")

    def test_invalid_retry_parameters_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache_dir = Path(directory)
            with self.assertRaisesRegex(ValueError, "delay"):
                fetch(self.url, cache_dir, False, -1)
            with self.assertRaisesRegex(ValueError, "timeout"):
                fetch(self.url, cache_dir, False, 0, timeout=0)
            with self.assertRaisesRegex(ValueError, "retries"):
                fetch(self.url, cache_dir, False, 0, retries=-1)
            with self.assertRaisesRegex(ValueError, "retry_backoff"):
                fetch(self.url, cache_dir, False, 0, retry_backoff=-1)


class GenerationReportTests(unittest.TestCase):
    def test_human_size_uses_binary_units(self) -> None:
        self.assertEqual(human_size(0), "0 o")
        self.assertEqual(human_size(1024), "1.0 Kio")
        self.assertEqual(human_size(1024**2), "1.0 Mio")
        self.assertEqual(human_size(1024**3), "1.0 Gio")

    def test_text_and_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output = base / "book.info"
            output.write_bytes(b"generated-info")
            report = build_generation_report(
                source_url="https://example.test/source",
                entry_count=3,
                linked_pages=2,
                orphan_pages=1,
                texi=(
                    "@cindex 1\n@cindex CEC 1\n"
                    "@cindex 2\n@cindex CEC 2\n"
                ),
                outputs={"info": output},
            )
            json_path = base / "report.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                emit_generation_report(report, json_path)

            self.assertIn("3 (2 liées, 1 orphelines)", stderr.getvalue())
            self.assertIn("2 uniques, plage 1–2", stderr.getvalue())
            saved = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["paragraphs"]["unique"], 2)
            self.assertEqual(saved["outputs"]["info"]["bytes"], 14)

    def test_missing_outputs_are_omitted_and_json_is_optional(self) -> None:
        report = build_generation_report(
            source_url="https://example.test/source",
            entry_count=0,
            linked_pages=0,
            orphan_pages=0,
            texi="",
            outputs={"info": Path("fichier-inexistant.info")},
        )
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            emit_generation_report(report)

        self.assertEqual(report["outputs"], {})
        self.assertIn("plage None–None", stderr.getvalue())


class CliTests(unittest.TestCase):
    def test_user_agent_uses_package_version(self) -> None:
        self.assertIn(f"cec2info/{VERSION}", USER_AGENT)

    def test_parser_accepts_all_output_formats(self) -> None:
        args = build_parser().parse_args(
            [
                "--compile",
                "--info",
                "manuel.info",
                "--pdf",
                "--pdf-output",
                "manuel.pdf",
                "--epub",
                "--epub-output",
                "manuel.epub",
                "--expected-last-paragraph",
                "0",
            ]
        )

        self.assertTrue(args.compile)
        self.assertEqual(args.info, Path("manuel.info"))
        self.assertTrue(args.pdf)
        self.assertEqual(args.pdf_output, Path("manuel.pdf"))
        self.assertTrue(args.epub)
        self.assertEqual(args.epub_output, Path("manuel.epub"))
        self.assertEqual(args.expected_last_paragraph, 0)

    def test_parser_rejects_negative_delay(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            build_parser().parse_args(["--delay", "-1"])
        self.assertIn("positive ou nulle", stderr.getvalue())

    def test_numeric_argument_types_accept_nonnegative_values(self) -> None:
        self.assertEqual(nonnegative_float("0.25"), 0.25)
        self.assertEqual(nonnegative_int("12"), 12)
        with self.assertRaisesRegex(argparse.ArgumentTypeError, "positive ou nulle"):
            nonnegative_int("-1")

    def test_main_reports_expected_error_without_traceback(self) -> None:
        stderr = io.StringIO()
        with (
            patch("cec2info.run", side_effect=RuntimeError("échec contrôlé")),
            contextlib.redirect_stderr(stderr),
        ):
            status = main([])

        self.assertEqual(status, 1)
        self.assertIn("Erreur: échec contrôlé", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_run_writes_texinfo_and_report(self) -> None:
        items = "".join(
            f'<li><a href="__P{i}.HTM">Entrée {i}</a></li>'
            for i in range(1, 21)
        )
        index_data = f"<html><body><ul>{items}</ul></body></html>".encode()

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            args = build_parser().parse_args(
                [
                    "--cache-dir",
                    str(base / "cache"),
                    "--output",
                    str(base / "book.texi"),
                    "--expected-last-paragraph",
                    "0",
                    "--report-json",
                    str(base / "report.json"),
                ]
            )
            with (
                patch("cec2info.fetch", return_value=index_data),
                patch("cec2info.load_bodies", return_value=0),
            ):
                status = run(args)

            self.assertEqual(status, 0)
            self.assertIn("@node Top", (base / "book.texi").read_text())
            report = json.loads((base / "report.json").read_text())
            self.assertEqual(report["entries"], 20)
            self.assertEqual(report["pages"]["linked"], 20)

    def test_run_invokes_all_requested_compilers(self) -> None:
        items = "".join(
            f'<li><a href="__P{i}.HTM">Entrée {i}</a></li>'
            for i in range(1, 21)
        )
        index_data = f"<ul>{items}</ul>".encode()

        def create_output(_source: Path, output: Path) -> None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"sortie")

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            args = build_parser().parse_args(
                [
                    "--output",
                    str(base / "book.texi"),
                    "--expected-last-paragraph",
                    "0",
                    "--compile",
                    "--info",
                    str(base / "book.info"),
                    "--pdf",
                    "--pdf-output",
                    str(base / "book.pdf"),
                    "--epub",
                    "--epub-output",
                    str(base / "book.epub"),
                ]
            )
            with (
                patch("cec2info.fetch", return_value=index_data),
                patch("cec2info.load_bodies", return_value=0),
                patch("cec2info.compile_info", side_effect=create_output) as info,
                patch("cec2info.compile_pdf", side_effect=create_output) as pdf,
                patch("cec2info.compile_epub", side_effect=create_output) as epub,
            ):
                status = run(args)

            self.assertEqual(status, 0)
            info.assert_called_once()
            pdf.assert_called_once()
            epub.assert_called_once()


@unittest.skipUnless(
    all(shutil.which(tool) for tool in ("makeinfo", "texi2dvi")),
    "Texinfo/TeX ne sont pas installés",
)
class FormatCompilationTests(unittest.TestCase):
    def test_info_pdf_and_epub_are_generated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            entry = Entry(
                title="Section de test",
                href=None,
                depth=1,
                body=body_to_texinfo("1 Texte de validation des formats."),
            )
            roots = [entry]
            assign_nodes(roots)
            texi = render_texinfo(roots, "https://example.test/source")
            validate_paragraph_indexes(texi, expected_last=1)

            texi_path = base / "test.texi"
            info_path = base / "test.info"
            pdf_path = base / "test.pdf"
            epub_path = base / "test.epub"
            texi_path.write_text(texi, encoding="utf-8")

            compile_info(texi_path, info_path)
            compile_pdf(texi_path, pdf_path)
            compile_epub(texi_path, epub_path)

            self.assertIn(
                "Texte de validation",
                info_path.read_text(encoding="utf-8"),
            )
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF"))
            self.assertFalse(
                any(
                    (base / f"test{suffix}").exists()
                    for suffix in (".aux", ".cp", ".cps", ".dvi", ".log", ".toc")
                )
            )
            with zipfile.ZipFile(epub_path) as archive:
                xhtml = b"".join(
                    archive.read(name)
                    for name in archive.namelist()
                    if name.endswith(".xhtml")
                )
            self.assertIn(b"Texte de validation", xhtml)


class MissingToolTests(unittest.TestCase):
    def test_compilers_report_missing_system_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            texi_path = base / "test.texi"
            texi_path.write_text("@bye\n", encoding="utf-8")

            with patch("cec2info_output.shutil.which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "makeinfo"):
                    compile_info(texi_path, base / "test.info")
                with self.assertRaisesRegex(RuntimeError, "texi2dvi"):
                    compile_pdf(texi_path, base / "test.pdf")
                with self.assertRaisesRegex(RuntimeError, "makeinfo"):
                    compile_epub(texi_path, base / "test.epub")


if __name__ == "__main__":
    unittest.main()
