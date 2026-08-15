"""Language profiles for Vatican sources and generated documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    texinfo_language: str
    index_url: str
    source_format: str
    content_start_pattern: str
    paragraph_number_corrections: tuple[tuple[int, int], ...]
    document_title: str
    info_basename: str
    dir_entry_name: str
    paragraph_prefix: str
    paragraph_index_title: str
    next_label: str
    boilerplate_phrases: tuple[str, ...]
    ignored_lines: frozenset[str]
    part_pattern: str
    section_pattern: str
    chapter_pattern: str
    article_pattern: str
    paragraph_pattern: str
    unnumbered_titles: frozenset[str]
    brief_titles: frozenset[str]
    conversion_notice: str
    source_rights_notice: str
    subtitle: str
    introduction: str
    navigation_help: str


FRENCH = LanguageProfile(
    code="fr",
    texinfo_language="fr",
    index_url="https://www.vatican.va/archive/FRA0013/_INDEX.HTM",
    source_format="intratext",
    content_start_pattern=r"^PROLOGUE$",
    paragraph_number_corrections=(),
    document_title="Catéchisme de l'Église catholique",
    info_basename="catechisme",
    dir_entry_name="Catéchisme",
    paragraph_prefix="CEC",
    paragraph_index_title="Index des paragraphes du CEC",
    next_label="suivant",
    boilerplate_phrases=(
        "intratext - lecture du texte",
        "copyright © libreria editrice vaticana",
        "précédent",
        "suivant",
        "aide",
        "le saint-siège",
    ),
    ignored_lines=frozenset(
        {
            "catéchisme de l'église catholique",
            "intratext - lecture du texte",
            "précédent - suivant",
            "précédent",
            "suivant",
        }
    ),
    part_pattern=r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+PARTIE\b",
    section_pattern=r"^(PREMIERE|DEUXIEME|TROISIEME|QUATRIEME)\s+SECTION\b",
    chapter_pattern=r"^CHAPITRE\b",
    article_pattern=r"^ARTICLE\s+\d+\b",
    paragraph_pattern=r"^PARAGRAPHE\s+\d+\b",
    unnumbered_titles=frozenset({"liste des sigles", "prologue"}),
    brief_titles=frozenset({"en bref"}),
    conversion_notice=(
        "Conversion personnelle au format GNU Info à partir du texte publié par\n"
        "le Saint-Siège / Libreria Editrice Vaticana."
    ),
    source_rights_notice="Le texte source demeure soumis aux droits indiqués par son éditeur.",
    subtitle="Édition GNU Info générée depuis le corpus officiel du Vatican",
    introduction=(
        "Cette édition est générée automatiquement depuis le sommaire et les pages\n"
        "de lecture IntraText du Vatican."
    ),
    navigation_help=(
        "Navigation : utilisez @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} pour un menu,\n"
        "@kbd{i} pour l'index des numéros du CEC, et @kbd{s} pour une recherche\n"
        "plein texte."
    ),
)

ENGLISH = LanguageProfile(
    code="en",
    texinfo_language="en",
    index_url="https://www.vatican.va/archive/ENG0015/_INDEX.HTM",
    source_format="intratext",
    content_start_pattern=r"^PROLOGUE$",
    paragraph_number_corrections=(),
    document_title="Catechism of the Catholic Church",
    info_basename="catechism",
    dir_entry_name="Catechism",
    paragraph_prefix="CCC",
    paragraph_index_title="Index of CCC paragraphs",
    next_label="next",
    boilerplate_phrases=(
        "intratext - text",
        "copyright © libreria editrice vaticana",
        "previous",
        "next",
        "help",
        "the holy see",
    ),
    ignored_lines=frozenset(
        {
            "catechism of the catholic church",
            "intratext - text",
            "previous - next",
            "previous",
            "next",
        }
    ),
    part_pattern=r"^PART\s+(ONE|TWO|THREE|FOUR)\b",
    section_pattern=r"^SECTION\s+(ONE|TWO|THREE|FOUR)\b",
    chapter_pattern=r"^CHAPTER\b",
    article_pattern=r"^ARTICLE\s+\d+\b",
    paragraph_pattern=r"^PARAGRAPH\s+\d+[.]?\b",
    unnumbered_titles=frozenset({"abbreviations", "prologue"}),
    brief_titles=frozenset({"in brief"}),
    conversion_notice=(
        "Personal GNU Info conversion based on the text published by\n"
        "the Holy See / Libreria Editrice Vaticana."
    ),
    source_rights_notice="The source text remains subject to the rights stated by its publisher.",
    subtitle="GNU Info edition generated from the official Vatican corpus",
    introduction=(
        "This edition is generated automatically from the Vatican IntraText table\n"
        "of contents and reading pages."
    ),
    navigation_help=(
        "Navigation: use @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} for a menu,\n"
        "@kbd{i} for the CCC paragraph index, and @kbd{s} for a full-text search."
    ),
)

GERMAN = LanguageProfile(
    code="de",
    texinfo_language="de",
    index_url="https://www.vatican.va/archive/DEU0035/_INDEX.HTM",
    source_format="intratext",
    content_start_pattern=r"^PROLOG$",
    paragraph_number_corrections=(),
    document_title="Katechismus der Katholischen Kirche",
    info_basename="katechismus",
    dir_entry_name="Katechismus",
    paragraph_prefix="KKK",
    paragraph_index_title="Index der KKK-Absätze",
    next_label="vor",
    boilerplate_phrases=(
        "intratext - text",
        "copyright © libreria editrice vaticana",
        "zurück",
        "hilfe",
        "der heilige stuhl",
    ),
    ignored_lines=frozenset(
        {
            "katechismus der katholischen kirche",
            "intratext - text",
            "zurück - vor",
            "zurück",
            "vor",
        }
    ),
    part_pattern=r"^(ERSTER|ZWEITER|DRITTER|VIERTER)\s+TEIL\b",
    section_pattern=r"^(ERSTER|ZWEITER|DRITTER|VIERTER)\s+ABSCHNITT\b",
    chapter_pattern=r"^(ERSTES|ZWEITES|DRITTES|VIERTES)\s+KAPITEL\b",
    article_pattern=r"^ARTIKEL\s+\d+\b",
    paragraph_pattern=r"^ABSATZ\s+\d+\b",
    unnumbered_titles=frozenset({"abkürzungen", "prolog"}),
    brief_titles=frozenset({"kurztext"}),
    conversion_notice=(
        "Persönliche GNU-Info-Konvertierung auf Grundlage des vom\n"
        "Heiligen Stuhl / der Libreria Editrice Vaticana veröffentlichten Textes."
    ),
    source_rights_notice="Der Quelltext unterliegt weiterhin den vom Herausgeber angegebenen Rechten.",
    subtitle="Aus dem offiziellen vatikanischen Korpus erzeugte GNU-Info-Ausgabe",
    introduction=(
        "Diese Ausgabe wird automatisch aus dem Inhaltsverzeichnis und den\n"
        "IntraText-Leseseiten des Vatikans erzeugt."
    ),
    navigation_help=(
        "Navigation: @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} für ein Menü,\n"
        "@kbd{i} für den KKK-Absatzindex und @kbd{s} für die Volltextsuche."
    ),
)

ITALIAN = LanguageProfile(
    code="it",
    texinfo_language="it",
    index_url="https://www.vatican.va/archive/catechism_it/index_it.htm",
    source_format="legacy",
    content_start_pattern=r"^PREFAZIONE$",
    paragraph_number_corrections=(),
    document_title="Catechismo della Chiesa Cattolica",
    info_basename="catechismo",
    dir_entry_name="Catechismo",
    paragraph_prefix="CCC",
    paragraph_index_title="Indice dei paragrafi del CCC",
    next_label="successivo",
    boilerplate_phrases=("copyright © libreria editrice vaticana", "indice", "home"),
    ignored_lines=frozenset({"catechismo della chiesa cattolica"}),
    part_pattern=r"^PARTE\s+(PRIMA|SECONDA|TERZA|QUARTA)\b",
    section_pattern=r"^SEZIONE\s+(PRIMA|SECONDA|TERZA|QUARTA)\b",
    chapter_pattern=r"^CAPITOLO\b",
    article_pattern=r"^ARTICOLO\s+\d+\b",
    paragraph_pattern=r"^PARAGRAFO\s+\d+\b",
    unnumbered_titles=frozenset({"elenco delle abbreviazioni", "prefazione"}),
    brief_titles=frozenset({"in sintesi"}),
    conversion_notice=(
        "Conversione personale in GNU Info basata sul testo pubblicato dalla\n"
        "Santa Sede / Libreria Editrice Vaticana."
    ),
    source_rights_notice="Il testo sorgente resta soggetto ai diritti indicati dall'editore.",
    subtitle="Edizione GNU Info generata dal corpus ufficiale del Vaticano",
    introduction="Questa edizione è generata automaticamente dalle pagine ufficiali del Vaticano.",
    navigation_help=(
        "Navigazione: @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} per un menu,\n"
        "@kbd{i} per l'indice dei paragrafi e @kbd{s} per la ricerca."
    ),
)

SPANISH = LanguageProfile(
    code="es",
    texinfo_language="es",
    index_url="https://www.vatican.va/archive/catechism_sp/index_sp.html",
    source_format="legacy",
    content_start_pattern=r"^PRÓLOGO$",
    paragraph_number_corrections=(),
    document_title="Catecismo de la Iglesia Católica",
    info_basename="catecismo-es",
    dir_entry_name="Catecismo",
    paragraph_prefix="CIC",
    paragraph_index_title="Índice de los párrafos del CIC",
    next_label="siguiente",
    boilerplate_phrases=("copyright © libreria editrice vaticana", "índice", "inicio"),
    ignored_lines=frozenset({"catecismo de la iglesia católica"}),
    part_pattern=r"^(PRIMERA|SEGUNDA|TERCERA|CUARTA)\s+PARTE\b",
    section_pattern=r"^(PRIMERA|SEGUNDA|TERCERA|CUARTA)\s+SECCIÓN\b",
    chapter_pattern=r"^CAPÍTULO\b",
    article_pattern=r"^ARTÍCULO\s+\d+\b",
    paragraph_pattern=r"^PÁRRAFO\s+\d+\b",
    unnumbered_titles=frozenset({"abreviaturas", "prólogo"}),
    brief_titles=frozenset({"resumen"}),
    conversion_notice=(
        "Conversión personal a GNU Info basada en el texto publicado por la\n"
        "Santa Sede / Libreria Editrice Vaticana."
    ),
    source_rights_notice="El texto fuente sigue sujeto a los derechos indicados por su editor.",
    subtitle="Edición GNU Info generada a partir del corpus oficial del Vaticano",
    introduction="Esta edición se genera automáticamente desde las páginas oficiales del Vaticano.",
    navigation_help=(
        "Navegación: @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} para un menú,\n"
        "@kbd{i} para el índice de párrafos y @kbd{s} para buscar."
    ),
)

PORTUGUESE = LanguageProfile(
    code="pt",
    texinfo_language="pt",
    index_url="https://www.vatican.va/archive/cathechism_po/index_new/prima-pagina-cic_po.html",
    source_format="legacy",
    content_start_pattern=r"^§\s*1\s*-\s*§\s*25$",
    paragraph_number_corrections=((2117, 2217), (1439, 2439)),
    document_title="Catecismo da Igreja Católica",
    info_basename="catecismo-pt",
    dir_entry_name="Catecismo",
    paragraph_prefix="CIC",
    paragraph_index_title="Índice dos parágrafos do CIC",
    next_label="seguinte",
    boilerplate_phrases=("copyright © libreria editrice vaticana", "índice", "início"),
    ignored_lines=frozenset({"catecismo da igreja católica"}),
    part_pattern=r"^(PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA)\s+PARTE\b",
    section_pattern=r"^(PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA)\s+SECÇÃO\b",
    chapter_pattern=r"^CAPÍTULO\b",
    article_pattern=r"^ARTIGO\s+\d+\b",
    paragraph_pattern=r"^PARÁGRAFO\s+\d+\b",
    unnumbered_titles=frozenset({"abreviaturas", "prólogo"}),
    brief_titles=frozenset({"resumindo"}),
    conversion_notice=(
        "Conversão pessoal para GNU Info baseada no texto publicado pela\n"
        "Santa Sé / Libreria Editrice Vaticana."
    ),
    source_rights_notice="O texto-fonte permanece sujeito aos direitos indicados pelo editor.",
    subtitle="Edição GNU Info gerada a partir do corpus oficial do Vaticano",
    introduction="Esta edição é gerada automaticamente a partir das páginas oficiais do Vaticano.",
    navigation_help=(
        "Navegação: @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} para um menu,\n"
        "@kbd{i} para o índice dos parágrafos e @kbd{s} para pesquisar."
    ),
)

LATIN = LanguageProfile(
    code="la",
    # GNU Texinfo does not ship a Latin localization table.
    texinfo_language="en",
    index_url="https://www.vatican.va/archive/catechism_lt/index_lt.htm",
    source_format="legacy",
    content_start_pattern=r"^PROOEMIUM$",
    paragraph_number_corrections=(),
    document_title="Catechismus Catholicae Ecclesiae",
    info_basename="catechismus-la",
    dir_entry_name="Catechismus",
    paragraph_prefix="CCE",
    paragraph_index_title="Index numerorum CCE",
    next_label="sequens",
    boilerplate_phrases=("copyright © libreria editrice vaticana", "index", "initium"),
    ignored_lines=frozenset({"catechismus catholicae ecclesiae"}),
    part_pattern=r"^PARS\s+(PRIMA|SECUNDA|TERTIA|QUARTA)\b",
    section_pattern=r"^SECTIO\s+(PRIMA|SECUNDA|TERTIA|QUARTA)\b",
    chapter_pattern=r"^CAPUT\b",
    article_pattern=r"^ARTICULUS\s+\d+\b",
    paragraph_pattern=r"^NUMERUS\s+\d+\b",
    unnumbered_titles=frozenset({"compendia", "prooemium"}),
    brief_titles=frozenset({"compendium"}),
    conversion_notice=(
        "Conversio personalis in formam GNU Info ex textu a Sancta Sede /\n"
        "Libreria Editrice Vaticana publicato."
    ),
    source_rights_notice="Textus fontis iuribus ab editore indicatis manet subiectus.",
    subtitle="Editio GNU Info ex corpore Vaticano officiali generata",
    introduction="Haec editio automatice ex paginis officialibus Vaticanis generatur.",
    navigation_help=(
        "Navigatio: @kbd{n} / @kbd{p} / @kbd{u}, @kbd{m} pro indice,\n"
        "@kbd{i} pro indice numerorum et @kbd{s} ad quaerendum."
    ),
)

DEFAULT_LANGUAGE = "fr"
LANGUAGE_PROFILES = {
    profile.code: profile
    for profile in (ENGLISH, FRENCH, GERMAN, ITALIAN, LATIN, PORTUGUESE, SPANISH)
}
OFFICIAL_INDEX_URLS = frozenset(profile.index_url for profile in LANGUAGE_PROFILES.values())


def get_language_profile(code: str) -> LanguageProfile:
    """Return the configured profile for a supported language code."""
    try:
        return LANGUAGE_PROFILES[code]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGE_PROFILES))
        raise ValueError(f"unsupported language {code!r}; choose one of: {supported}") from exc
