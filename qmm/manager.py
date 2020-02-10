#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>
"""Handles the Qt main window."""
import logging
from PyQt5.QtCore import pyqtSlot, QEvent, Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QFileDialog, QMenu
from PyQt5 import QtGui
from . import dialogs, widgets, filehandler
from .ui_mainwindow import Ui_MainWindow
from .config import get_config_dir
from .common import settings_are_set
from .widgets import QSettings, QAbout

logger = logging.getLogger(__name__)


class CustomMenu:
    def __init__(self):
        super().__init__()
        self._menu_obj = QMenu()
        self._install_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-install.svg")),
            "Install")
        self._uninstall_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-uninstall.svg")),
            "Uninstall")
        self._delete_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/trash.svg")),
            "Delete")

    def setup_menu(self, obj):
        obj.setContextMenuPolicy(Qt.CustomContextMenu)
        obj.customContextMenuRequested.connect(self._do_menu_actions)

    def _do_menu_actions(self, position):
        raise NotImplementedError()


class EventDropFilter:
    def __init__(self):
        super().__init__()
        self._objects = []

    def setup_filters(self, objects):
        for obj in objects:
            obj.installEventFilter(self)
            self._objects.append(obj.objectName())

    def eventFilter(self, o, e):  # noqa
        if o.objectName() in self._objects:
            if e.type() == QEvent.DragEnter:
                e.acceptProposedAction()
                return True
            if e.type() == QEvent.Type.Drop:
                return self._on_drop_action(e)
        # return false ignores the event and allow further propagation
        return False

    def _on_drop_action(self, e):
        raise NotImplementedError()


class MainWindow(QMainWindow, EventDropFilter, CustomMenu, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("qModManager")
        self.setup_filters([self.listWidget])
        self.setup_menu(self.listWidget)
        # Will do style using QT, see TODO file
        # loadQtStyleSheetFile('style.css', self)

        self._settings_window = None
        self._about_window = None
        self.managed_archives = filehandler.ArchivesCollection()
        self._qc = {}
        self.__connection_link = None
        self._init_settings()

    def _do_menu_actions(self, position):
        right_click_action = self._menu_obj.exec_(self.listWidget.mapToGlobal(position))
        item = self.listWidget.item(self.listWidget.indexAt(position).row())
        if right_click_action == self._install_action:
            self._do_install_selected_mod(item)
        if right_click_action == self._uninstall_action:
            self._do_uninstall_selected_mod(item)
        if right_click_action == self._delete_action:
            self._do_delete_selected_file(item)

    def _init_settings(self):
        if not settings_are_set():
            self.do_settings(first_launch=True)
        else:
            self._init_mods()

    def _init_mods(self):
        p_dialog = dialogs.qProgress(
            parent=self, title="Computing data",
            message="Please wait for the software to initialize it's data."
        )
        p_dialog.show()

        filehandler.build_game_files_crc32(p_dialog.progress)
        filehandler.build_loose_files_crc32(p_dialog.progress)
        self.managed_archives.build_archives_list(p_dialog.progress)

        p_dialog.progress("", category="Conflict detection")
        filehandler.detect_conflicts_between_archives(self.managed_archives)

        p_dialog.progress("", category="Parsing archives")
        for archive_name in self.managed_archives.keys():
            item = widgets.ListRowItem(
                filename=archive_name,
                data=filehandler.missing_matched_mismatched(
                    self.managed_archives[archive_name]),
                stat=self.managed_archives.stat(archive_name),
                hashsum=self.managed_archives.hashsums(archive_name)
            )
            self._add_item_to_list(item)
        p_dialog.done(1)

    def _add_item_to_list(self, item):
        self.listWidget.addItem(item)
        # Sets the widget to be displayed in the given item .
        # self.ui.listWidget.setItemWidget(item, item._widget)

    def set_tab_color(self, index, color: QtGui.QColor = None) -> None:
        """Manage tab text color.

        Helper to _on_selection_change.

        Store the default text color of a tab in order to restore it
        whenever the selected element in the linked list changes.

        Args:
            index: index of the tab
            color: new color of the text
        """
        if index not in self._qc.keys():  # Cache default color
            self._qc[index] = self.tabWidget.tabBar().tabTextColor(index)

        if not color:
            color = self._qc[index]
        self.tabWidget.tabBar().setTabTextColor(index, color)

    @pyqtSlot(name="on_listWidget_itemSelectionChanged")
    def _on_selection_change(self) -> None:
        """Change the tab color to match the selected element in linked list.

        rgb(135, 33, 39) # redish
        rgb(78, 33, 135) # blueish
        rgb(91, 135, 33) # greenish
        """
        items = self.listWidget.selectedItems()
        if not items:
            return

        item = items[0]
        self.content_name.setText(item.name)
        self.content_added.setText(item.added)
        self.content_hashsum.setText(item.hashsum)

        self.tab_files_content.setPlainText(item.files)

        matched_idx = self.tabWidget.indexOf(self.tab_matched)
        if item.has_matched:
            self.set_tab_color(matched_idx, QtGui.QColor(91, 135, 33))
        else:
            self.set_tab_color(matched_idx)
        self.tab_matched_content.setPlainText(item.matched)

        mismatched_idx = self.tabWidget.indexOf(self.tab_mismatched)
        if item.has_mismatched:
            self.set_tab_color(mismatched_idx, QtGui.QColor(78, 33, 135))
        else:
            self.set_tab_color(mismatched_idx)
        self.tab_mismatched_content.setPlainText(item.mismatched)

        self.tab_missing_content.setPlainText(item.missing)

        skipped_idx = self.tabWidget.indexOf(self.tab_skipped)
        if item.has_skipped:
            self.set_tab_color(skipped_idx, QtGui.QColor(135, 33, 39))
        else:
            self.set_tab_color(skipped_idx)
        self.tab_skipped_content.setPlainText(item.skipped)

        conflict_idx = self.tabWidget.indexOf(self.tab_conflicts)
        if item.has_conflicts:
            self.set_tab_color(conflict_idx, QtGui.QColor(135, 33, 39))
        else:
            self.set_tab_color(conflict_idx)
        self.tab_conflicts_content.setPlainText(item.conflicts)

    @pyqtSlot(name="on_actionOpen_triggered")
    def _do_add_new_mod(self):
        if not settings_are_set():
            dialogs.qWarning(
                "You must set your game folder location."
            )
            return

        qfd = QFileDialog(self)
        filters = ["Archives (*.7z *.zip *.rar)"]
        qfd.setNameFilters(filters)
        qfd.selectNameFilter(filters[0])
        qfd.fileSelected.connect(self._on_action_open_done)
        qfd.exec_()

    def _get_selected_item(self, default: widgets.ListRowItem = None) -> widgets.ListRowItem:
        items = self.listWidget.selectedItems()
        if not items:
            return default
        return items[0]

    @pyqtSlot(name="on_actionRemove_file_triggered")
    def _do_delete_selected_file(self, menu_item=None):
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_delete_selected_file without a selection")
            return

        ret = dialogs.qWarningYesNo(
            "This action will uninstall the mod, then delete the archive from "
            "your filesystem.\n\nDo you want to continue?"
        )
        if not ret:
            return

        if item.has_matched:
            ret = self._do_uninstall_selected_mod()
            if not ret:
                return
        filehandler.delete_archive(item.filename)
        del self.managed_archives[item.filename]
        filehandler.detect_conflicts_between_archives(self.managed_archives)

    @pyqtSlot(name="on_actionInstall_Mod_triggered")
    def _do_install_selected_mod(self, menu_item=None):
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_install_selected_mod without a selection")
            return

        files = filehandler.install_archive(item.filename, item.install_info())
        if not files:
            dialogs.qWarning(
                f"The archive {item.filename} extracted with errors.\n"
                f"Please refer to {get_config_dir('error.log')} for more information."
            )
        else:
            filehandler.detect_conflicts_between_archives(self.managed_archives)
            self._refresh_list_item_strings()
            self._on_selection_change()

    @pyqtSlot(name="on_actionUninstall_Mod_triggered")
    def _do_uninstall_selected_mod(self, menu_item=None):
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("triggered without item to process")
            return False

        if item.has_mismatched:
            dialogs.qInformation(
                "Unable to uninstall mod: mismatched items exists on drive.\n"
                "This is most likely due to another installed mod conflicting "
                "with this mod.\n"
            )
            return False

        if filehandler.uninstall_files(item.list_matched(include_folders=True)):
            filehandler.detect_conflicts_between_archives(self.managed_archives)
            self._refresh_list_item_strings()
            self._on_selection_change()
            return True

        dialogs.qWarning(
            "The uninstallation process failed at some point. Please "
            "report this happened to the developper alongside the error "
            f"file {get_config_dir('error.log')}."
        )
        return False

    @pyqtSlot(name="on_actionSettings_triggered")
    def do_settings(self, first_launch=False):
        """Show the settings window.

        Args:
            first_launch (bool):
                If true, disable cancel button and bind the save button to
                MainWindow_init_mods
        """
        if not self._settings_window:
            self._settings_window = QSettings()
        if first_launch:
            button = self._settings_window.save_button
            self.__connection_link = button.clicked.connect(self._init_mods)
            self._settings_window.set_mode(first_run=True)
        else:
            if self.__connection_link:
                button = self._settings_window.save_button
                button.disconnect(self.__connection_link)
                self._settings_window.set_mode(first_run=False)
        self._settings_window.set_mode(first_launch)
        self._settings_window.show()

    @pyqtSlot(name="on_actionAbout_triggered")
    def do_about(self):
        """Show the about window."""
        if not self._about_window:
            self._about_window = QAbout()
        self._about_window.show()

    def _on_drop_action(self, e):
        if e.mimeData().urls():  # Makes sure we have urls
            logger.info("Received drop event with files %s", [f.path for f in e.mimeData().urls()])
            for uri in e.mimeData().urls():
                self._on_action_open_done(uri.path())
            return True
        return False

    def _refresh_list_item_strings(self):
        for idx in range(0, self.listWidget.count()):
            self.listWidget.item(idx).refresh_strings()

    def _on_action_open_done(self, filename):
        """Callback to QFileDialog once a file is selected."""
        hashsum = filehandler.sha256hash(filename)

        if not self.managed_archives.find(hashsum=hashsum):
            archive_name = filehandler.copy_archive_to_repository(filename)
            if not archive_name:
                dialogs.qWarning(
                    "A file with the same name already exists in the repository."
                )
                return False
            self.managed_archives.add_archive(filename, hashsum)
            filehandler.conflicts_process_files(
                files=self.managed_archives[archive_name],
                archives_list=self.managed_archives,
                current_archive=archive_name,
                processed=None)

            item = widgets.ListRowItem(
                filename=archive_name,
                data=filehandler.missing_matched_mismatched(self.managed_archives[archive_name]),
                stat=self.managed_archives.stat(archive_name),
                hashsum=self.managed_archives.hashsums(archive_name))

            self._add_item_to_list(item)
            self._refresh_list_item_strings()
            self.listWidget.scrollToItem(item)
            return True

        dialogs.qWarning((
            "The file you selected is already present in the repository. "
            f"It may exists under a different name.\nHashsum matched: {hashsum}"
        ))
        return False


def main():
    import sys  # pylint: disable=import-outside-toplevel
    import signal  # pylint: disable=import-outside-toplevel
    import locale  # pylint: disable=import-outside-toplevel
    # Sets locale according to $LANG variable instead of C locale
    locale.setlocale(locale.LC_ALL, '')
    # Ends the application on CTRL+c
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    logger.info("Starting application")
    try:
        app = QApplication(sys.argv)
        QtGui.QFontDatabase.addApplicationFont(":/unifont.ttf")  # noqa PyCallByClass, PyArgumentList
        mainwindow = MainWindow()
        mainwindow.show()
        sys.exit(app.exec_())
    except Exception:
        logger.exception("Critical error occurred:")
        raise
    finally:
        logger.info("Application shutdown complete.")
