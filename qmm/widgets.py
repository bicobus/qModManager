# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from os import path
# from collections import deque # DetailView
from .common import timestampToString, settings
from .filehandler import (FILE_MISSING, FILE_MATCHED, FILE_MISMATCHED,
                          FILE_IGNORED)
from .conflictbucket import ConflictBucket
from .ui_settings import Ui_Settings
# from .ui_detailedview import Ui_DetailedView # DetailView
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSlot

# from PyQt5.QtGui import QIcon, QPixmap
# _detailViewButton = QtWidgets.QPushButton()
# icon = QIcon()
# icon.addPixmap(QPixmap(":/icons/info.svg"), QIcon.Normal, QIcon.Off)
# _detailViewButton.setIcon(icon)

logger = logging.getLogger(__name__)


class QSettings(QtWidgets.QWidget, Ui_Settings):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

    def show(self):
        super().show()
        self.game_input.setText(settings['game_folder'])
        self.repo_input.setText(settings['local_repository'])

    @pyqtSlot()
    def on_game_button_clicked(self):
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.game_label.text(),
            directory=settings['game_folder']
        )

        if value and value != settings['game_folder']:
            self.game_input.setText(value)

    @pyqtSlot()
    def on_repo_button_clicked(self):
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.repo_label.text(),
            directory=settings['local_repository']
        )
        if value and value != settings['local_repository']:
            self.repo_input.setText(value)

    @pyqtSlot()
    def on_save_button_clicked(self):
        if (self.game_input.text() != settings['game_folder']
                and path.isdir(self.game_input.text())):
            settings['game_folder'] = self.game_input.text()
        if (self.repo_input.text() != settings['local_repository']
                and path.isdir(self.repo_input.text())):
            settings['local_repository'] = self.repo_input.text()
        self.hide()

    @pyqtSlot()
    def on_cancel_button_clicked(self):
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
#  FIXME: Unfinished, will need to be revisited
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

    def __init__(self, filename, data, stat, hashsum):
        super().__init__()
        self._key = path.basename(filename)
        self._data = data
        self._stat = stat
        self._name = None
        self._added = None
        self._hashsum = hashsum

        self._matched = []
        self._matched_str = None
        self._missing = []
        self._missing_str = None
        self._mismatched = []
        self._mismatched_str = None
        self._ignored = []
        self._ignored_str = None
        self._conflicts = {}
        self._conflicts_str = None
        self._build_strings = [
            "matched", "missing", "mismatched", "ignored", "conflicts"
        ]

        self.setText(self.filename)

    def _set_item_status(self, item, status):
        if status == FILE_MATCHED:
            self._matched.append(item)
        elif status == FILE_MISMATCHED:
            self._mismatched.append(item)
        elif status == FILE_MISSING:
            self._missing.append(item)
        elif status == FILE_IGNORED:
            self._ignored.append(item)
        else:
            return False
        return True

    def _conflict_triage(self, item):
        c = []
        # Check other archives
        if item.Path in ConflictBucket().conflicts.keys():
            c.extend(ConflictBucket().conflicts[item.Path])
        # Check against existing files
        if item.CRC in ConflictBucket().looseconflicts.keys():
            c.extend(ConflictBucket().looseconflicts[item.CRC])
        # Check against game files (Path and CRC)
        if (item.Path in ConflictBucket().gamefiles.values()
                or item.CRC in ConflictBucket().gamefiles.keys()):
            c.append(ConflictBucket().gamefiles[item.CRC])
        if c:
            self._conflicts[item.Path] = c

    def _format_strings(self):
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

    def refresh_strings(self):
        self._conflicts = {}
        for item, _ in self._data:
            self._conflict_triage(item)
        self._format_strings()

    @property
    def name(self):
        if not self._name:
            self._name = self._key.replace('_', ' ')
        return self._name

    @property
    def filename(self):
        return self._key

    @property
    def added(self):
        if not self._added:
            self._added = timestamp_to_string(self._stat.st_mtime)
        return self._added

    @property
    def hashsum(self):
        if self._hashsum:
            return self._hashsum
        return ""

    @property
    def files(self):
        top = []
        strings = ["== Archive's content:\n"]
        errstring = "ERR: Following file has unknown status → {}"
        for item, status in self._data:
            if not self._set_item_status(item, status):
                top.append(errstring.format(item.Path))

            self._conflict_triage(item)

            # Add only files to avoid clutter
            if 'D' not in item.Attributes:
                strings.append(f"   - {item.Path}\n")

        self._format_strings()
        rstr = ""
        if top:
            rstr = "".join(top) + "\n\n"
        rstr += "".join(strings)

        return rstr

    @property
    def matched(self):
        return self._matched_str

    @property
    def has_matched(self):
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


def _format_regular(title, items):
    strings = [f"== {title}:\n"]
    for item in items:
        if 'D' in item.Attributes:
            continue
        crc = hex(item.CRC)
        strings.append(f"  - {item.Path} ({crc})\n")
    strings.append("\n")
    return "".join(strings)


def _format_conflicts(title, items):
    strings = [f"== {title}:\n"]
    for filepath, archives in items:
        strings.append(f"  - {filepath}\n        -> ")
        strings.append("\n        -> ".join(archives) + "\n")
    return "".join(strings)
