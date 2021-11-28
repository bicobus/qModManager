# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

import logging
from abc import ABC, abstractmethod
from enum import IntEnum, auto, unique
from typing import Dict, Generator, Iterable, List, Tuple, Union

from qmm import bucket
from qmm.fileutils import FileState, file_status

logger = logging.getLogger(__name__)


@unique
class ArchiveType(IntEnum):
    FILE = auto()
    VIRTUAL = auto()


class ABCArchiveInstance(ABC):
    _conflicts: Dict[str, List[Union[str, bucket.FileMetadata]]]
    _meta: List[Tuple[bucket.FileMetadata, FileState]]

    ar_type = None

    def __init__(self, archive_name, file_list):
        """Inintialize needed information pertaining to an archive file.

        Args:
            archive_name (str or bytes): Name of the file. Bytes is for special cases.
            file_list (List[bucket.FileMetadata]): List of
                :py:attr:`FileMetadata` that an archive contains.
        """
        if not self.ar_type:
            raise ValueError("Object type not defined.")
        self._archive_name = archive_name
        self._file_list = file_list
        # NOTE: folders are not filtered out of meta.
        self._meta = []
        self.reset_status()
        # Contains a list of archives or, if the conflict is with a game file,
        # a FileMetadata instance.
        self._conflicts = {}

    def reset_status(self):
        """
        Called whenever the state of an archive becomes dirty, which is also
        the default state.

        Populate 'self._meta' with tuples containing the 'FileMetadata' object
        of each individual file alongside the current status of that file. The
        status can be either :py:attr:`FILE_MATCHED`, :py:attr:`FILE_MISMATCHED`,
        :py:attr:`FILE_IGNORED` or :py:attr:`FILE_MISSING`.
        """
        self._meta = []
        for item in self._file_list:
            self._meta.append((item, file_status(item)))

    @abstractmethod
    def reset_conflicts(self):
        pass

    def files(self, exclude_directories=False) -> Generator[bucket.FileMetadata, None, None]:
        if exclude_directories:
            for filename in filter(lambda x: not x.is_dir(), self._file_list):
                yield filename
        else:
            for filename in self._file_list:
                yield filename

    def folders(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield folders present in the archive."""
        for folder in filter(lambda x: x.is_dir(), sorted(self._file_list, reverse=True)):
            yield folder

    @abstractmethod
    def matched(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of matched entries of the archive."""
        for item in filter(lambda x: x[1] == FileState.MATCHED, self._meta):
            yield item[0]

    @abstractmethod
    def mismatched(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of mismatched entries of the archive."""
        if not self.has_mismatched:
            return
        for item in filter(lambda x: x[1] == FileState.MISMATCHED, self._meta):
            # File is mismatched against something else, find it and store it
            for mfile in bucket.loosefiles.values():
                for f in filter(lambda x, i=item: x.path == i[0].path, mfile):
                    logger.debug("Found mismatched as '%s'", f)
                    yield f

    @abstractmethod
    def missing(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of missing entries of the archive."""
        for item in filter(lambda x: x[1] == FileState.MISSING, self._meta):
            yield item[0]

    @abstractmethod
    def ignored(self) -> Iterable[bucket.FileMetadata]:
        """Yield file metadata of ignored entries of the archive."""
        for item in filter(lambda x: x[1] == FileState.IGNORED, self._meta):
            yield item[0]

    @abstractmethod
    def conflicts(self):
        """Yield :py:attr:`FileMetadata` of conflicting entries of the archive."""
        for path, archives in self._conflicts.items():
            yield path, archives

    @abstractmethod
    def uninstall_info(self):
        """Informations necessary to the uninstall function."""

    @abstractmethod
    def install_info(self):
        pass

    def status(self) -> Generator[Tuple[bucket.FileMetadata, int], None, None]:
        for name, status in self._meta:
            yield name, status

    def find(self, fmd: bucket.FileMetadata):
        """Return a FileMetadata object if managed by the archive.

        The comparison is done on path and crc, not origin.

        Args:
            fmd (FileMetadata): a FileMetadata object

        Returns:
            tuple: (FileMetadata, int)
        """
        if not isinstance(fmd, bucket.FileMetadata):
            raise TypeError(f"path must be FileMetadata, not {type(fmd)}")
        for item in filter(lambda x: x[0] == fmd, self._meta):
            return item
        return None

    def find_metadata_by_path(self, path):
        for item in filter(lambda x: x[0].path == path, self._meta):
            return item
        return None

    def get_status(self, file: bucket.FileMetadata) -> FileState:
        return self.find(file)[1]

    def _has_status(self, status):
        return any(x[1] == status for x in self._meta)

    @property
    def has_matched(self):
        """Return True if a file of the archive is of status :py:attr:`FILE_MATCHED`."""
        return self._has_status(FileState.MATCHED)

    @property
    def all_matching(self):
        """Return `True` if all files in the archive matches on the drive."""
        no_directory = filter(lambda x: x[0].attributes != "D", self._meta)
        return all(x[1] in (FileState.MATCHED, FileState.IGNORED) for x in no_directory)

    @property
    def has_mismatched(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_MISMATCHED`.
        """
        return self._has_status(FileState.MISMATCHED)

    @property
    def has_missing(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_MISSING`.
        """
        return self._has_status(FileState.MISSING)

    @property
    def has_ignored(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_IGNORED`.
        """
        return self._has_status(FileState.IGNORED)

    @property
    def all_ignored(self):
        """
        Value is `True` if all files of the archive are of status :py:attr:`FILE_IGNORED`.
        """
        return all(x[1] == FileState.IGNORED or x[0].attributes == "D" for x in self._meta)

    @property
    def has_conflicts(self):
        """Value is `True` if conflicts exists for this archive."""
        return bool(self._conflicts)

    @property
    def empty(self):
        """A boolean if wether the archive contains anything useful.

        list7z will return an empty list if none of the files present in the
        archive are valid. That could happen for a variety of reasons, like an
        archive containing only folders or empty files. In those cases, the
        FileState for the entries won't be set and the software won't know
        what to ignore.
        """
        return False if self._file_list else True
