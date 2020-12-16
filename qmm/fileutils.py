# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

import enum
import pathlib
from enum import Enum, auto
from functools import lru_cache

from PyQt5 import QtGui

from qmm import bucket

# Mods directory structure
# REVIEW: Should be used in function `build_game_files_crc32`. However the path
#  structure is too complex and a dedicated function or module should be written
#  in order to build paths corresponding the the game expectation.
# NOTE: race folder contains it's how set of sub-folders. Might need to be
first_level_dir = (
    "items", "outfits", "setBonuses", "statusEffects", "race", "colours", "combatMove"
)
subfolders_of = {
    "items": ("weapons", "clothing", "tattoos", "items", "patterns"),
    "race": ("bodyParts", "coveringTypes", "subspecies")
}


class FileState(Enum):
    #: Indicate that the file is found on the drive, and match in content.
    MATCHED = auto()
    #: Indicate that the file is absent from the drive.
    MISSING = auto()
    #: Indicate that the file to exists on drive, but not matching in content.
    MISMATCHED = auto()
    #: Indicate that the file will be ignored by the software.
    IGNORED = auto()

    def __str__(self):
        if self.name is self.MATCHED.name:
            return _("Matched")
        if self.name is self.MISSING.name:
            return _("Missing")
        if self.name is self.MISMATCHED.name:
            return _("Mismatched")
        if self.name is self.IGNORED.name:
            return _("Ignored")

        raise Exception(
            f"String representation of the requested enum '{self.name}' does not exists.\n"
        )

    @property
    def qcolor(self) -> QtGui.QColor:
        return FileStateColor[self.name].qcolor


class FileStateColor(Enum):
    """Gradients of colors for each file of the tree widget."""
    MATCHED = (91, 135, 33, 255)  # greenish
    MISMATCHED = (132, 161, 225, 255)  # blueish
    MISSING = (237, 213, 181, 255)  # (225, 185, 132, 255),  # yellowish
    CONFLICTS = (135, 33, 39, 255)  # red-ish
    IGNORED = (219, 219, 219, 255)  # gray
    tab_ignored = (135, 33, 39, 255)
    tab_conflict = (135, 33, 39, 255)

    def __init__(self, r, g, b, a):
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    @property
    def qcolor(self) -> QtGui.QColor:
        return QtGui.QColor(self.r, self.g, self.b, self.a)


class ArchiveEvents(enum.Enum):
    FILE_ADDED = enum.auto()
    FILE_REMOVED = enum.auto()


def ignore_patterns(seven_flag=False):
    """Output a tuple of patterns to ignore.

    Args:
        seven_flag (bool): Patterns format following 7z exclude switch.
    """
    if seven_flag:
        return "-xr!*.DS_Store", "-x!__MACOSX", "-xr!*Thumbs.db"
    return ".DS_Store", "__MACOSX", "Thumbs.db"


@lru_cache(maxsize=None)
def _bad_directory_structure(path: pathlib.Path):
    if (
        len(path.parts) >= 2
        and path.parts[1] not in first_level_dir
        or len(path.parts) >= 3
        and path.parts[1] == "items"
        and path.parts[2] not in subfolders_of["items"]
    ):
        return True
    return False


@lru_cache(maxsize=None)
def _bad_suffix(suffix):
    return bool(suffix not in (".xml", ".svg"))


def file_status(file: bucket.FileMetadata) -> FileState:
    if (
        file.pathobj.name in ignore_patterns()
        or _bad_directory_structure(file.path_as_posix())
        or (file.pathobj.suffix and _bad_suffix(file.pathobj.suffix))
    ):
        return FileState.IGNORED
    if (
        file.is_dir()
        and bucket.file_path_in_loosefiles(file)
        or bucket.file_crc_in_loosefiles(file)
        and bucket.file_path_in_loosefiles(file)
    ):
        return FileState.MATCHED
    if bucket.file_path_in_loosefiles(file) and not bucket.file_crc_in_loosefiles(file):
        return FileState.MISMATCHED
    return FileState.MISSING
