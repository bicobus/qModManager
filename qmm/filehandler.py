# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
import shutil
import yaml

from io import TextIOWrapper
from hashlib import sha256
from zipfile import ZipFile, is_zipfile
from collections import namedtuple
from time import time
from py7zlib import Archive7z, ArchiveError, MAGIC_7Z

from .config import Config
from .dialogs import qError
log = logging.getLogger(__name__)


Unpack = namedtuple('Unpack', 'file_list error')


class UnrecognizedArchive(Exception):
    pass


def _check_7zfile(fp):
    try:
        if fp.read(len(MAGIC_7Z)) == MAGIC_7Z:
            return True
    except OSError:
        pass
    return False


def is_7zfile(filename):
    """Check the magic number of a file and ensure it is a 7z archive.

    The filename argument can be an IO stream or a string
    """
    result = False
    try:
        if hasattr(filename, "read"):
            result = _check_7zfile(fp=filename)
        else:
            with open(filename, "rb") as fp:
                result = _check_7zfile(fp)
    except OSError:
        pass
    return result


def _get_mod_folder(config_obj, with_file=None, has_res=False):
    path = [config_obj['game_folder']]
    if not has_res:
        path.extend(['res', 'mods'])
    if with_file:
        path.append(with_file)
    return os.path.join(*path)


class ArchiveInterface:
    def __init__(self, filename, config_obj):
        self.filename = filename
        if is_zipfile(filename):
            self.filetype = "zip"
        elif is_7zfile(filename):
            self.filetype = "7z"
        else:
            raise UnrecognizedArchive("Unsupported archive: %s", filename)

        self._config_obj = config_obj
        self._archive_object = None
        self._has_res_folder = False

    def __exit__(self, type, value, traceback):
        self.close()

    def _get_archive_object(self):
        """Initialize the file pointer and archive object
        """
        if self._archive_object:
            return self._archive_object

        self._filestream = open(self.filename, 'rb')
        if self.filetype == 'zip':
            self._archive_object = ZipFile(self._filestream)
        elif self.filetype == '7z':
            try:
                self._archive_object = Archive7z(self._filestream)
            except ArchiveError as e:
                log.exception("Something bad happened while handling the archive:\n%s", e)
                return False

    def _check_file_exist(self, filename):
        """Check if filename already exist in in the game mod folder.
        """
        return os.path.exists(os.path.join(
            self._config_obj['game_folder'],
            self.res_folder,
            filename
        ))

    def _get_filename_from_member(self, member):
        if self.filetype == "zip":
            return member
        elif self.filetype == "7z":
            return member.filename

    def _set_res_folder(self, member):
        """
        Flip the "res folder" switch. Used while extracting.
        """
        fname = member if self.filetype == "zip" else member.filename
        if fname.split('/')[0] == 'res':
            self._has_res_folder = True

    def namelist(self):
        """Walk through an archive and yield each member
        """
        if self.filetype == "zip":
            for member in self._archive_object.namelist():
                yield member
        elif self.filetype == "7z":
            for member in self._archive_object.getmembers():
                yield member

    def extract(self, member):
        """Extract one member of an archive to destination.

        If member is from a Archive7z object, make sure the remote folder exists.
        """
        try:
            destination = os.path.join(
                self._config_obj['game_folder'],
                self.res_folder
            )
            if self.filetype == "zip":
                self._archive_object.extract(member, destination)
            elif self.filetype == "7z":
                destination = os.path.join(destination, self._get_filename_from_member(member))
                if not os.path.exists(os.path.dirname(destination)):
                    os.makedirs(os.path.dirname(destination))
                with open(destination, 'wb') as fp:
                    fp.write(member.read())
        except IOError as e:
            log.exception("Unable to write file to disk:\n%s", e)
            return False
        return True

    def close(self):
        """Properly free the resource
        """
        try:
            self._filestream.close()
        except Exception:
            log.exception("Unable to close the archive file.")
            raise
        self._archive_object = None

    @property
    def archive_object(self):
        if not self._archive_object:
            self._get_archive_object()
        return self._archive_object

    @property
    def res_folder(self):
        return os.path.join('res', 'mods') if not self._has_res_folder else ''


class ArchiveHandler(ArchiveInterface):
    """Handle specific archive, can unpack and return the sha256 hash"""

    def __init__(self, filename, config_obj):
        super().__init__(filename, config_obj)
        self._hash = None
        self._metadata = None

    def copy_file_to_repository(self):
        """
        Copy an archive to the manager's repository
        """
        if not self._config_obj['local_repository']:
            log.warning("Unable to copy archive: no local repository configured.")
            return False

        dst_folder = os.path.join(
            self._config_obj['local_repository'],
            self.hash[:2]
        )

        new_filename = os.path.join(
            dst_folder,
            os.path.basename(self.filename)
        )

        if os.path.exists(new_filename):
            log.error("Unable to copy archive, a file with a similar name already exists.")
            return False

        try:
            if not os.path.exists(dst_folder):
                os.makedirs(dst_folder)
            shutil.copy(self.filename, dst_folder)
        except IOError as e:
            log.error("Error copying archive: %s", e)
            return False
        else:
            self.filename = new_filename
            return True

    def unpack(self):
        if not self._config_obj['game_folder']:
            log.warning("Unable to unpack archive: game location is unknown.")
            return False

        unpacked_files = []
        error_list = []
        for member in self.namelist():
            self._set_res_folder(member)
            fname = self._get_filename_from_member(member)
            if fname == '_metadata.yaml':
                continue

            if self._check_file_exist(fname):
                log.warning(
                    "File '%s' already exists in mod directory.",
                    fname
                )

                lname = fname.split('/')
                lname.remove('')
                if (self._has_res_folder and len(lname) > 2) or not self._has_res_folder:
                    error_list.append(fname)

                continue
            self.extract(member)
            unpacked_files.append(fname)

        if error_list:
            detail = "Ignored files:\n\n\t{}".format("\n\t".join(error_list))
        else:
            detail = None

        return Unpack(file_list=unpacked_files, error=detail)

    @property
    def metadata(self):
        if self._metadata:
            return self._metadata

        mdata_filename = '_metadata.yaml'
        if self.filetype == 'zip':
            if mdata_filename in self.archive_object.namelist():
                x = TextIOWrapper(self.archive_object.open(mdata_filename))
                self._metadata = yaml.load(x.read())
        elif self.filetype == '7z':
            if mdata_filename in self.archive_object.getnames():
                x = self.archive_object.getmember(mdata_filename)
                self._metadata = yaml.load(x.read().decode('utf-8'))

        if not self._metadata:
            self._metadata = {
                'name': '',
                'author': '',
                'description': '',
                'category': []
            }

        self._metadata['filename'] = os.path.basename(self.filename)

        return self._metadata

    @property
    def hash(self):
        if not self._hash:
            with open(self.filename, 'rb') as fp:
                m = sha256(fp.read())
            self._hash = m.hexdigest()
        return self._hash

    @hash.setter
    def hash(self, value):
        pass

    @property
    def name(self):
        return self._metadata['name'] if self._metadata['name'] else self._metadata['filename']


class ArchiveManager:
    """The ArchiveManager keep tracks, install and uninstall the differents
    archives of the repository.
    """

    def __init__(self, config_obj):
        self._config_obj = config_obj
        self._files_index = Config("files_index.json", compress=True)
        self._file_list = dict()
        self.load()

    def add_file(self, filename):
        """Adds a file to the repository.
        """
        my_file = ArchiveHandler(filename, self._config_obj)

        if my_file.hash in self._files_index:
            log.warning("Duplicate archive, ignored: %s", my_file.filename)
            return False

        my_file.copy_file_to_repository()

        self._files_index[my_file.hash] = {
            'filename': my_file.filename,
            'installed': False,
            'installed_files': [],
            'file_added': time(),
            'archive_installed': None
        }
        self._file_list[my_file.hash] = my_file

        # XXX: the auto-save doesn't trigger because we do not modify a first level element
        self._files_index.delayed_save()

        return my_file.hash

    def remove_file(self, file_hash):
        if file_hash not in self._files_index:
            log.error("Unable to remove an non-existing file: %s", file_hash)

        filename = self._file_list[file_hash].filename
        self._file_list[file_hash].close()
        del(self._file_list[file_hash])
        del(self._files_index[file_hash])
        try:
            os.remove(filename)
        except OSError as e:
            log.error("Unable to remove file from drive: %s", e)

    def install_mod(self, file_hash):
        """Install the content of an archive into the game mod folder.
        """
        if file_hash not in self._files_index:
            log.error("Installation failure, hash not found: %s", file_hash)
            return

        files, error = self._file_list[file_hash].unpack()
        self._files_index[file_hash].update({
            'installed': True,
            'installed_files': files,
            'archive_installed': time()
        })
        self._files_index.delayed_save()

        if error:
            qError((
                "One or more files could not be installed because they already "
                "exists within the game's mods folder. They will therefore not "
                "be managed through this mod."),
                detailed=error
            )

    def uninstall_mod(self, file_hash):
        dir_list = []
        for item in self._files_index[file_hash]['installed_files']:
            has_res = (item.split('/')[0] == 'res')
            filename = _get_mod_folder(self._config_obj, with_file=item, has_res=has_res)
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

        self._files_index[file_hash].update({
            'installed': False,
            'installed_files': [],
            'archive_installed': None
        })
        self._files_index.delayed_save()

    def load(self):
        """Builds the internal list of files
        """
        if len(self._files_index) == 0 or len(self._file_list) > 0:
            return False

        for file_hash, data in self._files_index.items():
            self._file_list[file_hash] = ArchiveHandler(data['filename'], self._config_obj)

    def get_files(self):
        for file_hash, file in self._file_list.items():
            yield file

    def get_file_by_hash(self, file_hash):
        if file_hash not in self._file_list.keys():
            return None
        return self._file_list[file_hash]

    def get_state_by_hash(self, file_hash):
        if file_hash not in self._files_index.keys():
            return None
        return self._files_index[file_hash]['installed']

    def get_fileinfo_by_hash(self, file_hash):
        if file_hash not in self._files_index.keys():
            return None
        return self._files_index[file_hash]
