# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>
import os
import gettext
import locale
import logging
from . import get_data_path
from .common import settings

logger = logging.getLogger(__name__)
DEFAULT_LANGUAGE = "en"
# List of maintained translation
LANGUAGE_CODES = [
    ('English (United States)', 'en_US'),
    ('French', 'fr_FR')
]
LANGUAGE_ALIASES = {
    'en': 'en_US',
    'fr': 'fr_FR',
    'fr_BE': 'fr_FR'
}


def normalize_locale(loc: str):
    loc = loc.replace('-', '_')
    if loc in LANGUAGE_ALIASES.keys():
        loc = LANGUAGE_ALIASES[loc]
    return loc


def get_locale():
    if not settings['language']:
        try:
            language = locale.getdefaultlocale()[0]
        except ValueError:
            language = DEFAULT_LANGUAGE
        language = normalize_locale(language)

        for lang in list_available_languages():
            if lang == language:
                break
            if lang.startswith(language) or language.startswith(lang):
                language = lang
                break
    else:
        if settings['language'] not in list_available_languages():
            settings['language'] = DEFAULT_LANGUAGE
        language = normalize_locale(settings['language'])

    return language


def list_available_languages():
    locale_path = get_data_path('locales')
    langs = [d for d in os.listdir(locale_path)
             if os.path.isdir(os.path.join(locale_path, d))]
    langs.append(DEFAULT_LANGUAGE)

    for lang in langs:
        if any(lang == code[1] for code in LANGUAGE_CODES):
            logger.warning((
                "A new translation seems to have been added to the locales "
                "directory. Please update the list of maintained translations "
                "in the qmm/lang.py file. Code: %s"
            ), lang)
            return [DEFAULT_LANGUAGE]
    return langs


def set_gettext():
    lang = get_locale()
    locale_dir = get_data_path('locales')
    trans = gettext.translation(
        "qmm", localedir=locale_dir, languages=[lang], fallback=True
    )
    return trans.gettext


_ = set_gettext()
