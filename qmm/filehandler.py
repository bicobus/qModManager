# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
import shutil
import subprocess
import re
import pathlib

from functools import lru_cache
from zlib import crc32
from hashlib import sha256
from collections import namedtuple
from collections.abc import MutableMapping
from tempfile import TemporaryDirectory

from . import is_windows
from .common import tools_path, settings, settings_are_set
from .conflictbucket import ConflictBucket
log = logging.getLogger(__name__)

# this shit: https://docs.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-startupinfoa
# Internet wisdom tells me STARTF_USESHOWWINDOW is used to hide the would be console
startupinfo = None
if is_windows:
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    pathObject = pathlib.PureWindowsPath
else:
    pathObject = pathlib.PurePosixPath

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

UnpackList = namedtuple('UnpackList', 'file_list error')
FileMetadata = namedtuple('FileMetadata', 'Path Attributes CRC Modified')
ArchiveStruct = namedtuple(
    'ArchiveStruct', 'valid mismatched missing conflict ignored')


class FileHandlerException(Exception):
    pass


class ArchiveException(FileHandlerException):
    pass


def ignore_patterns(sevenFlag=False):
    if sevenFlag:
        return ('-xr!*.DS_Store', '-x!__MACOSX', '-xr!*Thumbs.db')
    return ('.DS_Store', '__MACOSX', 'Thumbs.db')


def extract7z(file_archive, outputpath, excludeList=None, progress=None):
    filepath = os.path.abspath(file_archive)
    outputpath = os.path.abspath(outputpath)
    cmd = [
        tools_path(
        ), 'x', f'{filepath}', f'-o{outputpath}', '-ba', '-bb1', '-y',
        '-scsUTF-8', '-sccUTF-8'
    ]
    cmd.extend(ignore_patterns(True))
    if excludeList:
        assert isinstance(excludeList, list)
        cmd.extend(excludeList)

    proc = subprocess.Popen(
        cmd, startupinfo=startupinfo, stdout=subprocess.PIPE,
        stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    fList = []
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
                fList.append(FileMetadata(Attributes=None, Path=path,
                                          CRC=None, Modified=None))
                if progress:
                    progress(f'Extracting {path}...')

    returncode = proc.wait()
    if returncode != 0 or errstring:
        raise ArchiveException((
            f"{filepath}: Extraction failed with error code {returncode} "
            f"and message:\n{errstring}"))

    return fList


def list7z(filepath, progress=None):
    filepath = os.path.abspath(filepath)

    if progress:
        progress(f'Processing {filepath}...')

    cmd = [
        tools_path(
        ), 'l', f'{filepath}', '-ba', '-scsUTF-8', '-sccUTF-8', '-slt'
    ]

    proc = subprocess.Popen(
        cmd, startupinfo=startupinfo, stdout=subprocess.PIPE,
        stdin=subprocess.PIPE, stderr=subprocess.STDOUT)

    fList = []
    model = {
        'Path': None,
        'Modified': None,
        'Attributes': None,
        'CRC': None
    }
    errstring = ""
    with proc.stdout as out:
        for line in iter(out.readline, b''):
            line = line.decode('utf-8')

            errData = reErrorMatch(line)
            if errData:
                errstring = line + b''.join(out).decode('utf-8')
                break

            fileData = reListMatch(line)
            if fileData:
                fdg = fileData.group(1).strip()
                if fdg == 'Path':
                    tmpData = model.copy()
                if fdg in ('Path', 'Modified', 'Attributes', 'CRC'):
                    tmpData[fdg] = fileData.group(2).strip()
                if fdg == 'CRC':
                    if 'D' not in tmpData['Attributes']:
                        tmpData[fdg] = int(tmpData[fdg], 16)
                    fList.append(FileMetadata(**tmpData))

    returncode = proc.wait()
    if returncode != 0 or errstring:
        raise ArchiveException((
            f"{filepath}: listing failed with error code {returncode} "
            f"and message:\n{errstring}"))

    return fList


def _sha256hash(filename):
    """Returns the 256 hash of the managed archive."""
    try:
        if hasattr(filename, 'read'):
            result = sha256(filename.read).hexdigest()
        else:
            with open(filename, 'rb') as fp:
                result = sha256(fp.read()).hexdigest()
    except OSError:
        pass

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
            path = pathlib.Path(os.path.join(settings['local_repository'], path))
        if not path.is_file():
            return
        if not hashsum:
            hashsum = _sha256hash(path)
        self[path.name] = list7z(path, progress)
        self._set_stat(path.name, path)
        self._set_hashsums(path.name, hashsum)

    def find(self, archiveName=None, hashsum=None):
        """Try to find a member, then returns its object, either through the name
        of the archive and/or the sha256sum of the file.

        If archiveName is not None, will check if archiveName exists in the
        keys of the collection.
        If hashsum is not None, will check if the value exists in the
        self._hashsums dict.
        If all checks fails, returns False.

        Keywords arguments:
        archiveName -- filename of the archive, suffix included (default None)
        hashsum -- sha256sum of the file (default None)
        """
        if archiveName and archiveName in self._data.keys():
            return self._data[archiveName]
        if hashsum and hashsum in self._hashsums:
            for key, item in self._hashsums:
                if item == hashsum:
                    return self._data[key]
        return False

    @property
    def stat(self, key):
        return self._stat[key]

    def _set_stat(self, key, value):
        assert isinstance(value, pathlib.Path)
        self._stat[key] = value.stat()

    @property
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
        del(self._data[key])
        del(self._stat[key])
        del(self._hashsums[key])


def _ignored_part_in_path(path):
    for item in path:
        if item in ignore_patterns():
            return True
    return False


def _get_mod_folder(with_file=None, force_build=False):
    path = [settings['game_folder']]
    mods_path = ['res', 'mods']
    if with_file:
        # XXX Removes the check, res/mods is supposed to not be present
        if with_file.split('/')[0] != 'res':
            path.extend(mods_path)
        path.append(with_file)
    elif force_build:
        path.extend(mods_path)
    return os.path.join(*path)


def _compute_files_crc32(folder, partition=('res', 'mods')):
    for root, _, files in os.walk(folder):
        if not files:
            continue
        # We want to build a path that is similar to the one present in an
        # archive. To do so we need to remove anything that is before, and
        # including the "partition" folder.
        path = root.partition(os.path.join(*partition) + os.path.sep)[2]

        for file in files:
            key = pathObject(os.path.join(path, file)).as_posix()
            with open(os.path.join(root, file), 'rb') as fp:
                yield (key, crc32(fp.read()))


# The paths returned by this function are non-existent due to a difference
# between the mods and the game folder structure.
def build_game_files_crc32(progress=None):
    target_folder = os.path.join(settings['game_folder'], 'res')
    scan_theses = ('clothing', 'outfits', 'tattoos', 'weapons')

    crc_dict = {}
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
            if crc in crc_dict.keys():
                log.error(f"Game has duplicate file or we found a CRC collision: {crc}")
            crc_dict[crc] = key

    ConflictBucket.gamefiles = crc_dict
    return crc_dict


# Returns a dict indexed on the files
def build_loose_files_crc32(progress=None):
    mod_folder = _get_mod_folder(force_build=True)
    crc_dict = {}
    for key, crc in _compute_files_crc32(mod_folder):
        progress(f"Computing {key}...")
        crc_dict[crc] = key

    ConflictBucket.loosefiles = crc_dict
    return crc_dict


def _filter_list_on_exclude(archives_list, list_to_exclude):
    for archive_name, items in archives_list.items():
        if not list_to_exclude or archive_name not in list_to_exclude:
            yield (archive_name, items)


def file_in_other_archives(file, archives, ignore):
    """Returns a list of archives in which file is found if the number of said
    archive is above 1. Otherwise returns False.

    file: file to be found
    archives: instance of ArchivesCollections
    ignore: list of archives to ignore, for instance already parsed archives
    """
    def _ofile(v):
        return (v.CRC, v.Path)

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
        if file.CRC in ConflictBucket().loosefiles.keys():
            ConflictBucket().has_loose_conflicts(file)

        if file.Path in ConflictBucket().conflicts.keys():
            continue

        bad_archives = file_in_other_archives(
            file=file,
            archives=archives_list,
            ignore=processed)

        if bad_archives:
            bad_archives.append(current_archive)
            ConflictBucket().conflicts.setdefault(file.Path, [])
            ConflictBucket().conflicts[file.Path].extend(bad_archives)


def detect_conflicts_between_archives(archives_lists):
    assert isinstance(archives_lists, ArchivesCollection), type(archives_lists)
    list_done = []  # (sha256, filepath) of already processed archives
    conflicts = ConflictBucket().conflicts
    for archive_name, archive_content in archives_lists.items():
        conflicts_process_files(archive_content, archives_lists, archive_name, list_done)
        list_done.append(archive_name)

    return conflicts


FILE_MATCHED = 1
FILE_MISSING = 2
FILE_MISMATCHED = 3
FILE_IGNORED = 4


@lru_cache(maxsize=None)
def _bad_directory_structure(path):
    if len(path.parts) > 1 and not any(path.parts[1] == x for x in first_level_dir):
        return True
    return False


def file_status(file):
    cBucket = ConflictBucket().loosefiles
    path = pathObject(file.Path)
    if (path.name in ignore_patterns()
        or (not path.suffix
            and _bad_directory_structure(path))
        or (path.suffix
            and path.suffix not in ('.xml', '.svg')
            or _bad_directory_structure(path))):
        return FILE_IGNORED
    if file.CRC in cBucket.keys() and cBucket[file.CRC] == file.Path:
        return FILE_MATCHED
    if file.Path in cBucket.values() and file.CRC not in cBucket.keys():
        return FILE_MISMATCHED
    return FILE_MISSING


def missing_matched_mismatched(file_list):
    new_list = []
    for file in file_list:
        new_list.append((file, file_status(file)))
    return new_list


def copy_archive_to_repository(filename):
    """Copy an archive to the manager's repository"""
    if not settings['local_repository']:
        log.warning("Unable to copy archive: no local repository configured.")
        return False

    new_filename = os.path.join(
        settings['local_repository'],
        os.path.basename(filename)
    )

    if os.path.exists(new_filename):
        log.error(
            "Unable to copy archive, a file with a similar name already exists.")
        return False

    try:
        if not os.path.exists(settings['local_repository']):
            os.makedirs(settings['local_repository'])
        shutil.copy(filename, settings['local_repository'])
    except IOError as e:
        log.error("Error copying archive: %s", e)
        return False
    else:
        return os.path.basename(new_filename)


def install_archive(fileToExtract, ignoreList):
    """Install the content of an archive into the game mod folder."""
    if not settings['game_folder']:
        log.warning("Unable to unpack archive: game location is unknown.")
        return False

    fileToExtract = os.path.join(settings['local_repository'], fileToExtract)
    ignoreList = ["-x!{}".format(path.Path) for path in ignoreList]

    try:
        with TemporaryDirectory(prefix="qmm-") as td:
            files = extract7z(fileToExtract, td, excludeList=ignoreList)
            for file in files:
                src = os.path.join(td, file.Path)
                if os.path.isdir(src):
                    continue
                dst = _get_mod_folder(file.Path)
                os.makedirs(dst, mode=0o644, exist_ok=True)
                shutil.copy2(src, dst)
    except ArchiveException as e:
        log.exception(e)
        return False
    return files


def uninstall_files(fileList):
    """Removes a list of files and directory from the filesystem."""
    assert isinstance(fileList, list)

    dlist = []
    for item in fileList:
        assert isinstance(item, pathlib.PurePath)
        i = pathlib.Path(item)
        log.debug("Trying to delete file: %s", item.Path)
        if not i.is_dir():
            try:
                i.unlink()
            except OSError as e:
                log.error("Unable to remove file %s: %s", item, e)
        else:
            dlist.append(i)

    dlist.sort(reverse=True)
    for directory in dlist:
        try:
            directory.rmdir()
        except OSError as e:  # Probably due to not being empty
            log.debug("Unable to remove directory %s: %s", directory, e)


def delete_archive(filepath):
    """Delete an archive from the filesystem."""
    if not isinstance(filepath, pathlib.Path):
        filepath = pathlib.Path(filepath)

    if filepath.exists():
        try:
            filepath.unlink()
        except OSError as e:
            log.error("Unable to remove file from drive: %s", e)
            return False
    else:
        log.error("Unable to remove an non-existing file: %s", filepath)
    return True
