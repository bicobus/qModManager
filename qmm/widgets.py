# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Contains various Qt Widgets used internally by the application."""

import logging
from os import path
from typing import Iterable, List, Union

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, QSize
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem

from qmm.bucket import FileMetadata
from qmm.common import settings, timestamp_to_string
from qmm.filehandler import (
    ArchivesCollection,
    ArchiveInstance,
    LITERALS,
    TRANSLATED_LITERALS,
)
from qmm.lang import LANGUAGE_CODES, get_locale  # , normalize_locale
from qmm.ui_about import Ui_About
from qmm.ui_settings import Ui_Settings

logger = logging.getLogger(__name__)
FILESTATE_COLORS = {
    "matched": (91, 135, 33, 255),  # greenish
    "mismatched": (132, 161, 225, 255),  # blueish
    "missing": (237, 213, 181, 255),  # (225, 185, 132, 255),  # yellowish
    "conflicts": (135, 33, 39, 255),  # red-ish
    "ignored": (219, 219, 219, 255),  # gray
}


class QAbout(QtWidgets.QWidget, Ui_About):
    """About window displaying various informations about the software."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        font = QtGui.QFont()
        font.setFamily("Unifont")
        font.setPointSize(11)
        self.text_author.setFont(font)


class QSettings(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__(flags=Qt.Window)
        self.centralwidget = None
        self.settingwidget = None
        self.statusbar = None
        self.setup_ui()

    def setup_ui(self):
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
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred
        )
        size_policy.setHorizontalStretch(0)
        size_policy.setVerticalStretch(0)
        size_policy.setHeightForWidth(
            self.settingwidget.sizePolicy().hasHeightForWidth()
        )

        self.statusbar = QtWidgets.QStatusBar(self)
        self.statusbar.setObjectName("statusbar")
        self.setStatusBar(self.statusbar)
        newsize = self.sizeHint() + self.settingwidget.sizeHint()
        self.resize(newsize)
        self.settingwidget.save_button.clicked.connect(self.hide)
        self.settingwidget.cancel_button.clicked.connect(self.hide)

    def show(self):
        """Show the window and assign internal variables."""
        super().show()
        self.settingwidget.game_input.setText(settings["game_folder"])
        self.settingwidget.repo_input.setText(settings["local_repository"])

    def set_mode(self, first_run=False):
        if first_run:
            self.settingwidget.cancel_button.setEnabled(False)
            self.setWindowFlag(Qt.WindowCloseButtonHint, on=False)
        else:
            self.settingwidget.cancel_button.setEnabled(True)
            self.setWindowFlag(Qt.WindowCloseButtonHint, on=True)

    def connect_to_savebutton(self, callback):
        return self.settingwidget.save_button.clicked.connect(callback)

    def disconnect_from_savebutton(self, callback):
        self.settingwidget.save_button.disconnect(callback)


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
        current_idx = self.language_combo_box.findData(get_locale())
        self.language_combo_box.setCurrentIndex(current_idx)
        self.language_combo_box.setDisabled(True)

    @pyqtSlot(name="on_game_button_clicked")
    def _set_game_directory(self):
        """Show a file selection window to the user."""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.game_label.text(),
            directory=settings["game_folder"],
        )  # noqa pycharm

        if value and value != settings["game_folder"]:
            self.game_input.setText(value)

    @pyqtSlot(name="on_repo_button_clicked")
    def _set_repository_directory(self):
        """Show a file selection window to use user."""
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.repo_label.text(),
            directory=settings["local_repository"],
        )  # noqa pycharm
        if value and value != settings["local_repository"]:
            self.repo_input.setText(value)

    @pyqtSlot(name="on_save_button_clicked")
    def _commit_changes(self):
        """Commit changes to the settings file then hide self."""
        game_input = self.game_input.text()
        repo_input = self.repo_input.text()
        if game_input != settings["game_folder"] and path.isdir(game_input):
            settings["game_folder"] = game_input
        if repo_input != settings["local_repository"] and path.isdir(repo_input):
            settings["local_repository"] = repo_input
        # XXX: disable language settings until feature fully developed
        # if (not settings['language']
        #         or self.language_combo_box.currentData() != settings['language']):
        #     if settings['language'] != normalize_locale(get_locale()):
        #         logger.debug(
        #             "New lang: %s; From lang: %s (norm: %s)",
        #             settings['language'],
        #             get_locale(),
        #             normalize_locale(get_locale())
        #         )
        #         qInformation(_(
        #             "You changed the software's locale, changes will be taken "
        #             "into account at the next software launch."
        #         ))
        #     settings['language'] = self.language_combo_box.currentData()

    @pyqtSlot(name="on_cancel_button_clicked")
    def on_cancel_button_clicked(self):
        """Simply hide the window.

        The default values are being defined within the show method, thus
        there is nothing here for us to do.

        Returns:
            void
        """
        self.hide()


def autoresize_columns(tree_widget: QTreeWidget):
    """Resize all columns of a QTreeWidget to fit content."""
    tree_widget.expandAll()
    for i in range(0, tree_widget.columnCount() - 1):
        tree_widget.resizeColumnToContents(i)


def _create_treewidget(text: Union[str, List], parent, tooltip: str = None, color=None):
    w = QTreeWidgetItem(parent)
    if isinstance(text, str):
        text = [text]
    for idx, string in enumerate(text):
        w.setText(idx, string)
        if color:
            w.setBackground(idx, QtGui.QColor(*color))
    if tooltip:
        w.setToolTip(0, tooltip)
    return w


def build_tree_from_path(
    item: FileMetadata, parent: QTreeWidget, folders, color=None, extra_column=None
):
    """Generate a set of related :func:`PyQt5.QtWidgets.QTreeWidgetItem` based
    on a file path.

    Args:
        item: a :obj:`qmm.bucket.FileMetadata` object.
        parent: The container widget to anchor the first node to.
        folders: A dict containing the parents widgets.
        color: Background color value for the widget.
        extra_column: Extra values to pass down to :func:`_create_treewidget`

    Returns:
        dict: A dictionnary containing the folders ancestry.
    """

    def _gv(val):
        x = [val]
        if extra_column:
            x.extend(extra_column)
        return x

    folder, file = item.split()
    folder_list = folder.split("/")
    key = None
    for idx, folder in enumerate(folder_list):
        key = ".".join(folder_list[i] for i in range(0, idx + 1))
        if key not in folders.keys():
            if idx > 0:
                pkey = ".".join(folder_list[i] for i in range(0, idx))
                p = folders[pkey]
            else:
                p = parent
            folders.setdefault(key, _create_treewidget(_gv(folder), parent=p))
    if file != "":
        _create_treewidget(_gv(file), folders[key], tooltip=item.path, color=color)
    return folders


def build_ignored_tree_widget(
    tree_widget: QTreeWidget, ignored_iter: Iterable[FileMetadata]
):
    parent_folders = {}
    for item in ignored_iter:
        build_tree_from_path(item, tree_widget, parent_folders)


def build_tree_widget(container: QTreeWidget, archive_instance: ArchiveInstance):
    parent_folders = {}
    for item in archive_instance.files():
        status = archive_instance.get_status(item)
        build_tree_from_path(
            item,
            container,
            parent_folders,
            color=FILESTATE_COLORS[LITERALS[status]],
            extra_column=[TRANSLATED_LITERALS[status]],
        )


def build_conflict_tree_widget(
    container: QTreeWidget, archive_instance: ArchiveInstance
):
    for root, conflicts in archive_instance.conflicts():
        root_widget = QTreeWidgetItem()
        root_widget.setText(0, root)
        root_widget.setText(1, "")
        for item in conflicts:
            if isinstance(item, FileMetadata):
                content = [item.path, item.origin]
            else:
                content = [item, "Archive"]
            _create_treewidget(content, root_widget)
        container.addTopLevelItem(root_widget)


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

        self._built_strings = False

        self.setText(self.filename)  # filename == _key
        self.set_gradients()
        self.set_text_color()

    def set_gradients(self):
        gradient = QtGui.QLinearGradient(75, 75, 150, 150)
        if self.archive_instance.has_mismatched:
            gradient.setColorAt(0, QtGui.QColor(*FILESTATE_COLORS["mismatched"]))
        elif (
            self.archive_instance.all_matching and not self.archive_instance.all_ignored
        ):
            gradient.setColorAt(0, QtGui.QColor(*FILESTATE_COLORS["matched"]))
        elif self.archive_instance.has_matched and self.archive_instance.has_missing:
            gradient.setColorAt(0, QtGui.QColor(*FILESTATE_COLORS["missing"]))
        else:
            gradient.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        if self.archive_instance.has_conflicts:
            gradient.setColorAt(1, QtGui.QColor(*FILESTATE_COLORS["conflicts"]))
        brush = QtGui.QBrush(gradient)
        self.setBackground(brush)

    def set_text_color(self):
        if self.archive_instance.all_ignored:
            self.setForeground(QtGui.QColor("gray"))

    def refresh_strings(self):
        """Called when the game's folder state changed.

        Reinitialize the widget's strings, recompute the conflicts then redo
        all triaging and formatting.
        """
        self.archive_instance.reset_status()
        self.archive_instance.reset_conflicts()
        self.set_gradients()

    @property
    def name(self):
        """Return the name of the archive, formatted for GUI usage.

        Transfrom the '_' character into space.
        """
        if not self._name:
            self._name = self._key.replace("_", " ")
        return self._name

    @property
    def filename(self):
        """Returns the name of the archive filename, suitable for path manipulations."""
        return self._key

    @property
    def modified(self):
        """Return last modified time for an archive, usually time of creation."""
        if not self._modified:
            self._modified = timestamp_to_string(self._stat.st_mtime)
        return self._modified

    @property
    def hashsum(self):
        """Returns the sha256 hashsum of the archive."""
        if self._hashsum:
            return self._hashsum
        return ""


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
