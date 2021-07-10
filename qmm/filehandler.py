# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019-2020 bicobus <bicobus@keemail.me>
import logging
import os
import pathlib
import re
import shutil
import subprocess
from hashlib import sha256
from tempfile import TemporaryDirectory
from typing import (
    Dict,
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
from qmm.ab.archives import ABCArchiveInstance, ArchiveType
from qmm.common import bundled_tools_path, settings, settings_are_set, valid_suffixes
from qmm.config import SettingsNotSetError
from qmm.fileutils import ArchiveEvents, ignore_patterns, subfolders_of

logger = logging.getLogger(__name__)

# this shit: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfoa # noqa: E501
# Internet wisdom tells me STARTF_USESHOWWINDOW is used to hide the would be console
startupinfo = None
if is_windows:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

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


class ArchiveException(Exception):
    pass


def build_cmd(filepath, *ext, extract=True, output=None, **extra):
    ext = list(ext)
    if isinstance(filepath, os.PathLike):
        filepath = str(filepath)
    if extract:
        action = "x"
        ext.append("-y")  # Assume yes to all queries
        ext.extend(ignore_patterns(True))
    else:
        action = "l"

    ext.extend(["-scsUTF-8", "-sccUTF-8"])
    if extra.get("exclude_list"):
        ext.append(extra["exclude_list"])
    if output:
        ext.append(f"-o{output}")

    cmd = [
        bundled_tools_path(),
        action,
        filepath,
    ]
    cmd.extend(ext)
    return cmd


def extract7z(
    file_archive: pathlib.Path, output_path: pathlib.Path, exclude_list=None, progress=None,
) -> Union[List[bucket.FileMetadata], bool]:
    cmd = build_cmd(
        file_archive.absolute(),
        "-ba",
        "-bb1",
        output=output_path.absolute(),
        excluded_list=exclude_list,
    )

    logger.debug("Running %s", cmd)
    try:
        proc = subprocess.Popen(
            cmd,
            startupinfo=startupinfo,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
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
            f"{file_archive.absolute()}: Extraction failed with error code {return_code} "
            f"and message:\n{errstring}"
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
    """Return the 256 hash of the managed archive.

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


class VirtualArchiveInstance(ABCArchiveInstance):
    ar_type = ArchiveType.VIRTUAL

    def __init__(self, file_list):
        super().__init__(archive_name=b"\x00", file_list=file_list)
        print("done")

    def reset_conflicts(self):
        logger.debug("reset conflicts called on virtual")

    def matched(self):
        return

    def mismatched(self):
        return

    def missing(self):
        return

    def ignored(self):
        yield from super().ignored()

    def conflicts(self):
        yield from super().conflicts()

    def uninstall_info(self):
        logger.debug("uninstall info called on virtual")

    def install_info(self):
        logger.debug("install info called on virtual")


class ArchiveInstance(ABCArchiveInstance):
    """
    Represent an archive and its content already analyzed and ready for display.
    """

    ar_type = ArchiveType.FILE

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
            if (
                bucket.with_gamefiles(path=item.path)
                or bucket.with_gamefiles(crc=item.crc)
            ):
                tmp_conflicts.append(bucket.gamefiles[item.crc])
            if tmp_conflicts:
                self._conflicts[item.path] = tmp_conflicts

    def matched(self):
        yield from super().matched()

    def mismatched(self):
        yield from super().mismatched()

    def missing(self):
        yield from super().missing()

    def ignored(self):
        yield from super().ignored()

    def conflicts(self):
        yield from super().conflicts()

    def uninstall_info(self):
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


class ArchivesCollection(MutableMapping[str, ArchiveInstance]):
    """Manage sets of :py:class:`ArchiveInstance`."""

    def __init__(self):
        super().__init__()
        self._data: Dict[str, ArchiveInstance] = {}
        self._hashsums = {}
        self._stat = {}
        self._special = None

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
            (Union[:attr:`ArchiveEvents.FILE_ADDED`, :attr:`ArchiveEvents.FILE_REMOVED`], str):
                State and name of the file.
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
                    yield ArchiveEvents.FILE_ADDED, entry.name
                else:
                    found.append(entry.name)
        # Check for ghosts
        for key in self._data:
            if key not in found:
                logger.info("Archive removed: %s", key)
                to_delete.append(key)
                yield ArchiveEvents.FILE_REMOVED, key
        # Remove ghosts from index
        for k in to_delete:
            del self[k]
        self._special = None

    def add_archive(self, path, hashsum: str = None, progress=None):
        """Add an archive to the list of managed archives.

        This method should be used over __setitem__ as it setup the different
        metadata required by the UI.
        """
        if not isinstance(path, os.PathLike):
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
        if not isinstance(src_path, os.PathLike):
            src_path = pathlib.Path(src_path)
        if not isinstance(dest_path, os.PathLike):
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

    def diff_matched_with_loosefiles(self):
        archives = set()
        for item in self._data.values():
            archives = archives.union(set(item.matched()))

        looseset = set()
        for crclist in bucket.loosefiles.values():
            for item in crclist:
                looseset.add(item)
        self._special = VirtualArchiveInstance(looseset - archives)

    @property
    def special(self):
        if not self._special:
            logger.error(
                "Trying to access special ArchiveInstance, but it hasn't been initialized yet."
            )
        return self._special

    def initiate_conflicts_detection(self):
        for _, archive_instance in self._data.items():
            archive_instance.reset_conflicts()

    def stat(self, key):
        return self._stat[key]

    def _set_stat(self, key, value: pathlib.Path):
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
        if key == b"\x00":
            logger.info("Accessing virtual instance.")
            return self._special
        return self._data[key]

    def __setitem__(self, key: str, value: ArchiveInstance):
        if key == b"\x00":
            raise ArchiveException("Null as keyvalue is illegal.")
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
        sanitized_root = root.split(settings["game_folder"])[1]
        path = sanitized_root.partition(os.path.join(*partition) + os.path.sep)[2]

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
    # NOTE: these definitively should be moved elsewhere and be mindful of
    #  `fileutils.first_level_dir` and `fileutils.subfolder_of` as well as the
    #  game actual folder structure. Some mod sub-folders are *not* first level
    #  directories.
    scan_theses = (
        "clothing", "outfits", "tattoos", "weapons", "setBonuses", "statusEffects", "items",
        "race", "combatMove", "patterns", "colours"
    )
    if progress:
        progress("", category="Game Files")

    for p_folder in scan_theses:
        folder = os.path.join(target_folder, p_folder)
        for kfile, crc in _compute_files_crc32(folder, partition=("res",)):
            # normalize path: category/namespace/... -> namespace/category/...
            try:
                category, namespace, extra = kfile.split(os.path.sep, 2)
            except ValueError:
                # We expect a 3 parts structure, any lower and something is wrong with the game
                # files.
                logger.warning("Skipping dirty file %s", os.path.join("res", kfile))
                continue
            if category in subfolders_of["items"]:
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
    """Process an archive, verify that each of its files are unique.

    Args:
        files (:meth:`~.ArchiveInstance.files`): Process the files fed by the
            instance method.
        archives_list (:obj:`~.ArchivesCollection`): Instance of
            ArchivesCollection.
        current_archive (str): Filename on the disk of the current archive
            being processed.
        processed (list or None): List of processed archives. Set to None if only one archive
            needs to be processed.
    """
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
