# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019-2020 bicobus <bicobus@keemail.me>
import logging
import os
import pathlib
import re
import shutil
import subprocess
from functools import lru_cache
from hashlib import sha256
from tempfile import TemporaryDirectory
from typing import (
    Dict,
    Generator,
    IO,
    Iterable,
    Iterator,
    List,
    MutableMapping,
    Tuple,
    Union,
)
from zlib import crc32

from send2trash import TrashPermissionError, send2trash

from qmm import bucket, is_windows
from qmm.common import settings, settings_are_set, bundled_tools_path, valid_suffixes
from qmm.config import SettingsNotSetError

logger = logging.getLogger(__name__)

# this shit: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfoa # noqa: E501
# Internet wisdom tells me STARTF_USESHOWWINDOW is used to hide the would be console
startupinfo = None
if is_windows:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

# Mods directory structure
# TODO: add setBonuses and statusEffects as first level
first_level_dir = ("items", "outfits")  # outfits aren't stored under items
second_level_dir = ("weapons", "clothing", "tattoos")

# Regexes to capture 7z's output
reListMatch = re.compile(r"^(Path|Modified|Attributes|CRC)\s=\s(.*)$").match
reExtractMatch = re.compile(r"- (.+)$").match
reErrorMatch = re.compile(
    r"""^(
    Error:.+|
    .+\s{5}Data\sError?|
    Sub\sitems\sErrors:.+
)""",
    re.X | re.I,
).match

#: Indicate that the file is found on the drive, and match in content.
FILE_MATCHED = 1
#: Indicate that the file is absent from the drive.
FILE_MISSING = 2
#: Indicate that the file to exists on drive, but not matching in content.
FILE_MISMATCHED = 3
#: Indicate that the file will be ignored by the software.
FILE_IGNORED = 4
LITERALS = {
    FILE_MATCHED: "matched",
    FILE_MISSING: "missing",
    FILE_MISMATCHED: "mismatched",
    FILE_IGNORED: "ignored",
}
TRANSLATED_LITERALS = {
    FILE_MATCHED: _("Matched"),
    FILE_MISSING: _("Missing"),
    FILE_MISMATCHED: _("Mismatched"),
    FILE_IGNORED: _("Ignored"),
}


class FileHandlerException(Exception):
    pass


class ArchiveException(FileHandlerException):
    pass


def ignore_patterns(seven_flag=False):
    """Output a tuple of patterns to ignore.

    Args:
        seven_flag (bool): Patterns format following 7z exclude switch.
    """
    if seven_flag:
        return "-xr!*.DS_Store", "-x!__MACOSX", "-xr!*Thumbs.db"
    return ".DS_Store", "__MACOSX", "Thumbs.db"


def extract7z(
    file_archive: pathlib.Path, output_path: pathlib.Path, exclude_list=None, progress=None,
) -> Union[List[bucket.FileMetadata], bool]:
    filepath = file_archive.absolute()
    output_path = output_path.absolute()
    cmd = [
        bundled_tools_path(),
        "x",
        str(filepath),
        f"-o{output_path}",
        "-ba",
        "-bb1",
        "-y",
        "-scsUTF-8",
        "-sccUTF-8",
    ]
    cmd.extend(ignore_patterns(True))
    if exclude_list:
        assert isinstance(exclude_list, list)
        cmd.extend(exclude_list)

    logger.debug("Running %s", cmd)
    try:
        proc = subprocess.Popen(
            cmd,
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as e:
        logger.error("System error\n%s", e)
        return False

    f_list: List[bucket.FileMetadata] = []
    errstring = ""
    with proc.stdout as out:
        for line in iter(out.readline, b""):
            line = line.decode("utf-8")

            err = reErrorMatch(line)
            if err:
                errstring = line + b"".join(out).decode("utf-8")
                break

            extract = reExtractMatch(line)
            if extract:
                logger.info("Extracting %s", line.strip())
                path = extract.group(1).strip()
                f_list.append(
                    bucket.FileMetadata(
                        attributes="", path=path, crc=0, modified="", isfrom=file_archive.name,
                    )
                )
                if progress:
                    progress(f"Extracting {path}...")

    return_code = proc.wait()
    if return_code != 0 or errstring:
        raise ArchiveException(
            (
                f"{filepath}: Extraction failed with error code {return_code} "
                f"and message:\n{errstring}"
            )
        )

    return f_list


def list7z(file_path: Union[str, pathlib.Path], progress=None) -> List[bucket.FileMetadata]:
    if not isinstance(file_path, pathlib.Path):
        file_path = pathlib.Path(file_path)
    if not file_path.exists():
        raise ArchiveException(f"{file_path} couldn't be found.")

    model = {
        "path": "",
        "modified": "",
        "attributes": "",
        "crc": 0,
        "isfrom": file_path.name,
    }

    if progress:
        progress(f"Processing {file_path.as_posix()}...")

    cmd = [bundled_tools_path(), "l", str(file_path), "-ba", "-scsUTF-8", "-sccUTF-8", "-slt"]

    proc = subprocess.Popen(
        cmd,
        startupinfo=startupinfo,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    f_list: List[bucket.FileMetadata] = []
    err_string = ""
    with proc.stdout as out:
        for line in iter(out.readline, b""):
            line = line.decode("utf-8")

            err_data = reErrorMatch(line)
            if err_data:
                err_string = line + b"".join(out).decode("utf-8")
                break

            file_data = reListMatch(line)
            if file_data:
                fdg = file_data.group(1).strip()
                if fdg == "Path":
                    tmp_data = model.copy()
                if fdg in ("Path", "Modified", "Attributes", "CRC"):
                    tmp_data[fdg.lower()] = file_data.group(2).strip()
                if fdg == "CRC":
                    if "D" not in tmp_data["attributes"]:
                        tmp_data[fdg.lower()] = int(tmp_data[fdg.lower()], 16)
                    f_list.append(bucket.FileMetadata(**tmp_data))

    return_code = proc.wait()
    if return_code != 0 or err_string:
        raise ArchiveException(
            (
                f"{file_path}: listing failed with error code {return_code} "
                f"and message:\n{err_string}"
            )
        )

    return f_list


def sha256hash(filename: Union[IO, str]) -> Union[str, None]:
    """Returns the 256 hash of the managed archive.

    Args:
        filename: path to the file to hash

    Returns:
        str or None: a string if successful, otherwise None
    """
    try:
        if hasattr(filename, "read"):
            result = sha256(filename.read()).hexdigest()
        else:
            with open(filename, "rb") as fp:
                result = sha256(fp.read()).hexdigest()
    except OSError as e:
        logger.exception(e)
        result = None

    return result


class ArchiveInstance:
    """Represent an archive and its content already analyzed and ready for
    display."""

    _conflicts: Dict[str, List[Union[str, bucket.FileMetadata]]]
    _meta: List[Tuple[bucket.FileMetadata, int]]

    def __init__(self, archive_name: str, file_list: List[bucket.FileMetadata]):
        self._archive_name = archive_name
        self._file_list = file_list
        # Note: folders are not filtered out of meta.
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
        status can be either 'FILE_MATCHED', 'FILE_MISMATCHED', 'FILE_IGNORED'
        or 'FILE_MISSING'.
        """
        self._meta = []
        for item in self._file_list:
            self._meta.append((item, file_status(item)))

    def reset_conflicts(self):
        """
        Generate a list of conflicting files, either from in the game folders
        or in other archives, for each file present in this archive.
        """
        for item in self._file_list:
            tmp_conflicts = []
            # Check other archives
            if bucket.with_conflict(item.path):
                tmp_conflicts.extend(bucket.conflicts[item.path])
            # Check against game files (Path and CRC)
            # fmt: off
            if (
                bucket.with_gamefiles(path=item.path)
                or bucket.with_gamefiles(crc=item.crc)
            ):
                tmp_conflicts.append(bucket.gamefiles[item.crc])
            # fmt: on
            if tmp_conflicts:
                self._conflicts[item.path] = tmp_conflicts

    def status(self) -> Generator[Tuple[bucket.FileMetadata, int], None, None]:
        for name, status in self._meta:
            yield name, status

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

    def matched(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of matched entries of the archive."""
        for item in filter(lambda x: x[1] == FILE_MATCHED, self._meta):
            yield item[0]

    def mismatched(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of mismatched entries of the archive."""
        if not self.has_mismatched:
            return
        for item in filter(lambda x: x[1] == FILE_MISMATCHED, self._meta):
            # File is mismatched against something else, find it and store it
            for mfile in bucket.loosefiles.values():
                for f in filter(lambda x: x.path == item[0].path, mfile):
                    logger.debug("Found mismatched as '%s'", f)
                    yield f

    def missing(self) -> Generator[bucket.FileMetadata, None, None]:
        """Yield file metadata of missing entries of the archive."""
        for item in filter(lambda x: x[1] == FILE_MISSING, self._meta):
            yield item[0]

    def ignored(self) -> Iterable[bucket.FileMetadata]:
        """Yield file metadata of ignored entries of the archive."""
        for item in filter(lambda x: x[1] == FILE_IGNORED, self._meta):
            yield item[0]

    def conflicts(self):
        """Yield file metadata of conflicting entries of the archive."""
        for path, archives in self._conflicts.items():
            yield path, archives

    def uninstall_info(self):
        """Informations necessary to the uninstall function."""
        return list(self.matched()) + list(self.folders())

    def install_info(self):
        """Return a several lists useful to the installation process.

        The content in matched and ignored key will be compiled into a set of
        exclude flags, whereas the content of mismatched key will be overridden.

        See Also:
            :func:`install_archive`
        """
        return {
            "matched": list(self.matched()),
            "mismatched": list(self.mismatched()),
            "ignored": list(self.ignored()),
        }

    def find(self, path):
        for item in filter(lambda x: x[0].path == path, self._meta):
            return item
        return None

    def get_status(self, file):
        return self.find(file)[1]

    def _has_status(self, status):
        return any(x[1] == status for x in self._meta)

    @property
    def has_matched(self):
        """Return True if a file of the archive is of status :py:attr:`FILE_MATCHED`."""
        return self._has_status(FILE_MATCHED)

    @property
    def all_matching(self):
        """Return `True` if all files in the archive matches on the drive."""
        no_directory = filter(lambda x: x[0].attributes != "D", self._meta)
        return all(x[1] in (FILE_MATCHED, FILE_IGNORED) for x in no_directory)

    @property
    def has_mismatched(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_MISMATCHED`.
        """
        return self._has_status(FILE_MISMATCHED)

    @property
    def has_missing(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_MISSING`.
        """
        return self._has_status(FILE_MISSING)

    @property
    def has_ignored(self):
        """
        Value is `True` if a file of the archive is of status :py:attr:`FILE_IGNORED`.
        """
        return self._has_status(FILE_IGNORED)

    @property
    def all_ignored(self):
        """
        Value is `True` if all files of the archive are of status :py:attr:`FILE_IGNORED`.
        """
        return all(x[1] == FILE_IGNORED or x[0].attributes == "D" for x in self._meta)

    @property
    def has_conflicts(self):
        """Value is `True` if conflicts exists for this archive."""
        return bool(self._conflicts)


class ArchivesCollection(MutableMapping[str, ArchiveInstance]):
    #: State of a file yielded through :meth:`refresh`
    FileAdded = 1
    #: State of a file yielded through :meth:`refresh`
    FileRemoved = 2

    def __init__(self):
        super().__init__()
        self._data: Dict[str, ArchiveInstance] = {}
        self._hashsums = {}
        self._stat = {}

    def build_archives_list(self, progress, rebuild=False):
        if not settings_are_set():
            raise SettingsNotSetError()

        if self._data and not rebuild:
            return False

        repo = pathlib.Path(settings["local_repository"])
        for entry in repo.glob("*.*"):
            if entry.is_file() and entry.suffix in valid_suffixes("pathlib"):
                self.add_archive(entry, progress=progress)
            else:
                logger.warning("File with suffix '%s' ignored.", entry.suffix)
        return True

    def refresh(self) -> Iterable[Tuple[int, str]]:
        """Scan the local repository to add or remove archives as needed.

        This is a companion method to use with WatchDog whenever something
        changes on the filesystem.

        Yields:
            (Union[:attr:`FileAdded`, :attr:`FileRemoved`], str): State and name of
                the file
        """
        if not settings_are_set():
            return

        found, to_delete = [], []
        repo = pathlib.Path(settings["local_repository"])
        for entry in repo.glob("*.*"):
            if entry.is_file() and entry.suffix in valid_suffixes("pathlib"):
                if not self.find(archive_name=entry.name):
                    logger.info("Found new archive: %s", entry.name)
                    self.add_archive(entry)
                    found.append(entry.name)
                    yield self.FileAdded, entry.name
                else:
                    found.append(entry.name)
        # Check for ghosts
        for key in self._data:
            if key not in found:
                logger.info("Archive removed: %s", key)
                to_delete.append(key)
                yield self.FileRemoved, key
        # Remove ghosts from index
        for k in to_delete:
            del self[k]

    def add_archive(self, path, hashsum: str = None, progress=None):
        """Add an archive to the list of managed archives.

        This method should be used over __setitem__ as it setup the different
        metadata required by the UI.
        """
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(settings["local_repository"], path)
        if not path.is_file():
            return
        if not hashsum:
            hashsum = sha256hash(path)
        self[path.name] = ArchiveInstance(path.name, list7z(path, progress))
        self._set_stat(path.name, path)
        self._set_hashsums(path.name, hashsum)

    def rename_archive(self, src_path, dest_path):
        """Rename the key pointing to an archive.

        Whenever an archive on the drive gets renamed, we need to do the same
        with the key under which the parsed data is stored.
        """
        if not isinstance(src_path, pathlib.Path):
            src_path = pathlib.Path(src_path)
        if not isinstance(dest_path, pathlib.Path):
            dest_path = pathlib.Path(dest_path)
        if src_path.name in self._data and dest_path.name not in self._data:
            self._data[dest_path.name] = self._data[src_path.name]
            del self._data[src_path.name]
            return True
        return False

    def find(self, archive_name: str = None, hashsum: str = None):
        """Find a member based on the name or hashsum of the archive.

        If archiveName is not None, will check if archiveName exists in the
        keys of the collection. If hashsum is not None, will check if the value
        exists in the self._hashsums dict. If all checks fails, returns False.

        Args:
            archive_name: filename of the archive, suffix included (default None)
            hashsum: sha256sum of the file (default None)
        Returns:
            Boolean or ArchiveInstance
        """
        if archive_name and archive_name in self._data.keys():
            return self._data[archive_name]
        if hashsum and hashsum in self._hashsums.values():
            for key, item in self._hashsums.items():
                if item == hashsum:
                    return self._data[key]
        return False

    def initiate_conflicts_detection(self):
        for _, archive_instance in self._data.items():
            archive_instance.reset_conflicts()

    def stat(self, key):
        return self._stat[key]

    def _set_stat(self, key, value):
        assert isinstance(value, pathlib.Path)
        self._stat[key] = value.stat()

    def hashsums(self, key):
        return self._hashsums[key]

    def _set_hashsums(self, key, value):
        self._hashsums[key] = value

    def __len__(self):
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __getitem__(self, key) -> ArchiveInstance:
        return self._data[key]

    def __setitem__(self, key: str, value: ArchiveInstance):
        if key not in self._data or self._data[key] != value:
            assert isinstance(value, ArchiveInstance), type(value)
            assert all(isinstance(x, bucket.FileMetadata) for x in value.files())
            self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]
        del self._stat[key]
        del self._hashsums[key]


def _ignored_part_in_path(path):
    for item in path:
        if item in ignore_patterns():
            return True
    return False


def get_mod_folder(with_file: str = None, prepend_modpath=False) -> pathlib.Path:
    """Return the path to the game folder.

    Args:
        with_file: append 'with_file' to the path
        prepend_modpath: if True, adds the module path before 'with_file'

    Returns:
        PathLike structure representing the game folder.
    """
    path = [settings["game_folder"]]
    if prepend_modpath:
        path.extend(["res", "mods"])
    if with_file:
        path.append(with_file)
    return pathlib.Path(*path)


def _crc32(filename: Union[IO, str, os.PathLike]) -> Union[bucket.Crc32, None]:
    """Returns the CRC32 hash of the given filename.

    Args:
        filename: path to the file to hash

    Returns:
         str or None: a string if successful, None otherwise
    """
    try:
        if hasattr(filename, "read"):
            result = crc32(filename.read())
        else:
            with open(filename, "rb") as fp:
                result = crc32(fp.read())
    except OSError as e:
        logger.exception(e)
        result = None

    return result


def _compute_files_crc32(
    folder, partition=("res", "mods")
) -> Tuple[pathlib.PurePath, bucket.Crc32]:
    for root, _, files in os.walk(folder):
        if not files:
            continue
        # We want to build a path that is similar to the one present in an
        # archive. To do so we need to remove anything that is before, and
        # including the "partition" folder.
        # ...blah/res/mods/namespace/category/ -> namespace/category/
        path = root.partition(os.path.join(*partition) + os.path.sep)[2]

        for file in files:
            kfile = pathlib.PurePath(path, file)
            with pathlib.Path(root, file).open("rb") as fp:
                yield str(kfile), _crc32(fp)


def build_game_files_crc32(progress=None):
    """Compute the CRC32 value of all the game files then add them to a bucket.

    The paths returned by this function are non-existent due to a difference
    between the mods and the game folder structure. It is needed to be that way
    in order to compare the mod files with the existing game files.

    Args:
        progress (:meth:`~.dialogs.SplashProgress.progress`):
            Callback to a method accepting strings as argument.
    """
    target_folder = os.path.join(settings["game_folder"], "res")
    scan_theses = ("clothing", "outfits", "tattoos", "weapons")
    if progress:
        progress("", category="Game Files")

    for p_folder in scan_theses:
        folder = os.path.join(target_folder, p_folder)
        for kfile, crc in _compute_files_crc32(folder, partition=("res",)):
            # normalize path: category/namespace/... -> namespace/category/...
            category, namespace, extra = kfile.split(os.path.sep, 2)
            if category in ("clothing", "weapons", "tattoos"):
                kfile = pathlib.PurePath(namespace, "items", category, extra)
            else:
                kfile = pathlib.PurePath(namespace, category, extra)
            if progress:
                progress(f"Computing {kfile}...")
            bucket.as_gamefile(crc, kfile)


def build_loose_files_crc32(progress=None):
    """Build the CRC32 value of all loose files.

    Args:
        progress (:meth:`~.dialogs.SplashProgress.progress`):
            Callback to a method accepting strings as argument.

    """
    if progress:
        progress("", category="Loose Files")
    mod_folder = get_mod_folder(prepend_modpath=True)
    for kfile, crc in _compute_files_crc32(mod_folder):
        if progress:
            progress(f"Computing {kfile}...")
        bucket.as_loosefile(crc, kfile)


def _filter_list_on_exclude(archives_list, list_to_exclude) -> Tuple[str, ArchiveInstance]:
    for archive_name, file_info in archives_list.items():
        if not list_to_exclude or archive_name not in list_to_exclude:
            yield archive_name, file_info


def file_in_other_archives(
    file: bucket.FileMetadata, archives: ArchivesCollection, ignore: List
) -> List:
    """Search for existence of file in other archives.

    Args:
        file (FileMetadata):
            file to be found
        archives (ArchivesCollection):
            instance of ArchivesCollection
        ignore (list):
            list of archives to ignore, for example already parsed archives

    Returns:
        List: List of archives containing the same file.
    """
    found = []
    for archive_name, items in _filter_list_on_exclude(archives, ignore):
        for crc, other_file_path in map(lambda v: (v.crc, v.path), items.files()):
            if not file.is_dir() and file.path == other_file_path and file.crc != crc:
                found.append(archive_name)

    return found


def conflicts_process_files(files, archives_list, current_archive, processed):
    """Process an archive, verify that each of its files are unique."""
    for file in files():
        if bucket.with_conflict(file.path):
            continue

        bad_archives = file_in_other_archives(file=file, archives=archives_list, ignore=processed)

        if bad_archives:
            bad_archives.append(current_archive)
            bucket.as_conflict(file.path, bad_archives)


def generate_conflicts_between_archives(archives_lists: ArchivesCollection, progress=None):
    assert isinstance(archives_lists, ArchivesCollection), type(archives_lists)
    list_done: List[str] = []
    # archive_content is a list of objects [FileMetadata, FileMetadata, ...]
    for archive_name, archive_content in archives_lists.items():
        if progress:
            progress(archive_name)
        conflicts_process_files(
            files=archive_content.files,
            archives_list=archives_lists,
            current_archive=archive_name,
            processed=list_done,
        )
        list_done.append(archive_name)


@lru_cache(maxsize=None)
def _bad_directory_structure(path: pathlib.Path):
    if len(path.parts) > 1 and not any(path.parts[1] == x for x in first_level_dir):
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
    if bucket.file_crc_in_loosefiles(file) and bucket.file_path_in_loosefiles(file):
        return FILE_MATCHED
    if bucket.file_path_in_loosefiles(file) and not bucket.file_crc_in_loosefiles(file):
        return FILE_MISMATCHED
    return FILE_MISSING


def copy_archive_to_repository(filename):
    """Copy an archive to the manager's repository."""
    if not settings["local_repository"]:
        logger.warning("Unable to copy archive: no local repository configured.")
        return False

    new_filename = os.path.join(settings["local_repository"], os.path.basename(filename))

    if os.path.exists(new_filename):
        logger.error("Unable to copy archive, a file with a similar name already exists.")
        return False

    try:
        if not os.path.exists(settings["local_repository"]):
            os.makedirs(settings["local_repository"])
        shutil.copy(filename, settings["local_repository"])
    except IOError as e:
        logger.error("Error copying archive: %s", e)
        return False
    else:
        return os.path.basename(new_filename)


def install_archive(
    file_to_extract: str, file_context: Dict[str, List[bucket.FileMetadata]]
) -> Union[bool, List[bucket.FileMetadata]]:
    """Install the content of an archive into the game mod folder.

    Args:
        file_to_extract (str): path to the archive to extract.
        file_context (dict): A dict containing the keys `matched`, `mismatched`,
            `ignored`. Each of these entries point to a list containing
            :obj:`FileMetadata <qmm.bucket.FileMetadata>` objects.

            The content in matched and ignored key will be compiled into a set
            of exclude flags, whereas the content of mismatched key will be
            overridden. See :meth:`ArchiveInstance.install_info`

    Returns:
        Output of function :func:`extract7z` or :py:data:`False`
    """
    if not settings["game_folder"]:
        logger.warning("Unable to unpack archive: game location is unknown.")
        return False

    file_to_extract = pathlib.Path(settings["local_repository"], file_to_extract)
    ignore_list = [
        "-x!{}".format(filemd.path)
        for filemd in file_context["ignored"] + file_context["matched"]
    ]

    try:
        with TemporaryDirectory(prefix="qmm-") as td:
            logger.debug("Extracting files to %s", td)
            files = extract7z(file_to_extract, pathlib.Path(td), exclude_list=ignore_list)
            if not files:
                logger.error("Exctracted list is empty, something terrible happened.")
            for myfile in files:
                src = pathlib.Path(td, myfile.path)
                if src.is_dir():
                    logger.debug("IGNORED %s", src.as_posix())
                    continue
                dst = get_mod_folder(myfile.path, prepend_modpath=True)
                os.makedirs(os.path.dirname(dst), mode=0o750, exist_ok=True)
                shutil.copy2(src, dst)
                ccrc = _crc32(dst)
                bucket.as_loosefile(ccrc, myfile.path)
                logger.debug("INSTALLED [loose] (%s) %s", ccrc, src.as_posix())
            for misfile in file_context["mismatched"]:
                logger.debug("STATE removed from loose files (%s) %s", misfile.crc, misfile.path)
                bucket.remove_item_from_loosefiles(misfile)
    except ArchiveException as e:
        logger.exception(e)
        return False
    except OSError as e:
        logger.exception(e)
        return False
    else:
        logger.info("Installed archive %s", file_to_extract)
    return files


def uninstall_files(file_list: List[bucket.FileMetadata]):
    """Removes a list of files and directory from the filesystem.

    Args:
        file_list (list[FileMetadata]): A list of
            :obj:`FileMetadata <qmm.bucket.FileMetadata>` objects.

    Returns:
        bool: :py:data:`True` on success, :py:data:`False` if an error occurred
        during the deleting process.

    Notes:
        Any error will be logged silently to the application configured
        facility.
    """
    dlist = []
    success = True
    for item in file_list:
        assert isinstance(item, bucket.FileMetadata)
        file = item.pathobj
        logger.debug("Trying to delete file: %s", file)
        if not file.is_dir():
            try:
                file.unlink()
                bucket.remove_item_from_loosefiles(item)
            except OSError as e:
                if e.errno == 39:  # Folder non-empty
                    logger.warning(e.strerror)
                else:
                    logger.error("Unable to remove file %s: %s", file, e)
                    success = False
            else:
                logger.debug("File unlinked: %s", file)
        else:
            dlist.append(file)

    dlist.sort(reverse=True)  # list of strings, longest first
    for directory in dlist:
        try:
            directory.rmdir()
        except OSError as e:  # Probably due to not being empty
            logger.error("Unable to remove directory %s: %s", directory, e)
            # Not raising the exception, non-empty folders might belong to
            # other mods or be intentionally present through external
            # intervention.
        else:
            logger.debug("Directory removed: %s", directory)

    return success


def delete_archive(filepath):
    """Delete an archive from the filesystem."""
    # Assume filepath to only be a filename
    if not isinstance(filepath, pathlib.Path):
        filepath = pathlib.Path(settings["local_repository"], filepath)

    try:
        send2trash(filepath)
    except TrashPermissionError as e:
        logger.error("Unable to move file %s to trash:\n%s", filepath, e)
        return False
    except OSError as e:
        logger.error("An error occured outside of send2trash for file %s:\n%s", filepath, e)
        return False
    else:
        logger.info("Moved file %s to trashbin.", filepath.as_posix())
    return True
