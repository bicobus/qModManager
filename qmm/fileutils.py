# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020-2021 bicobus <bicobus@keemail.me>

import enum
import pathlib
from enum import Enum, auto

from PyQt5 import QtGui

from qmm import bucket
from qmm.gamestruct import GameStructure, liliththrone

game_structure = GameStructure(liliththrone.validators)


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


def file_status(file: bucket.FileMetadata) -> FileState:
    if file.pathobj.name in ignore_patterns() or (
        len(pathlib.Path(file.path).parts) >= 2
        and not game_structure.validate(str(file.path_as_posix()))
    ):
        return FileState.IGNORED
    if bucket.file_path_in_loosefiles(file) and (
        file.is_dir() or bucket.file_crc_in_loosefiles(file)
    ):
        return FileState.MATCHED
    if bucket.file_path_in_loosefiles(file) and not bucket.file_crc_in_loosefiles(file):
        return FileState.MISMATCHED
    return FileState.MISSING
