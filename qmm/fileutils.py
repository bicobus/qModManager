# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

import enum
import pathlib
from functools import lru_cache

from qmm import bucket

# Mods directory structure
# REVIEW: Should be used in function `build_game_files_crc32`. However the path
# structure is too complex and a dedicated function or module should be written
# in order to build paths corresponding the the game expectation.
first_level_dir = ("items", "outfits", "setBonuses", "statusEffects")
subfolders_of = {
    "items": ("weapons", "clothing", "tattoos", "items", "patterns")
}

# TODO: use enums instead of constants. Namespace: FileStatus

#: Indicate that the file is found on the drive, and match in content.
FILE_MATCHED = 1
#: Indicate that the file is absent from the drive.
FILE_MISSING = 2
#: Indicate that the file to exists on drive, but not matching in content.
FILE_MISMATCHED = 3
#: Indicate that the file will be ignored by the software.
FILE_IGNORED = 4


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


def file_status(file: bucket.FileMetadata) -> int:
    if (
        file.pathobj.name in ignore_patterns()
        or _bad_directory_structure(file.path_as_posix())
        or (file.pathobj.suffix and _bad_suffix(file.pathobj.suffix))
    ):
        return FILE_IGNORED
    if (
        file.is_dir()
        and bucket.file_path_in_loosefiles(file)
        or bucket.file_crc_in_loosefiles(file)
        and bucket.file_path_in_loosefiles(file)
    ):
        return FILE_MATCHED
    if bucket.file_path_in_loosefiles(file) and not bucket.file_crc_in_loosefiles(file):
        return FILE_MISMATCHED
    return FILE_MISSING
