# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020-2021 bicobus <bicobus@keemail.me>
import os
import gettext
import locale
import logging

from qmm import get_data_path
from qmm.common import settings

logger = logging.getLogger(__name__)
DEFAULT_LANGUAGE = "en_US"
# List of maintained translation
# fmt: off
LANGUAGE_CODES = [
    ('English (United States)', 'en_US'),
    ('Français', 'fr_FR'),
    ('中文', 'zh')
]
LANGUAGE_ALIASES = {
    'en': 'en_US',
    'fr': 'fr_FR',
    'fr_BE': 'fr_FR',
    'zh_HK': 'zh',
    'zh_TW': 'zh',
    'zh_CN': 'zh',
}
# fmt: on


def normalize_locale(loc: str):
    loc = loc.replace("-", "_")
    if loc in LANGUAGE_ALIASES.keys():
        loc = LANGUAGE_ALIASES[loc]
    return loc


def get_locale():
    if not settings["language"] or settings["language"] == "system":
        try:
            language = locale.getdefaultlocale()[0]
        except ValueError:
            language = DEFAULT_LANGUAGE
        finally:
            if not language:
                language = DEFAULT_LANGUAGE
        language = normalize_locale(language)

        for lang in list_available_languages():
            if lang == language:
                break
            if lang.startswith(language) or language.startswith(lang):
                language = lang
                break
    else:
        if settings["language"] not in list_available_languages():
            settings["language"] = DEFAULT_LANGUAGE
        language = normalize_locale(settings["language"])

    return language


def list_available_languages():
    locale_path = get_data_path("locales")
    langs = [d for d in os.listdir(locale_path) if os.path.isdir(
        os.path.join(locale_path, d))]
    langs.append(DEFAULT_LANGUAGE)

    for lang in langs:
        if not any(normalize_locale(lang) == c[1] for c in LANGUAGE_CODES):
            logger.warning(
                (
                    "A new translation seems to have been added to the locales "
                    "directory. Please update the list of maintained translations "
                    "in the qmm/lang.py file. Code: %s"
                ),
                lang,
            )
            return [DEFAULT_LANGUAGE]
    return langs


def set_gettext(install=True):
    lang = get_locale()
    locale_dir = get_data_path("locales")
    trans = gettext.translation(
        "qmm", localedir=locale_dir, languages=[lang], fallback=True)
    if install:
        trans.install()
    return trans.gettext
