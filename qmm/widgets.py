# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Contains various Qt Widgets used internally by the application."""

import logging
from os import path

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, QSize

from qmm.bucket import FileMetadata
from qmm.common import settings, timestamp_to_string
from qmm.dialogs import qInformation
from qmm.filehandler import ArchivesCollection
from qmm.lang import LANGUAGE_CODES, get_locale
from qmm.ui_about import Ui_About
from qmm.ui_settings import Ui_Settings

logger = logging.getLogger(__name__)


class QAbout(QtWidgets.QWidget, Ui_About):
    """About window displaying various informations about the software."""

    def __init__(self):
        super().__init__()
        self.setupUi(self)
        font = QtGui.QFont()
        font.setFamily("Unifont")
        font.setPointSize(11)
        self.text_author.setFont(font)


class QSettings(QtWidgets.QMainWindow):

    def __init__(self, parent=None):
        super().__init__(parent=parent, flags=Qt.Window)
        self.setObjectName("Settings")
        self.setWindowTitle(_("Settings"))
        self.setWindowModality(Qt.ApplicationModal)
        self.resize(600, 140)
        self.setMinimumSize(QSize(600, 140))
        self.setMaximumSize(QSize(800, 16777215))
        self.centralwidget = QtWidgets.QWidget(self, flags=Qt.Widget)
        self.centralwidget.setObjectName("centralwidget")
        self.settingwidget = QSettingsCentralWidget(self.centralwidget)
        self.settingwidget.setObjectName("settingwidget")
        self.setCentralWidget(self.centralwidget)
        size_policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred,
            QtWidgets.QSizePolicy.Preferred)
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(self.settingwidget.sizePolicy().hasHeightForWidth())

        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        newsize = self.sizeHint() + self.settingwidget.sizeHint()
        self.resize(newsize)
        # print(newsize)
        # print(self.centralwidget.sizeHint())

    def set_mode(self, first_run=False):
        if first_run:
            self.settingwidget.cancel_button.setEnabled(False)
            self.setWindowFlag(Qt.WindowCloseButtonHint, on=False)
        else:
            self.settingwidget.cancel_button.setEnabled(True)
            self.setWindowFlag(Qt.WindowCloseButtonHint, on=True)


class QSettingsCentralWidget(QtWidgets.QWidget, Ui_Settings):
    """Define the settings windows."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        self.repo_hide_help.hide()
        self.repo_helper.hide()
        self.game_hide_help.hide()
        self.game_helper.hide()

        for lang, code in LANGUAGE_CODES:
            self.language_combo_box.addItem(lang, code)
        current = get_locale()
        current_idx = self.language_combo_box.findData(current)
        self.language_combo_box.setCurrentIndex(current_idx)
        self.language_combo_box.setDisabled(True)

    def show(self):
        """Show the window and assign internal variables."""
        super().show()
        self.game_input.setText(settings['game_folder'])
        self.repo_input.setText(settings['local_repository'])

    @pyqtSlot(name="on_game_button_clicked")
    def _set_game_directory(self):
        """Show a file selection window to the user."""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.game_label.text(),
            directory=settings['game_folder']
        )  # noqa pycharm

        if value and value != settings['game_folder']:
            self.game_input.setText(value)

    @pyqtSlot(name="on_repo_button_clicked")
    def _set_repository_directory(self):
        """Show a file selection window to use user."""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.repo_label.text(),
            directory=settings['local_repository']
        )  # noqa pycharm
        if value and value != settings['local_repository']:
            self.repo_input.setText(value)

    @pyqtSlot(name="on_save_button_clicked")
    def _commit_changes(self):
        """Commit changes to the settings file then hide self."""
        if (self.game_input.text() != settings['game_folder']
                and path.isdir(self.game_input.text())):
            settings['game_folder'] = self.game_input.text()
        if (self.repo_input.text() != settings['local_repository']
                and path.isdir(self.repo_input.text())):
            settings['local_repository'] = self.repo_input.text()
        if (not settings['language']
                or self.language_combo_box.currentData() != settings['language']):
            settings['language'] = self.language_combo_box.currentData()
            qInformation(_("Please restart qMM to finalize language change."))
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

    def __init__(self, filename: str, archive_manager: ArchivesCollection):
        super().__init__()
        self._filename = filename
        self.archive_instance = archive_manager[filename]
        self._key = path.basename(filename)
        self._data = archive_manager[filename].status()
        self._stat = archive_manager.stat(filename)
        self._name = None
        self._modified = None
        self._hashsum = archive_manager.hashsums(filename)

        self._files_str = ""
        self._matched_str = ""
        self._missing_str = ""
        self._mismatched_str = ""
        self._ignored_str = ""
        self._conflicts_str = ""

        self._built_strings = False

        self.setText(self.filename)  # filename == _key
        self._format_strings()

    def _format_strings(self):
        self._files_str = _format_regular(
            title=_("Archive's content"),
            items=list(self.archive_instance.files(exclude_directories=True)))
        self._matched_str = _format_regular(
            title=_("Files installed"),
            items=list(self.archive_instance.matched()))
        self._missing_str = _format_regular(
            title=_("Missing from the game folder"),
            items=list(self.archive_instance.missing()))
        self._mismatched_str = _format_regular(
            title=_("Same name and different CRC or same CRC with different names"),
            items=list(self.archive_instance.mismatched()))
        self._conflicts_str = _format_conflicts(
            title=_("Conflicting files between archives"),
            items=self.archive_instance.conflicts)
        self._ignored_str = _format_regular(
            title=_("Files present in the archive but ignored"),
            items=list(self.archive_instance.ignored()))
        self._built_strings = True

    def refresh_strings(self):
        """Called when the game's folder state changed

        Reinitialize the widget's strings, recompute the conflicts then redo
        all triaging and formatting.
        """
        self.archive_instance.reset_status()
        self.archive_instance.reset_conflicts()
        self._built_strings = False
        self._format_strings()

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
    def modified(self):
        """Return last modified time for an archive, usually time of creation"""
        if not self._modified:
            self._modified = timestamp_to_string(self._stat.st_mtime)
        return self._modified

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
        return self._files_str

    @property
    def matched(self):
        """Returns a formatted string containing all files matched on the filesystem"""
        return self._matched_str

    @property
    def missing(self):
        """Return a string representing the list of missing files."""
        return self._missing_str

    @property
    def mismatched(self):
        """Return a string representing the mismatched elements."""
        return self._mismatched_str

    @property
    def conflicts(self):
        return self._conflicts_str

    @property
    def skipped(self):
        return self._ignored_str


def _format_regular(title, items):
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
    for filepath, archives in items():
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
