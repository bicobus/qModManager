# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
import shutil
import subprocess
import re
import pathlib

from zlib import crc32
from hashlib import sha256
from collections import namedtuple
from collections import MutableMapping
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
first_level_dir = ('items', 'outfits')
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


class ArchiveException(Exception):
    def __init__(self, message):
        self.message = message


class UnrecognizedArchive(ArchiveException):
    def __init__(self, message=None):
        super().__init__(message)


def ignore_patterns(sevenFlag=False):
    if sevenFlag:
        return ('-xr!*.DS_Store', '-x!__MACOSX', '-xr!*Thumbs.db')
    else:
        return ('.DS_Store', '__MACOSX', 'Thumbs.db')


def extract7z(file_archive, outputpath, progress=None):
    filepath = os.path.abspath(file_archive)
    outputpath = os.path.abspath(outputpath)
    cmd = [
        tools_path(
        ), 'x', f'{filepath}', f'-o{outputpath}', '-ba', '-bb1', '-y',
        '-scsUTF-8', '-sccUTF-8'
    ]
    cmd.extend(ignore_patterns(True))

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
    """Returns the 256 hash of the managed archive.
    """
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

        if len(self._data) > 0 and not rebuild:
            return False

        patterns = ['rar', 'zip', '7z']
        with os.scandir(settings['local_repository']) as it:
            for entry in it:
                if entry.is_file() and any(entry.name.endswith(x) for x in patterns):
                    filename = os.path.join(
                        settings['local_repository'], entry.name)
                    self[entry.name] = list7z(filename, progress=progress)
                    self._stat[entry.name] = pathlib.Path(
                        pathObject(filename)).stat()
                    self._hashsums[entry.name] = _sha256hash(filename)

    def find(self, archiveName=None, hashsum=None):
        if archiveName and archiveName in self._data.keys():
            return self._data[archiveName]
        if hashsum and hashsum in self._hashsums:
            for key, item in self._hashsums:
                if item == hashsum:
                    return self._hashsums[key]
        return False

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
    for root, dirs, files in os.walk(folder):
        if len(files) == 0:
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
        if archive_name not in list_to_exclude:
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


# archives_list: output of build_managed_archives_crc32
# check against loose files first, then
def detect_conflicts_between_archives(archives_lists):
    assert isinstance(archives_lists, ArchivesCollection), type(archives_lists)
    list_done = []  # (sha256, filepath) of already processed archives
    conflicts = ConflictBucket().conflicts
    for archive_name, archive_content in archives_lists.items():
        for file in archive_content:

            if file.CRC in ConflictBucket().loosefiles.keys():
                ConflictBucket().has_loose_conflicts(file)

            if file.Path in conflicts.keys():
                continue

            bad_archives = file_in_other_archives(
                file=file,
                archives=archives_lists,
                ignore=list_done)

            if bad_archives:
                bad_archives.append(archive_name)
                conflicts.setdefault(file.Path, [])
                conflicts[file.Path].extend(bad_archives)
        list_done.append(archive_name)

    return conflicts


FILE_MATCHED = 1
FILE_MISSING = 2
FILE_MISMATCHED = 3
FILE_IGNORED = 4


def file_in_loose_files(file):
    cBucket = ConflictBucket().loosefiles
    if os.path.basename(file.Path) in ignore_patterns():
        return FILE_IGNORED
    if file.CRC in cBucket.keys() and cBucket[file.CRC] == file.Path:
        return FILE_MATCHED
    if file.Path in cBucket.values() and file.CRC not in cBucket.keys():
        return FILE_MISMATCHED
    return FILE_MISSING


def missing_matched_mismatched(file_list):
    new_list = []
    for file in file_list:
        new_list.append((file, file_in_loose_files(file)))
    return new_list


def copy_archive_to_repository(filename):
    """
    Copy an archive to the manager's repository
    """
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


def install_archive(fileToCopy):
    """Install the content of an archive into the game mod folder.
    """
    if not settings['game_folder']:
        log.warning("Unable to unpack archive: game location is unknown.")
        return False

    fileToCopy = os.path.join(settings['local_repository'], fileToCopy)

    try:
        with TemporaryDirectory(prefix="qmm-") as td:
            files = extract7z(fileToCopy, td)
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


def uninstall_archive(hashsum):
    dir_list = []
    for item in managed_archives_db[hashsum]['installed_files']:
        filename = _get_mod_folder(settings, with_file=item)
        log.debug("Trying to delete file: %s", filename)
        if os.path.isdir(filename):
            dir_list.append(filename)
        else:
            try:
                os.remove(filename)
            except OSError as e:
                log.error("Unable to remove file %s: %s", item, e)

    # NOTE: reverse put the longest string first, since we aim to remove a
    #       directory tree, this sort should be sufficient
    dir_list.sort(reverse=True)
    for item in dir_list:
        try:
            os.rmdir(item)
        except OSError as e:
            log.debug("Directory not removed because: %s", e)
            log.warning("Ignoring non-empty directory: %s", item)

    managed_archives_db[hashsum].update({
        'installed': False,
        'installed_files': [],
        'archive_installed': None
    })
    managed_archives_db.delayed_save()


def delete_archive(hashsum):
    """Removes a file from the repository, and delete it from the filesystem
    """
    if hashsum not in managed_archives_db:
        log.error("Unable to remove an non-existing file: %s", hashsum)

    if managed_archives_db[hashsum]['installed']:
        uninstall_archive(hashsum)

    filename = managed_archives_db[hashsum]['filename']
    del(managed_archives_db[hashsum])
    try:
        os.remove(filename)
    except OSError as e:
        log.error("Unable to remove file from drive: %s", e)
    finally:
        managed_archives_db.delayed_save()
