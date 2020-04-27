# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Buckets of dicts with a set of helpers function.

This module serves has a stand-in database, any function or method it contain
would be facilitator to either access or transform the data. This module is
necessary in order to keep track of the state of the different files and make
that specific state available globally within the other modules.
"""
import logging
import pathlib
from datetime import datetime
from os.path import join, sep
from typing import Dict, List, TypeVar, Union

from qmm.common import settings

logger = logging.getLogger(__name__)
TYPE_LOOSEFILE = 1
TYPE_GAMEFILE = 2


class FileMetadata:
    """Representation of a file.

    Can handle game files, mod files or file information comming from an
    archive.
    """

    def __init__(self, crc, path: Union[str, pathlib.Path], attributes, modified, isfrom):
        self._CRC = crc
        self._from = isfrom
        if isinstance(path, pathlib.Path):
            self._normalize_path(path)
        else:
            self._normalize_path(pathlib.Path(path))

        if not attributes:
            self._Attributes = 'D' if self.pathobj.is_dir() else ''
        else:
            self._Attributes = attributes

        if not modified and self.pathobj.exists():
            self._Modified = datetime.strftime(
                datetime.fromtimestamp(self.pathobj.stat().st_mtime),
                "%Y-%m-%d %H:%M:%S")
        else:
            self._Modified = modified

    def _normalize_path(
        self,
        pathobj: pathlib.Path,
        partition=('res', 'mods')
    ):
        """Return a pathlib.Path object with a normalized path.

        We want to build a path that is similar to the one present in an
        archive. To do so we need to remove anything that is before, and
        including the "partition" folder.
        ...blah/res/mods/namespace/category/ -> namespace/category/
        """
        if pathobj.is_absolute():
            self._Path = pathobj.as_posix().partition(join(*partition) + sep)[2]
            self.pathobj = pathobj
        else:  # assume we already have the normalized string, fed from the archive
            self._Path = pathobj.as_posix()
            self.pathobj = pathlib.Path(settings['game_folder'],
                                        *partition,
                                        pathobj)

    def is_dir(self):
        """Check if the represented item is a directory"""
        if not self.pathobj.exists():
            return bool('D' in self._Attributes)
        return self.pathobj.is_dir()

    def is_file(self):
        """Check if the represented item is a file"""
        if not self.pathobj.exists():
            return bool('D' not in self._Attributes)
        return self.pathobj.is_file()

    def exists(self):
        """Check if the file exists on the disk"""
        return self.pathobj.exists()

    def path_as_posix(self):
        return pathlib.PurePosixPath(self._Path)

    @property
    def crc(self):
        return self._CRC

    @property
    def path(self):
        return self._Path

    @property
    def attributes(self):
        return self._Attributes

    @property
    def modified(self):
        return self._Modified

    @property
    def origin(self):
        r = self._from
        if self._from == TYPE_LOOSEFILE:
            r = 'Loosefile'
        elif self._from == TYPE_GAMEFILE:
            r = 'GameFile'
        return r

    def as_dict(self):
        """Return this object as a dict (kinda)."""
        return {
            'CRC': self._CRC,
            'Path': self._Path,
            'Attributes': self._Attributes,
            'Modified': self._Modified,
            'From': self._from,
            '_self': self
        }

    def __str__(self):
        return (
            f"{self.__class__}({self._Path}, crc: {self._CRC}, "
            f"from: {self.origin})"
        )


Crc32 = TypeVar("Crc32", int, int)
Conflict = Dict[str, List]
LooseFiles = Dict[Crc32, List[FileMetadata]]
GameFiles = Dict[Crc32, FileMetadata]

conflicts: Conflict = {}
loosefiles: LooseFiles = {}
gamefiles: GameFiles = {}


def _find_index_from(lbucket, crc, path):
    for item in lbucket[crc]:
        if item.path == path:
            return lbucket[crc].index(item)
    return False


def with_conflict(path: str) -> bool:
    """Check if path exists in conflicts's keys.

    The conflicts bucket purpose is to list issues in-between archives only.

    Args:
        path (str):  Simple string, should be a path pointing to a file
    Returns:
        bool: True if path exist in conflicts's keys
    """
    return bool(path in conflicts.keys())


def file_crc_in_loosefiles(filemd: FileMetadata) -> bool:
    """Check if a file's crc exists in loosefile's index."""
    return bool(filemd.crc in loosefiles.keys())


def file_path_in_loosefiles(filemd: FileMetadata) -> bool:
    """Check if a file's path exists within the different loosefile lists."""
    def _extract_paths(fmd):
        return [x.path for x in fmd]

    return bool(any(filemd.path in _extract_paths(v) for v in loosefiles.values()))


def with_gamefiles(crc: int = None, path: str = None):
    """First check if a CRC32 exist within the gamefiles bucket, if no CRC is
    given or the check fails, will then check if a path is present in the
    gamefiles's bucket values.
    Args:
        crc (int): CRC32 as integer
        path (str): the relative pathlike string of a file
    Returns:
        bool: True if either CRC32 or path are found
    """
    if crc in gamefiles.keys():
        return True
    if path in gamefiles.values():
        return True
    return False


def as_conflict(key: str, value):
    """Append and item to the conflicts bucket"""
    conflicts.setdefault(key, [])
    if isinstance(value, list):
        conflicts[key].extend(value)
    else:
        conflicts[key].append(value)


def as_gamefile(crc: int, value: pathlib.Path):
    if crc in gamefiles.keys():
        logger.warning(
            "Duplicate file found, crc matches for\n-> %s\n-> %s",
            gamefiles[crc],
            value)
        return
    value = FileMetadata(
        crc=crc, path=value, modified=None,
        attributes=None, isfrom=TYPE_GAMEFILE)
    gamefiles.setdefault(crc, value)


def as_loosefile(crc: int, filepath: pathlib.Path):
    """Adds filepath to the loosefiles bucket, indexed on given CRC."""
    loosefiles.setdefault(crc, [])
    filepath = FileMetadata(
        crc=crc, path=filepath, modified=None,
        attributes=None, isfrom=TYPE_LOOSEFILE
    )
    loosefiles[crc].append(filepath)


def remove_item_from_loosefiles(file: FileMetadata):
    """Removes the reference to file if it is found in loosefiles"""
    if file.crc in loosefiles.keys():
        if file_path_in_loosefiles(file):
            idx = _find_index_from(loosefiles, file.crc, file.path)
            loosefiles[file.crc].pop(idx)
            if not loosefiles[file.crc]:  # Removes entry if empty
                loosefiles.pop(file.crc)
