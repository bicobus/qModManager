"""Contains various Qt Widgets used internally by the application.
Licensed under the EUPL v1.2
© 2019 bicobus <bicobus@keemail.me>
"""

import logging
from os import path
# from collections import deque # DetailView
from typing import Tuple, List

from PyQt5 import QtWidgets, QtGui
from PyQt5.QtCore import pyqtSlot
from .common import timestamp_to_string, settings
from .filehandler import (FILE_MISSING, FILE_MATCHED, FILE_MISMATCHED,
                          FILE_IGNORED, missing_matched_mismatched)
from .bucket import FileMetadata
from . import bucket
from .ui_settings import Ui_Settings
from .ui_about import Ui_About
# from .ui_detailedview import Ui_DetailedView # DetailView

# from PyQt5.QtGui import QIcon, QPixmap
# _detailViewButton = QtWidgets.QPushButton()
# icon = QIcon()
# icon.addPixmap(QPixmap(":/icons/info.svg"), QIcon.Normal, QIcon.Off)
# _detailViewButton.setIcon(icon)

logger = logging.getLogger(__name__)


class QAbout(QtWidgets.QWidget, Ui_About):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        font = QtGui.QFont()
        font.setFamily("Unifont")
        font.setPointSize(11)
        self.text_author.setFont(font)


class QSettings(QtWidgets.QWidget, Ui_Settings):
    """Define the settings windows."""

    def __init__(self):
        super().__init__()
        self.setupUi(self)

    def set_mode(self, first_run=False):
        if first_run:
            self.cancel_button.setEnabled(False)
        else:
            self.cancel_button.setEnabled(True)

    def show(self):
        """Show the window and assign internal variables"""
        super().show()
        self.game_input.setText(settings['game_folder'])
        self.repo_input.setText(settings['local_repository'])

    @pyqtSlot(name="on_game_button_clicked")
    def _set_game_directory(self):
        """Callback, will show a file selection window to the user"""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.game_label.text(),
            directory=settings['game_folder']
        )  # noqa pycharm

        if value and value != settings['game_folder']:
            self.game_input.setText(value)

    @pyqtSlot(name="on_repo_button_clicked")
    def _set_repository_directory(self):
        """Callback, will show a file selection window to use user"""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.repo_label.text(),
            directory=settings['local_repository']
        )  # noqa pycharm
        if value and value != settings['local_repository']:
            self.repo_input.setText(value)

    @pyqtSlot(name="on_save_button_clicked")
    def _commit_changes(self):
        """Callback, commit changes to the settings file then hide self"""
        if (self.game_input.text() != settings['game_folder']
                and path.isdir(self.game_input.text())):
            settings['game_folder'] = self.game_input.text()
        if (self.repo_input.text() != settings['local_repository']
                and path.isdir(self.repo_input.text())):
            settings['local_repository'] = self.repo_input.text()
        self.hide()

    @pyqtSlot(name="on_cancel_button_clicked")
    def on_cancel_button_clicked(self):
        """Simply hide the window.
        The default values are being defined within the show method, thus
        there is nothing here for us to do.
        Returns:
            void
        """
        self.hide()


# widgets name:
#  * content_name
#  * content_author
#  * content_version
#  * content_url
#  * content_description
#  * content_tags
#  * filetreeWidget
#
#  Unfinished, will need to be revisited
# class DetailedView(QtWidgets.QWidget):
#     def __init__(self, parent=None):
#         super(DetailedView, self).__init__(parent)
#         self.ui = Ui_DetailedView()
#         self.ui.setupUi(self)
#         self.ui.button_hide.hide()
#         self.ui.filetreeWidget.hide()

#     def prepare_directoryList(self, directories):
#         """Returns a dict of lists of files indexed on a tuple of directories.
#         Example: dict(
#          ('res/TheShyGuy995/', 'weapons', 'Fire Emblem'): ['/Sheathed Sword.svg', '/Sword.xml']
#         )
#         """
#         dlist = list()
#         for file in directories:
#             dirname, _ = path.split(file)
#             if dirname not in dlist and "/" in dirname:
#                 dlist.append(dirname)

#         prefix = path.commonpath(dlist)
#         if "/" in prefix:
#             prefix = prefix.split("/")

#         ddir = dict()
#         for dirname in dlist:
#             sdir = dirname.split('/')
#             if isinstance(prefix, list):
#                 for p in prefix:
#                     sdir.remove(p)
#             else:
#                 sdir.remove(prefix)
#             dir_str = "/".join(sdir)

#             for ofile in directories:
#                 if dir_str in ofile:
#                     start, tmp, cfile = ofile.partition(dir_str)
#                     path_to_file = tmp.split("/")
#                     pfile = list()
#                     pfile.append(start)
#                     pfile.extend(path_to_file)
#                     pfile = tuple(pfile)
#                     if pfile not in ddir.keys():
#                         ddir[pfile] = deque()
#                     ddir[pfile].append(cfile)

#         return ddir

#     def build_dirlist(self, pathAndFiles):
#         dir_map = dict()
#         for directories, files in pathAndFiles.items():
#             for directory in directories:
#                 if directory not in dir_map.keys():
#                     index = directories.index(directory)
#                     if index > 0:
#                         previous = directories[index - 1]
#                     else:
#                         previous = self.ui.filetreeWidget

#                 dir_map[directory] = QtWidgets.QTreeWidgetItem(previous, directory)

#             for file in files:
#                 dir_map[directory].addChild(QtWidgets.QTreeWidgetItem(None, file.strip('/')))

#     def closeEvent(self, event):
#         """Ignore the close event and hide the widget instead

#         If the window gets closed, Qt will prune its data and renders it
#         unavailable for further usage.
#         """
#         self.hide()
#         event.ignore()


class ListRowItem(QtWidgets.QListWidgetItem):
    """ListWidgetItem representing one single archive."""
    _data: List[Tuple[FileMetadata, int]]

    def __init__(self, filename: str, data, stat, hashsum):
        super().__init__()
        self._key = path.basename(filename)
        self._data = data
        self._stat = stat
        self._name = None
        self._added = None
        self._hashsum = hashsum

        self._files_str = ""
        self._matched_str = ""
        self._missing_str = ""
        self._mismatched_str = ""
        self._ignored_str = ""
        self._conflicts_str = ""
        self._errored_str = ""

        self._triage_done = False
        self._triage_second = False
        self._built_strings = False

        self.setText(self.filename)
        self.__setup_buckets()
        self._triage()
        self._format_strings()

    def __setup_buckets(self):
        self._files = []
        self._folders = []
        self._matched = []
        self._missing = []
        self._mismatched = []
        self._ignored = []
        self._conflicts = {}
        self._errored = []

    def _triage(self):
        if self._triage_done:
            return
        for item, status in self._data:
            if not self._set_item_status(item, status):
                self._errored.append(item)
            if not item.is_dir():
                self._files.append(item)
            else:
                self._folders.append(item)
            self._conflict_triage(item)
        self._triage_done = True

    def _set_item_status(self, item, status):
        if status == FILE_MATCHED:
            self._matched.append(item)
        elif status == FILE_MISMATCHED:
            # File is mismatched against something else, find it and store it
            for crc, mfile in bucket.loosefiles.items():
                f = list(filter(lambda x: x.path == item.path, mfile))
                if f:
                    logger.debug("Found mismatched as '%s'", f[0])
                    self._mismatched.append(f[0])
        elif status == FILE_MISSING:
            self._missing.append(item)
        elif status == FILE_IGNORED:
            self._ignored.append(item)
        else:
            return False
        return True

    def _conflict_triage(self, item: FileMetadata):
        tmp_conflicts = []
        # Check other archives
        if bucket.with_conflict(item.path):
            tmp_conflicts.extend(bucket.conflicts[item.path])
        # Check against existing files
        # XXX maybe useless
        if bucket.with_looseconflicts(item.path):
            x = [c.path for c in bucket.looseconflicts[item.path]
                 if c.crc != item.crc]
            logger.debug(x)
            tmp_conflicts.extend(
                x
            )
        # Check against game files (Path and CRC)
        if (bucket.with_gamefiles(path=item.path)
                or bucket.with_gamefiles(crc=item.crc)):
            tmp_conflicts.append(bucket.gamefiles[item.crc])
        if tmp_conflicts:
            self._conflicts[item.path] = tmp_conflicts

    def _format_strings(self):
        self._files_str = _format_regular(
            title="Archive's content",
            items=self._files)
        self._errored_str = _format_regular(
            title="ERR: Following file has unknown status",
            items=self._errored)
        self._matched_str = _format_regular(
            title="Files installed",
            items=self._matched)
        self._missing_str = _format_regular(
            title="Missing from the game folder",
            items=self._missing)
        self._mismatched_str = _format_regular(
            title="Same name and different CRC or same CRC with different names",
            items=self._mismatched)
        self._conflicts_str = _format_conflicts(
            title="Conflicting files between archives",
            items=self._conflicts.items())
        self._ignored_str = _format_regular(
            title="Files present in the archive but ignored",
            items=self._ignored)
        self._built_strings = True

    def refresh_strings(self):
        """Called when the game's folder state changed

        Reinitialize the widget's strings, recompute the conflicts then redo
        all triaging and formatting.
        """
        self.__setup_buckets()
        self._data = missing_matched_mismatched([i for i, _ in self._data])
        self._triage_done = False
        self._triage_second = True
        self._triage()
        self._format_strings()

    def list_ignored(self):
        """Returns a list of ignored elements"""
        return self._ignored

    def install_info(self):
        return {
            'matched': self._matched,
            'mismatched': self._mismatched,
            'ignored': self._ignored
        }

    def list_matched(self, include_folders=False):
        """Returns a list of matched files.

        Args:
            include_folders (bool): If true, include folders into the list.
        """
        if not include_folders:
            return self._matched
        return self._matched + self._folders

    @property
    def name(self):
        """Return the name of the archive, formatted for GUI usage

        Transfrom the '_' character into space.
        """
        if not self._name:
            self._name = self._key.replace('_', ' ')
        return self._name

    @property
    def filename(self):
        """Returns the name of the archive filename, suitable for path manipulations"""
        return self._key

    @property
    def added(self):
        """Returns time at which the archive got added to the system"""
        if not self._added:
            self._added = timestamp_to_string(self._stat.st_mtime)
        return self._added

    @property
    def hashsum(self):
        """Returns the sha256 hashsum of the archive"""
        if self._hashsum:
            return self._hashsum
        return ""

    @property
    def files(self):
        """Returns a formatted string containing all the files of the archive"""
        if not self._built_strings:
            self._format_strings()
            self._built_strings = True

        if self._errored:
            return self._errored_str + "\n" + self._files_str
        return self._files_str

    @property
    def matched(self):
        """Returns a formatted string containing all files matched on the filesystem"""
        return self._matched_str

    @property
    def has_matched(self) -> bool:
        """Returns True if the archive has matched files on the filesystem"""
        if self._matched:
            return True
        return False

    @property
    def missing(self):
        return self._missing_str

    @property
    def has_missing(self):
        if self._missing:
            return True
        return False

    @property
    def mismatched(self):
        return self._mismatched_str

    @property
    def has_mismatched(self):
        if self._mismatched:
            return True
        return False

    @property
    def conflicts(self):
        return self._conflicts_str

    @property
    def has_conflicts(self):
        if self._conflicts:
            return True
        return False

    @property
    def skipped(self):
        return self._ignored_str

    @property
    def has_skipped(self):
        if self._ignored:
            return True
        return False


def _format_regular(title, items: List[FileMetadata]):
    strings = [f"== {title}:\n"]
    for item in items:
        if item.is_dir():
            continue
        crc = hex(item.crc)
        strings.append(f"  - {item.path} ({crc})\n")
    strings.append("\n")
    return "".join(strings)


def _format_conflicts(title, items):
    strings = [f"== {title}:\n"]
    for filepath, archives in items:
        strings.append(f"  - {filepath}\n")
        for element in archives:
            if isinstance(element, list):
                for e in element:
                    strings.append(f"\t-> (debug:a) {e.path}\n")
            else:
                if isinstance(element, FileMetadata):
                    e = [element.path, element.crc, element.origin]
                else:
                    e = element
                strings.append(f"\t-> (debug:b) {e}\n")
    return "".join(strings)
