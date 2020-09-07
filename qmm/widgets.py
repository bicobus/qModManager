# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Contains various Qt Widgets used internally by the application."""
import logging
from typing import Iterable, List, Union

from PyQt5 import QtGui, QtWidgets
from PyQt5.QtCore import QObject, QProcess, QUrl
from PyQt5.QtWidgets import QAction, QMenu, QTreeWidget, QTreeWidgetItem

from qmm.ab.widgets import ABCListRowItem
from qmm.fileutils import FileState
from qmm.bucket import FileMetadata
from qmm.common import command, toolsalias
from qmm.filehandler import ArchiveInstance
from qmm.ui_about import Ui_About  # pylint: disable=no-name-in-module

logger = logging.getLogger(__name__)

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


def _path_from_list(path, length):
    return "/".join(path[i] for i in range(0, length))


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
    folder_list = folder.split("/") if folder else ["/"]
    key = None
    for idx, folder in enumerate(folder_list):
        key = _path_from_list(folder_list, idx + 1)
        if key not in folders.keys():
            if idx > 0:
                p = folders[_path_from_list(folder_list, idx)]
            else:
                p = parent
            if finder:
                fmd = finder(key)[0]
                status = FileState.MATCHED if fmd.exists() else FileState.MISSING
                widget = ArchiveFilesTreeRow(
                    text=_gv(folder, [str(status)]),
                    parent=p,
                    item=fmd,
                    tooltip=fmd.path,
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
            color=status.qcolor,
            extra_column=[str(status)],
            finder=archive_instance.find_metadata_by_path
            if isinstance(archive_instance, ListRowVirtualItem)
            else None,
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
        color: Union[QtGui.QColor, None] = None,
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
                self.setBackground(idx, color)
        if tooltip:
            self.setToolTip(0, tooltip)
        if icon:
            self.setIcon(0, QtGui.QIcon(QtGui.QPixmap(icon)))


class ListRowItem(ABCListRowItem):
    """ListWidgetItem representing one single archive."""
    pass


class ListRowVirtualItem(ABCListRowItem):
    def __init__(self, archive_manager):
        super().__init__(None, archive_manager)

    def _post_init(self):
        self._filename = self._key = "Virtual_Package"
        self.archive_instance = self.am.special
        self._stat = None
        self._name = None
        self._modified = "N/A"
        self._hashsum = "N/A"
        self.setText(self.name)

    def set_gradients(self):
        logger.error("Gradients shouldn't be set for the virtual package.")

    def refresh_strings(self):
        logger.error("Refresh Strings called on a virtual package, this must not be done.")
