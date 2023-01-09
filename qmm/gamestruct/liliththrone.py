# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
import os
import pathlib
import re
from typing import List, Union

import attr

from . import as_validator
validators = []
main_folders = []
sub_folders = {}
TARGET_FOLDER = os.path.join("{}", "res")  # Path to append to the root of the game
MODS_FOLDER = os.path.join(TARGET_FOLDER, "mods")  # Path to append to TARGET_FOLDER

# Some normalization are required for these game folders
_special_action = (
    "clothing", "outfits", "tattoos", "weapons", "items"
    "colours",
    "combatMoves",
    "dialogue",
    "patterns",
    "race",
    "setBonuses",
    "sex",
    "statusEffects",
)
# Sub folders of TARGET_FOLDER
GAME_FOLDERS = ["encounters", "maps", "txt", ]
GAME_FOLDERS.extend(_special_action)


def path_game2mod(path) -> Union[bool, pathlib.PurePath]:
    try:
        category, namespace, extra = path.split(os.path.sep, 2)
    except ValueError as e:
        return False
    if category in _special_action:
        if category in sub_folders["items"]:
            newpath = pathlib.PurePath(namespace, "items", category, extra)
        else:
            newpath = pathlib.PurePath(namespace, category, extra)
    else:
        newpath = pathlib.PurePath(path)
    return newpath


class _MatchReValidator:
    """Validator helper to match a string to a precompiled regex."""
    def __init__(self, regex, flags=None):
        if not isinstance(regex, re.Pattern):
            self.regex = re.compile(regex, flags)  # type: ignore
        else:
            self.regex = regex

    def match(self, inst, attrib, value: str):
        if not self.regex.fullmatch(value):
            raise ValueError(
                "'{name}' must match regex {pattern!r}"
                " ({value!r} doesn't)".format(
                    name=attrib.name, pattern=self.regex.pattern, value=value
                ),
                attrib,
                self.regex,
                value,
            )


# matches:
# * innoxia/items/clothing/template/socks.svg
# * innoxia/items/tattoos/heartWomb/heart_womb.svg
# * innoxia/items/items/race/background_bottom.svg
# * innoxia/items/patterns/file.xml
_itemsr = _MatchReValidator(
    re.compile(
        r"""^[^/]+/items/
(?:
    (?:clothing|weapons|tattoos|items)/(?:[^/]+/)*(?:[^/]+(?=\.svg|\.xml)\.(?:svg|xml))?$
    |patterns/(?:[^/]+\.xml)?$
    |$
)""",
        re.X,
    )
)


@as_validator
@attr.s(frozen=True)
class ItemsValidator:
    data = attr.ib(validator=_itemsr.match)

    @staticmethod
    def primary() -> str:
        return "items"

    @staticmethod
    def secondary() -> List[str]:
        return ["clothing", "weapons", "tattoos", "items", "patterns"]


# matches:
# * innoxia/race/hyena/coveringTypes/fur.xml
# * innoxia/race/hyena/bodyParts/breast.xml
# * innoxia/race/hyena/subspecies/striped.xml
# * innoxia/race/hyena/racialBody.xml
# * innoxia/race/hyena/race.xml
racer = _MatchReValidator(
    re.compile(
        r"""^[^/]+/race/(?:[^/]+/
    (?:
        (?:bodyParts/|coveringTypes/)(?:[^/]+\.xml)?$
        |subspecies/(?:[^/]+\.(?:svg|xml))?$
        |(?:racialBody|race)\.xml$
        |$
    )
|$)""",
        re.X,
    )
)


@as_validator
@attr.s(frozen=True)
class RaceValidator:
    data = attr.ib(validator=racer.match)

    @staticmethod
    def primary():
        return "race"

    @staticmethod
    def secondary():
        return ["bodyparts", "coveringTypes", "subspecies"]


_outfitsr = _MatchReValidator(
    re.compile(r"^[^/]+/outfits/(?:[^/]+/)*(?:[^/]+\.xml)?$")
)


@as_validator
@attr.s(frozen=True)
class OutfitsValidator:
    data = attr.ib(validator=_outfitsr.match)

    @staticmethod
    def primary():
        return "outfits"

    @staticmethod
    def secondary():
        return None


coloursr = _MatchReValidator(
    re.compile(r"^[^/]+/colours/(?:[^/]+(?=\.xml)\.xml)?$")
)


@as_validator
@attr.s(frozen=True)
class ColoursValidator:
    data = attr.ib(validator=coloursr.match)

    @staticmethod
    def primary():
        return "colours"

    @staticmethod
    def secondary():
        return None


_setbonusesr = _MatchReValidator(
    re.compile(r"^[^/]+/setBonuses/(?:[^/]+\.xml)?$")
)


@as_validator
@attr.s(frozen=True)
class SetBonusesValidator:
    data = attr.ib(validator=_setbonusesr.match)

    @staticmethod
    def primary():
        return "setBonuses"

    @staticmethod
    def secondary():
        return None


_statusr = _MatchReValidator(
    re.compile(r"^[^/]+/statusEffects/(?:[^/]+\.(?:xml|svg))?$")
)


@as_validator
@attr.s(frozen=True)
class StatusEffectsValidator:
    data = attr.ib(validator=_statusr.match)

    @staticmethod
    def primary():
        return "statusEffects"

    @staticmethod
    def secondary():
        return None


# Matches:
# * innoxia/combatMove/hyena_bone_crush.svg
# * innoxia/combatMove/hyena_bone_crush.xml
_combatr = _MatchReValidator(
    re.compile(r"^[^/]+/combatMove/(?:[^/]+\.(?:xml|svg))?$")
)


@as_validator
@attr.s(frozen=True)
class CombatMoveValidator:
    data = attr.ib(validator=_combatr.match)

    @staticmethod
    def primary():
        return "combatMove"

    @staticmethod
    def secondary():
        return None


# Matches:
# * AceXp/dialogue/dominion/mansion_dungeon.xml
# * AceXp/dialogue/flags.xml
_dialogr = _MatchReValidator(
    re.compile(r"^[^/]+/dialogue/(?:flags\.xml$|(?:[^/]+/)*(?:[^/]+\.xml)?$|$)")
)


@as_validator
@attr.s(frozen=True)
class DialogueValidator:
    data = attr.ib(validator=_dialogr.match)

    @staticmethod
    def primary():
        return "dialogue"

    @staticmethod
    def secondary():
        return None


_encountersr = _MatchReValidator(
    re.compile(r"^[^/]+/encounters/(?:[^/]+/)*(?:[^/]+\.xml)?$")
)


@as_validator
@attr.s(frozen=True)
class EncountersValidator:
    data = attr.ib(validator=_encountersr.match)

    @staticmethod
    def primary():
        return "encounters"

    @staticmethod
    def secondary():
        return None


_sexr = _MatchReValidator(
    re.compile(r"^[^/]+/sex/(?:(?:managers|actions)/(?:[^/]+\.xml)?$|$)")
)


@as_validator
@attr.s(frozen=True)
class SexValidator:
    data = attr.ib(validator=_sexr.match)

    @staticmethod
    def primary():
        return "sex"

    @staticmethod
    def secondary():
        return ["managers", "actions"]


# Matches:
# * AceXp/maps/dominion/mansion/dungeon/map.png
# * AceXp/maps/dominion/mansion/dungeon/worldType.xml
# * AceXp/maps/dominion/mansion/dungeon/placeTypes/stairs.xml
# * AceXp/maps/dominion/mansion/dungeon/placeTypes/stairs.svg
_mapsr = _MatchReValidator(
    re.compile(
        r"""^[^/]+/maps/(?:
    (?:[^/]+/)+(?:
        (?<!placeTypes/)map\.png$
        |(?<!placeTypes/)worldType\.xml$
        |placeTypes/(?!worldType)(?:[^/]+\.(?:xml|svg))?$
        |$
    )
    |$
)"""
        , re.X)
)


@as_validator
@attr.s(frozen=True)
class MapsValidator:
    data = attr.ib(validator=_mapsr.match)

    @staticmethod
    def primary():
        return "maps"

    @staticmethod
    def secondary():
        return ["placeTypes"]


_txtr = _MatchReValidator(
    re.compile(r"^[^/]+/txt/(?:[^/]+/(?:[^/]+\.xml)?$|[^/]+\.xml$|$)")
)


@as_validator
@attr.s(frozen=True)
class TxtValidator:
    data = attr.ib(validator=_txtr.match)

    @staticmethod
    def primary():
        return "txt"

    @staticmethod
    def secondary():
        return None
