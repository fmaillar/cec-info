"""Language profiles for Vatican sources and generated documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    index_url: str
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
    index_url="https://www.vatican.va/archive/FRA0013/_INDEX.HTM",
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
    index_url="https://www.vatican.va/archive/ENG0015/_INDEX.HTM",
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

DEFAULT_LANGUAGE = "fr"
LANGUAGE_PROFILES = {profile.code: profile for profile in (ENGLISH, FRENCH)}
OFFICIAL_INDEX_URLS = frozenset(profile.index_url for profile in LANGUAGE_PROFILES.values())


def get_language_profile(code: str) -> LanguageProfile:
    """Return the configured profile for a supported language code."""
    try:
        return LANGUAGE_PROFILES[code]
    except KeyError as exc:
        supported = ", ".join(sorted(LANGUAGE_PROFILES))
        raise ValueError(f"unsupported language {code!r}; choose one of: {supported}") from exc
