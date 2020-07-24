# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Contains various Qt Widgets used internally by the application."""

import logging
from os import path
from typing import Iterable, List, Union

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QObject, QProcess, QUrl
from PyQt5.QtWidgets import QAction, QMenu, QTreeWidget, QTreeWidgetItem

from qmm.bucket import FileMetadata
from qmm.common import timestamp_to_string, command, toolsalias
from qmm.filehandler import (
    ArchivesCollection,
    ArchiveInstance,
    LITERALS,
    TRANSLATED_LITERALS,
)
from qmm.ui_about import Ui_About  # pylint: disable=no-name-in-module

logger = logging.getLogger(__name__)
#: Gradients of colors for each file of the tree widget.
FILESTATE_COLORS = {
    "matched": (91, 135, 33, 255),  # greenish
    "mismatched": (132, 161, 225, 255),  # blueish
    "missing": (237, 213, 181, 255),  # (225, 185, 132, 255),  # yellowish
    "conflicts": (135, 33, 39, 255),  # red-ish
    "ignored": (219, 219, 219, 255),  # gray
}

# NOTE: Investigate QDesktopServices if os.startfile is failing on windows
# def qopenpath(tool):
#     toolpath = command(tool, alias=True)
#     QtGui.QDesktopServices(QUrl(tool))


class QAbout(QtWidgets.QWidget, Ui_About):
    """About window displaying various informations about the software."""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        font = QtGui.QFont()
        font.setFamily("Unifont")
        font.setPointSize(11)
        self.text_author.setFont(font)


class TreeWidgetMenu(QObject):
    def __init__(self, treewidget: QTreeWidget):
        super().__init__(parent=treewidget)
        self.treewidget = treewidget
        try:
            svgedit = command("svgedit", True)
            svgtoolname = toolsalias["svgedit"]
        except KeyError:
            svgedit = None
            svgtoolname = "Default Application"
        self.svgedit = svgedit
        self.svgtext = svgtoolname

        try:
            xmledit = command("xmledit", True)
            xmltoolname = toolsalias["xmledit"]
        except KeyError:
            xmledit = None
            xmltoolname = "Default Application"
        self.xmledit = xmledit
        self.xmltext = xmltoolname

    def show_menu(self, position):
        widget_row = self.treewidget.itemAt(position)
        logger.debug("TREEMENU: menu called")
        if not isinstance(widget_row, ArchiveFilesTreeRow):
            logger.debug("TREEMENU: widget row isn't compatible")
            return

        menu = QMenu()
        open_dir = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/folder-open.svg")), _("Open in Explorer"), menu,
        )
        open_svg = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/image-edit.svg")),
            _("Open with {}").format(self.svgtext),
            menu,
        )
        open_xml = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-edit.svg")),
            _("Open with {}").format(self.xmltext),
            menu,
        )
        uri = widget_row.filemetadata.pathobj.as_uri()
        parent_uri = widget_row.filemetadata.pathobj.parent.as_uri()
        if not widget_row.filemetadata.exists():
            logger.debug("TREEMENU: File Doesn't Exists: disabling.")
            open_dir.setDisabled(True)
            open_svg.setDisabled(True)
            open_xml.setDisabled(True)
        elif widget_row.filemetadata.is_dir():
            logger.debug("TREEMENU: from folder, open folder '%s'", uri)
            open_dir.triggered.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl(uri)))
            open_svg.setDisabled(True)
            open_xml.setDisabled(True)
        else:
            filetype = widget_row.filemetadata.pathobj.suffix
            logger.debug("TREEMENU: from file, open folder '%s'", uri)
            open_dir.triggered.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl(parent_uri)))
            # We do not want to open an xml file with a svg editor
            if filetype != ".svg":
                open_svg.setDisabled(True)
            elif not self.svgedit:
                open_svg.triggered.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl(uri)))
            else:
                open_svg.triggered.connect(
                    lambda: QProcess.startDetached(str(self.svgedit), [uri], parent_uri)
                )
            # svg are xml files
            if not self.xmledit:
                open_xml.triggered.connect(lambda: QtGui.QDesktopServices.openUrl(QUrl(uri)))
            else:
                open_xml.triggered.connect(
                    lambda: QProcess.startDetached(str(self.xmledit), [uri], parent_uri)
                )

        menu.addAction(open_dir)
        menu.addAction(open_svg)
        menu.addAction(open_xml)
        action = menu.exec_(self.treewidget.mapToGlobal(position))
        logger.debug("TREEMENU: action triggered '%s'", action)
        logger.debug("TREEMENU: widget row: %s", widget_row)


def autoresize_columns(tree_widget: QTreeWidget):
    """Resize all columns of a QTreeWidget to fit content."""
    tree_widget.expandAll()
    for i in range(0, tree_widget.columnCount() - 1):
        tree_widget.resizeColumnToContents(i)


def _create_treewidget(
    text: Union[str, List], parent, tooltip: str = None, color=None, icon=None
):
    w = QTreeWidgetItem(parent)
    if isinstance(text, str):
        text = [text]
    for idx, string in enumerate(text):
        w.setText(idx, string)
        if color:
            w.setBackground(idx, QtGui.QColor(*color))
    if tooltip:
        w.setToolTip(0, tooltip)
    if icon:
        w.setIcon(0, QtGui.QIcon(QtGui.QPixmap(icon)))
    return w


def build_tree_from_path(item: FileMetadata, parent: QTreeWidget, folders, color=None, **kwargs):
    """Generate a set of related :func:`PyQt5.QtWidgets.QTreeWidgetItem` based
    on a file path.

    If *extra_column* is specified, it must be a list containing text that will
    be used to create new columns after the first one. Useful to add extra
    information.

    Args:
        item: a :obj:`qmm.bucket.FileMetadata` object.
        parent: The container widget to anchor the first node to.
        folders: A dict containing the parents widgets.
        color (Optional[List]): Background color value for the widget.
    Keyword Args:
        extra_column (List[str]): Extra values to pass down to
            :func:`_create_treewidget`

    Returns:
        dict: A dictionnary containing the folders ancestry.
    """

    def _gv(val, extra=None):
        x = [val]
        if extra:
            x.extend(extra)
        return x

    finder = kwargs.get("finder")
    folder, file = item.split()
    folder_list = folder.split("/")
    key = None
    for idx, folder in enumerate(folder_list):
        key = "/".join(folder_list[i] for i in range(0, idx + 1))
        if key not in folders.keys():
            if idx > 0:
                pkey = "/".join(folder_list[i] for i in range(0, idx))
                p = folders[pkey]
            else:
                p = parent
            if finder:
                fmd = finder(key)
                widget = ArchiveFilesTreeRow(
                    text=_gv(folder, [TRANSLATED_LITERALS[fmd[1]]]),
                    parent=p,
                    item=fmd[0],
                    tooltip=fmd[0].path,
                    color=color,
                    icon=":/icons/folder.svg",
                    filetype="directory",
                )
            else:
                widget = _create_treewidget(_gv(folder), parent=p, icon=":/icons/folder.svg")
            folders.setdefault(key, widget)
    if file:
        pos = file.rfind(".") + 1
        icon = None
        if file[pos:] == "xml":
            icon = ":/icons/file-text.svg"
        elif file[pos:] == "svg":
            icon = ":/icons/file-code.svg"
        ArchiveFilesTreeRow(
            text=_gv(file, kwargs.get("extra_column")),
            parent=folders[key],
            item=item,
            tooltip=item.path,
            color=color,
            icon=icon,
            filetype="file",
        )
    return folders


def build_ignored_tree_widget(container: QTreeWidget, ignored_iter: Iterable[FileMetadata]):
    parent_folders = {}
    for item in ignored_iter:
        build_tree_from_path(item, container, parent_folders)


def build_tree_widget(container: QTreeWidget, archive_instance: ArchiveInstance):
    parent_folders = {}
    for item in archive_instance.files():
        status = archive_instance.get_status(item)
        build_tree_from_path(
            item=item,
            parent=container,
            folders=parent_folders,
            color=FILESTATE_COLORS[LITERALS[status]],
            extra_column=[TRANSLATED_LITERALS[status]],
            finder=archive_instance.find,
        )


def build_conflict_tree_widget(container: QTreeWidget, archive_instance: ArchiveInstance):
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


class ArchiveFilesTreeRow(QtWidgets.QTreeWidgetItem):
    def __init__(
        self,
        text: Union[str, List],
        parent,
        item: FileMetadata,
        tooltip: str = None,
        color=None,
        icon=None,
        **extra,
    ):
        super().__init__(parent)
        self.filemetadata = item
        extra.setdefault("filetype", "directory")
        self._extra = extra

        if isinstance(text, str):
            text = [text]
        for idx, string in enumerate(text):
            self.setText(idx, string)
            if color:
                self.setBackground(idx, QtGui.QColor(*color))
        if tooltip:
            self.setToolTip(0, tooltip)
        if icon:
            self.setIcon(0, QtGui.QIcon(QtGui.QPixmap(icon)))


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
        elif self.archive_instance.all_matching and not self.archive_instance.all_ignored:
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
