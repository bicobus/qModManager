"""Buckets of dicts with a set of functions necessary to keep track of
the state of the game file structure.

  Licensed under the EUPL v1.2
  © 2019 bicobus <bicobus@keemail.me>
"""
import logging
from typing import Dict, List
from . import FileMetadata

logger = logging.getLogger(__name__)

conflicts: Dict[str, List] = {}
loosefiles: Dict[int, List] = {}
gamefiles: Dict[int, str] = {}
looseconflicts: Dict[int, List] = {}


def with_conflict(path: str) -> bool:
    """Check if path exists in conflicts's keys.

    Args:
        path (str):  Simple string, should be a path pointing to a file
    """
    return bool(path in conflicts.keys())


def with_loosefiles(crc: int = None, path: str = None) -> bool:
    """Check if either a crc or a path is present in the loosefiles bucket.

    Args:
        crc (int): If not None, will check if the value in loosefiles's keys
        path (str): If not None, will check if the value can be found in loosefiles
    Returns:
        bool: Returns True if either crc or path is found, otherwise False
    """
    if crc and crc in loosefiles.keys():
        return True
    if path and any(path in v for v in loosefiles.values()):
        return True
    return False


def with_looseconflicts(crc: int) -> bool:
    return bool(crc in looseconflicts.keys())


def with_gamefiles(crc: int = None, path: str = None):
    if crc in gamefiles.keys():
        return True
    if path in gamefiles.values():
        return True
    return False


def as_conflict(key: str, value):
    conflicts.setdefault(key, [])
    if isinstance(value, list):
        conflicts[key].extend(value)
    else:
        conflicts[key].append(value)


def as_gamefile(crc: int, value: str):
    if crc in gamefiles.keys():
        logger.warning(
            "Duplicate file found, crc matches for\n-> %s\n-> %s",
            gamefiles[crc],
            value)
        return
    gamefiles.setdefault(crc, value)


def as_loose_conflicts(file: FileMetadata):
    looseconflicts.setdefault(file.CRC, [])
    looseconflicts[file.CRC].append(loosefiles[file.CRC])


def as_loosefile(crc: int, filepath: str):
    loosefiles.setdefault(crc, [])
    loosefiles[crc].append(filepath)


def remove_from_loosefiles(file: FileMetadata):
    if file.CRC in loosefiles.keys():
        if file in loosefiles.values():
            loosefiles[file.CRC].pop(loosefiles[file.CRC].index(file))
