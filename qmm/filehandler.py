# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
import shutil
import subprocess
import re
import pathlib

from typing import Type, List, Tuple
from functools import lru_cache
from zlib import crc32
from hashlib import sha256
from collections.abc import MutableMapping
from tempfile import TemporaryDirectory

from . import FileMetadata
from . import bucket
from . import is_windows
from .common import tools_path, settings, settings_are_set
logger = logging.getLogger(__name__)

# this shit: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfoa
# Internet wisdom tells me STARTF_USESHOWWINDOW is used to hide the would be console
startupinfo = None
if is_windows:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    pathObject: Type[pathlib.PurePath] = pathlib.PureWindowsPath
else:
    pathObject: Type[pathlib.PurePath] = pathlib.PurePosixPath

# Mods directory structure
first_level_dir = ('items', 'outfits')  # outfits aren't supported in mods
second_level_dir = ('weapons', 'clothing', 'tattoos')
# --
reListMatch = re.compile(
    r"""^(Path|Modified|Attributes|CRC)\s=\s(.*)$""").match
reExtractMatch = re.compile(r'- (.+)$').match
reErrorMatch = re.compile(r"""^(
    Error:.+|
    .+\s{5}Data\sError?|
    Sub\sitems\sErrors:.+
)""", re.X | re.I).match


class FileHandlerException(Exception):
    pass


class ArchiveException(FileHandlerException):
    pass


def ignore_patterns(seven_flag=False):
    if seven_flag:
        return '-xr!*.DS_Store', '-x!__MACOSX', '-xr!*Thumbs.db'
    return '.DS_Store', '__MACOSX', 'Thumbs.db'


def extract7z(file_archive: pathlib.Path,
              output_path: pathlib.Path,
              exclude_list=None,
              progress=None):
    filepath = file_archive.absolute()
    output_path = output_path.absolute()
    cmd = [
        tools_path(), 'x', f'{filepath}', f'-o{output_path}',
        '-ba', '-bb1', '-y', '-scsUTF-8', '-sccUTF-8'
    ]
    cmd.extend(ignore_patterns(True))
    if exclude_list:
        assert isinstance(exclude_list, list)
        cmd.extend(exclude_list)

    proc = subprocess.Popen(
        cmd, startupinfo=startupinfo, stdout=subprocess.PIPE,
        stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    f_list: List[FileMetadata] = []
    errstring = ""
    with proc.stdout as out:
        for line in iter(out.readline, b''):
            line = line.decode('utf-8')

            err = reErrorMatch(line)
            if err:
                errstring = line + b''.join(out).decode("utf-8")
                break

            extract = reExtractMatch(line)
            if extract:
                path = extract.group(1).strip()
                f_list.append(FileMetadata(Attributes="", Path=path,
                                           CRC=0, Modified=""))
                if progress:
                    progress(f'Extracting {path}...')

    return_code = proc.wait()
    if return_code != 0 or errstring:
        raise ArchiveException((
            f"{filepath}: Extraction failed with error code {return_code} "
            f"and message:\n{errstring}"))

    return f_list


def list7z(file_path, progress=None) -> List[FileMetadata]:
    file_path = os.path.abspath(file_path)

    if progress:
        progress(f'Processing {file_path}...')

    cmd = [
        tools_path(), 'l', f'{file_path}',
        '-ba', '-scsUTF-8', '-sccUTF-8', '-slt'
    ]

    proc = subprocess.Popen(
        cmd, startupinfo=startupinfo, stdout=subprocess.PIPE,
        stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    f_list: List[FileMetadata] = []
    model = {
        'Path': "",
        'Modified': "",
        'Attributes': "",
        'CRC': 0
    }
    err_string = ""
    with proc.stdout as out:
        for line in iter(out.readline, b''):
            line = line.decode('utf-8')

            err_data = reErrorMatch(line)
            if err_data:
                err_string = line + b''.join(out).decode('utf-8')
                break

            file_data = reListMatch(line)
            if file_data:
                fdg = file_data.group(1).strip()
                if fdg == 'Path':
                    tmp_data = model.copy()
                if fdg in ('Path', 'Modified', 'Attributes', 'CRC'):
                    tmp_data[fdg] = file_data.group(2).strip()
                if fdg == 'CRC':
                    if 'D' not in tmp_data['Attributes']:
                        tmp_data[fdg] = int(tmp_data[fdg], 16)
                    f_list.append(FileMetadata(**tmp_data))

    return_code = proc.wait()
    if return_code != 0 or err_string:
        raise ArchiveException((
            f"{file_path}: listing failed with error code {return_code} "
            f"and message:\n{err_string}"))

    return f_list


def sha256hash(filename):
    """Returns the 256 hash of the managed archive.

    Args:
        filename: path to the file to hash

    Returns:
        string: if successful
        None: if not successful
    """
    try:
        if hasattr(filename, 'read'):
            result = sha256(filename.read).hexdigest()
        else:
            with open(filename, 'rb') as fp:
                result = sha256(fp.read()).hexdigest()
    except OSError as e:
        logger.exception(e)
        result = None

    return result


class ArchivesCollection(MutableMapping):
    def __init__(self):
        super().__init__()
        self._data = {}
        self._hashsums = {}
        self._stat = {}

    def build_archives_list(self, progress, rebuild=False):
        if not settings_are_set:
            return False

        if self._data and not rebuild:
            return False

        suffixes = ['.rar', '.zip', '.7z']
        repo = pathlib.Path(settings['local_repository'])
        for entry in repo.glob("*.*"):
            if entry.is_file() and entry.suffix in suffixes:
                self.add_archive(entry, progress=progress)
            else:
                print(entry.suffix)

    def add_archive(self, path, hashsum=None, progress=None):
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(settings['local_repository'], path)
        if not path.is_file():
            return
        if not hashsum:
            hashsum = sha256hash(path)
        self[path.name] = list7z(path, progress)
        self._set_stat(path.name, path)
        self._set_hashsums(path.name, hashsum)

    def find(self, archive_name=None, hashsum=None):
        """Try to find a member, then returns its object, either through the name
        of the archive and/or the sha256sum of the file.

        If archiveName is not None, will check if archiveName exists in the
        keys of the collection.
        If hashsum is not None, will check if the value exists in the
        self._hashsums dict.
        If all checks fails, returns False.

        Args:
            archive_name: filename of the archive, suffix included (default None)
            hashsum: sha256sum of the file (default None)
        """
        if archive_name and archive_name in self._data.keys():
            return self._data[archive_name]
        if hashsum and hashsum in self._hashsums.values():
            for key, item in self._hashsums.items():
                if item == hashsum:
                    return self._data[key]
        return False

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

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if key not in self._data or self._data[key] != value:
            assert isinstance(value, list), type(value)
            assert all(isinstance(x, FileMetadata) for x in value)
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


def _get_mod_folder(with_file=None, prepend_modpath=False) -> pathlib.Path():
    path = [settings['game_folder']]
    if prepend_modpath:
        path.extend(['res', 'mods'])
    if with_file:
        path.append(with_file)
    return pathlib.Path(*path)


def _crc32(filename) -> int:
    """Returns the CRC32 hash of the given filename.

    Args:
        filename: path to the file to hash

    Returns:
        string: if successful
        None: if not successful
    """
    try:
        if hasattr(filename, 'read'):
            result = crc32(filename.read())
        else:
            with open(filename, 'rb') as fp:
                result = crc32(fp.read())
    except OSError as e:
        logger.exception(e)
        result = None

    return result


def _compute_files_crc32(folder, partition=('res', 'mods')):
    root: str
    for root, _, files in os.walk(folder):
        if not files:
            continue
        # We want to build a path that is similar to the one present in an
        # archive. To do so we need to remove anything that is before, and
        # including the "partition" folder.
        path = root.partition(os.path.join(*partition) + os.path.sep)[2]

        for file in files:
            key = pathObject(path, file).as_posix()
            with open(os.path.join(root, file), 'rb') as fp:
                yield key, _crc32(fp)


def build_game_files_crc32(progress=None):
    """Compute the CRC32 value of all the game files then add them to a bucket

    The paths returned by this function are non-existent due to a difference
    between the mods and the game folder structure. It is needed to be that way
    in order to compare the mod files with the existing game files.

    Args:
        progress (dialogs.qProgress.progress): Callback to a method accepting strings as argument.
    """
    target_folder = os.path.join(settings['game_folder'], 'res')
    scan_theses = ('clothing', 'outfits', 'tattoos', 'weapons')

    for p_folder in scan_theses:
        folder = os.path.join(target_folder, p_folder)
        for key, crc in _compute_files_crc32(folder, partition=('res',)):
            # normalize path: category/namespace/... -> namespace/category/...
            k_parts = key.split(os.path.sep)
            n_parts = []
            category = k_parts.pop(0)  # category
            namespace = k_parts.pop(0)  # namespace
            # Those are under the 'items' folder: namespace/items/category/...
            if category in ('clothing', 'weapons', 'tattoos'):
                n_parts.extend([namespace, 'items'])
            else:
                n_parts.append(namespace)
            n_parts.append(category)
            n_parts.extend(k_parts)
            key = os.path.join(*n_parts)
            progress(f"Computing {key}...")
            bucket.as_gamefile(crc, key)


# Returns a dict indexed on the files
def build_loose_files_crc32(progress=None):
    """
    Build the CRC32 value of all loose files
    Args:
        progress: Callback to a method accepting strings as argument.

    Returns:
        None

    """
    mod_folder = _get_mod_folder(prepend_modpath=True)
    for key, crc in _compute_files_crc32(mod_folder):
        progress(f"Computing {key}...")
        bucket.as_loosefile(crc, key)


def _filter_list_on_exclude(archives_list, list_to_exclude):
    for archive_name, items in archives_list.items():
        if not list_to_exclude or archive_name not in list_to_exclude:
            yield archive_name, items


def file_in_other_archives(file, archives, ignore):
    """Returns a list of archives in which file is found if the number of said
    archive is above 1. Otherwise returns False.
    Args:
        file (FileMetadata): file to be found
        archives (ArchivesCollection): instance of ArchivesCollections
        ignore (list): list of archives to ignore, for instance already parsed archives

    Returns:
        List: List of archives containing the same file.
    """
    def _ofile(v):
        return v.CRC, v.Path

    found = []
    for ck, items in _filter_list_on_exclude(archives, ignore):
        for crc, other_file_path in map(_ofile, items):
            if ('D' not in file.Attributes
                    and file.Path == other_file_path
                    and file.CRC != crc):
                found.append(ck)

    return found


def conflicts_process_files(files, archives_list, current_archive, processed):
    for file in files:
        if bucket.with_loosefiles(crc=file.CRC):
            bucket.as_loose_conflicts(file)

        if bucket.with_conflict(file.Path):
            continue

        bad_archives = file_in_other_archives(
            file=file,
            archives=archives_list,
            ignore=processed)

        if bad_archives:
            bad_archives.append(current_archive)
            bucket.as_conflict(file.Path, bad_archives)


def detect_conflicts_between_archives(archives_lists: ArchivesCollection):
    assert isinstance(archives_lists, ArchivesCollection), type(archives_lists)
    list_done = []  # (sha256, filepath) of already processed archives
    for archive_name, archive_content in archives_lists.items():
        conflicts_process_files(archive_content, archives_lists, archive_name, list_done)
        list_done.append(archive_name)


FILE_MATCHED = 1
FILE_MISSING = 2
FILE_MISMATCHED = 3
FILE_IGNORED = 4


@lru_cache(maxsize=None)
def _bad_directory_structure(path):
    if len(path.parts) > 1 and not any(path.parts[1] == x for x in first_level_dir):
        return True
    return False


@lru_cache(maxsize=None)
def _bad_suffix(suffix):
    return bool(suffix not in ('.xml', '.svg'))


def file_status(file: FileMetadata) -> int:
    path = pathObject(file.Path)
    if (path.name in ignore_patterns()
            or _bad_directory_structure(path)
            or (path.suffix and _bad_suffix(path.suffix))):
        return FILE_IGNORED
    if (bucket.with_loosefiles(crc=file.CRC)
            and bucket.with_loosefiles(path=file.Path)):
        return FILE_MATCHED
    if (any(file.Path in v for v in bucket.loosefiles.values())
            and not bucket.with_loosefiles(crc=file.CRC)):
        return FILE_MISMATCHED
    return FILE_MISSING


def missing_matched_mismatched(file_list: List[FileMetadata]) -> List[Tuple[FileMetadata, int]]:
    new_list = []
    for file in file_list:
        new_list.append((file, file_status(file)))
    return new_list


def copy_archive_to_repository(filename):
    """Copy an archive to the manager's repository"""
    if not settings['local_repository']:
        logger.warning("Unable to copy archive: no local repository configured.")
        return False

    new_filename = os.path.join(
        settings['local_repository'],
        os.path.basename(filename)
    )

    if os.path.exists(new_filename):
        logger.error(
            "Unable to copy archive, a file with a similar name already exists.")
        return False

    try:
        if not os.path.exists(settings['local_repository']):
            os.makedirs(settings['local_repository'])
        shutil.copy(filename, settings['local_repository'])
    except IOError as e:
        logger.error("Error copying archive: %s", e)
        return False
    else:
        return os.path.basename(new_filename)


def install_archive(file_to_extract, ignore_list):
    """Install the content of an archive into the game mod folder."""
    if not settings['game_folder']:
        logger.warning("Unable to unpack archive: game location is unknown.")
        return False

    file_to_extract = pathlib.Path(settings['local_repository'], file_to_extract)
    ignore_list = ["-x!{}".format(path.Path) for path in ignore_list]

    try:
        with TemporaryDirectory(prefix="qmm-") as td:
            files = extract7z(file_to_extract, pathlib.Path(td), exclude_list=ignore_list)
            for file in files:
                src = pathlib.Path(td, file.Path)
                if src.is_dir():
                    continue
                dst = _get_mod_folder(file.Path, prepend_modpath=True)
                os.makedirs(os.path.dirname(dst), mode=0o750, exist_ok=True)
                shutil.copy2(src, dst)
                bucket.as_loosefile(_crc32(dst), file.Path)
    except ArchiveException as e:
        logger.exception(e)
        return False
    except OSError as e:
        logger.exception(e)
        return False
    return files


def uninstall_files(file_list: list):
    """Removes a list of files and directory from the filesystem."""
    dlist = []
    success = True
    for item in file_list:
        assert isinstance(item, FileMetadata)
        file = _get_mod_folder(item.Path, prepend_modpath=True)
        logger.debug("Trying to delete file: %s", file)
        if not file.is_dir():
            try:
                file.unlink()
                bucket.remove_from_loosefiles(item)
            except OSError as e:
                logger.error("Unable to remove file %s: %s", file, e)
                success = False
            else:
                logger.debug("File unlinked: %s", file)
        else:
            dlist.append(file)

    dlist.sort(reverse=True)
    for directory in dlist:
        try:
            directory.rmdir()
        except OSError as e:  # Probably due to not being empty
            logger.error("Unable to remove directory %s: %s", directory, e)
            success = False
        else:
            logger.debug("Directory removed: %s", directory)

    return success


def delete_archive(filepath):
    """Delete an archive from the filesystem."""
    if not isinstance(filepath, pathlib.Path):
        filepath = pathlib.Path(filepath)

    if filepath.exists():
        try:
            filepath.unlink()
        except OSError as e:
            logger.error("Unable to remove file from drive: %s", e)
            return False
    else:
        logger.error("Unable to remove an non-existing file: %s", filepath)
    return True
