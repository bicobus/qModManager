# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>
"""Handles the Qt main window."""
import logging
import pathlib

from PyQt5 import QtGui
from PyQt5.QtCore import QEvent, QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMenu
from watchdog.events import (EVENT_TYPE_CREATED, EVENT_TYPE_DELETED, EVENT_TYPE_MODIFIED, EVENT_TYPE_MOVED,
                             FileSystemEventHandler)
from watchdog.observers import Observer

from . import dialogs, filehandler, widgets
from .common import settings, settings_are_set, valid_suffixes
from .config import get_config_dir
from .lang import set_gettext
from .ui_mainwindow import Ui_MainWindow
from .widgets import QAbout, QSettings

logger = logging.getLogger(__name__)


class ArchiveAddedEventHandler(FileSystemEventHandler, QObject):
    sgn_moved = pyqtSignal([tuple])
    sgn_created = pyqtSignal([tuple])
    sgn_deleted = pyqtSignal([tuple])
    sgn_modified = pyqtSignal([tuple])

    def __init__(self):
        super().__init__()
        self._active = True
        self._accept = []
        self._ignored = {
            EVENT_TYPE_MOVED: [],
            EVENT_TYPE_CREATED: [],
            EVENT_TYPE_DELETED: [],
            EVENT_TYPE_MODIFIED: []
        }

    def ignore(self, src_path, event_type):
        if src_path in self._ignored[event_type]:
            return
        self._ignored[event_type].append(src_path)

    def clear(self, src_path, event_type):
        if src_path not in self._ignored[event_type]:
            return
        self._ignored[event_type].remove(src_path)

    def suspend(self, active: bool):
        if active:
            logger.debug("Window in focus: activating file system watch.")
        else:
            logger.debug("Window out of focus: suspending file system watch.")
        self._active = active

    def on_moved(self, event):
        if event.is_directory or not self._active:
            return
        self.sgn_moved.emit(event.key)

    def on_created(self, event):
        if event.is_directory or not self._active:
            return
        if pathlib.PurePath(event.src_path).suffix in valid_suffixes('pathlib'):
            self._accept.append(event.src_path)
            self.sgn_created.emit(event.key)

    def on_deleted(self, event):
        if event.is_directory or not self._active:
            return
        self.sgn_deleted.emit(event.key)

    def on_modified(self, event):
        if not self._active:
            return
        if event.src_path in self._accept:
            self._accept.remove(event.src_path)
            self.sgn_modified.emit(event.key)


class CustomMenu:
    def __init__(self):
        super().__init__()
        self._menu_obj = QMenu()
        self._install_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-install.svg")),
            _("Install"))
        self._uninstall_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-uninstall.svg")),
            _("Uninstall"))
        self._delete_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/trash.svg")),
            _("Delete"))

    def setup_menu(self, obj):
        obj.setContextMenuPolicy(Qt.CustomContextMenu)
        obj.customContextMenuRequested.connect(self._do_menu_actions)

    def _do_menu_actions(self, position):
        raise NotImplementedError()


class QEventFilter:
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


class MainWindow(QMainWindow, QEventFilter, CustomMenu, Ui_MainWindow):
    fswatch_suspend = pyqtSignal(bool)
    fswatch_ignore = pyqtSignal(['QString', 'QString'])
    fswatch_clear = pyqtSignal(['QString', 'QString'])

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
        self._window_was_active = None
        self._init_settings()

        # File watchers
        ar_handler = ArchiveAddedEventHandler()
        # TODO: moved handler
        # ar_handler.sgn_moved.connect(self.observer_cb)
        # ar_handler.sgn_created.connect(self.observer_cb)
        ar_handler.sgn_deleted.connect(self._on_fs_deleted)
        ar_handler.sgn_modified.connect(self._on_fs_modified)
        self.fswatch_ignore.connect(ar_handler.ignore)
        self.fswatch_clear.connect(ar_handler.clear)
        self.fswatch_suspend.connect(ar_handler.suspend)
        self._observer = Observer()
        self._observer.schedule(ar_handler, settings['local_repository'])
        self._observer.start()

    def __del__(self):
        if self._observer.is_alive():
            self._observer.stop()

    def changeEvent(self, e):
        """Override to suspend activity in the watchdog handler."""
        super().changeEvent(e)
        self.fswatch_suspend.emit(self.isActiveWindow())
        if (self.isActiveWindow() and
                isinstance(self._window_was_active, bool) and
                not self._window_was_active):
            logger.debug("Refresh archives.")
            for etype, archive_name, item in self.managed_archives.refresh():
                if etype == self.managed_archives.FileAdded:
                    row = widgets.ListRowItem(
                        filename=archive_name,
                        data=filehandler.missing_matched_mismatched(item),
                        stat=self.managed_archives.stat(archive_name),
                        hashsum=self.managed_archives.hashsums(archive_name)
                    )
                    self._add_item_to_list(row)
                if etype == self.managed_archives.FileRemoved:
                    idx = self.listWidget.row(self.listWidget.findItems(archive_name, Qt.MatchExactly)[0])
                    self._remove_row(archive_name, idx, preserve_managed=True)
        self._window_was_active = self.isActiveWindow()

    def _init_settings(self):
        if not settings_are_set():
            self.do_settings(first_launch=True)
        else:
            self._init_mods()

    def _init_mods(self):
        p_dialog = dialogs.SplashProgress(
            parent=self, title=_("Computing data"),
            message=_("Please wait for the software to initialize it's data.")
        )
        p_dialog.show()

        filehandler.build_game_files_crc32(p_dialog.progress)
        filehandler.build_loose_files_crc32(p_dialog.progress)
        self.managed_archives.build_archives_list(p_dialog.progress)

        p_dialog.progress("", category=_("Conflict detection"))
        filehandler.detect_conflicts_between_archives(self.managed_archives, progress=p_dialog.progress)

        p_dialog.progress("", category=_("Parsing archives"))
        for archive_name in self.managed_archives.keys():
            p_dialog.progress(archive_name)
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

    def _remove_row(self, filename, row, preserve_managed=False):
        if not preserve_managed:
            del self.managed_archives[filename]
        self.listWidget.takeItem(row)
        filehandler.detect_conflicts_between_archives(self.managed_archives)

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
                _("You must set your game folder location.")
            )
            return

        qfd = QFileDialog(self)
        filters = valid_suffixes()
        qfd.setNameFilters(filters)
        qfd.selectNameFilter(filters[0])
        qfd.fileSelected.connect(self._on_action_open_done)
        qfd.exec_()

    def _get_selected_item(self, default: widgets.ListRowItem = None) -> widgets.ListRowItem:
        items = self.listWidget.selectedItems()
        if not items or default in items:
            return default
        return items[0]

    @pyqtSlot(name="on_actionRemove_file_triggered")
    def _do_delete_selected_file(self, menu_item=None):
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_delete_selected_file without a selection")
            return

        ret = dialogs.qWarningYesNo(_(
            "This action will uninstall the mod, then move the archive to your "
            "trashbin.\n\nDo you want to continue?"
        ))
        if not ret:
            return

        logger.info("Deletion of archive %s", item.filename)
        if item.has_matched:
            ret = self._do_uninstall_selected_mod()
            if not ret:
                return
        self.fswatch_ignore.emit(item.filename, EVENT_TYPE_DELETED)
        filehandler.delete_archive(item.filename)
        self._remove_row(item.filename, self.listWidget.row(item))
        self.fswatch_clear.emit(item.filename, EVENT_TYPE_DELETED)
        del item

    @pyqtSlot(name="on_actionInstall_Mod_triggered")
    def _do_install_selected_mod(self, menu_item=None):
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_install_selected_mod without a selection")
            return

        logger.info("Installing file %s", item.filename)
        files = filehandler.install_archive(item.filename, item.install_info())
        if not files:
            dialogs.qWarning(_(
                "The archive {filename} extracted with errors.\n"
                "Please refer to {loglocation} for more information.").format(
                filename=item.filename,
                loglocation=get_config_dir('error.log')))
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
            dialogs.qInformation(_(
                "Unable to uninstall mod: mismatched items exists on drive.\n"
                "This is most likely due to another installed mod conflicting "
                "with this mod.\n"
            ))
            return False

        logger.info("Uninstalling files from archive %s", item.filename)
        if filehandler.uninstall_files(item.list_matched(include_folders=True)):
            filehandler.detect_conflicts_between_archives(self.managed_archives)
            self._refresh_list_item_strings()
            self._on_selection_change()
            return True

        dialogs.qWarning(_(
            "The uninstallation process failed at some point. Please report "
            "this happened to the developper alongside with the error file "
            "{logfile}."
        ).format(logfile=get_config_dir('error.log')))
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

    def _refresh_list_item_strings(self):
        for idx in range(0, self.listWidget.count()):
            self.listWidget.item(idx).refresh_strings()

    def _on_action_open_done(self, filename, archive=None):
        """Callback to QFileDialog once a file is selected."""
        hashsum = filehandler.sha256hash(filename)

        if not self.managed_archives.find(hashsum=hashsum):
            if not archive:
                archive_name = filehandler.copy_archive_to_repository(filename)
            else:
                archive_name = archive
            if not archive_name:
                dialogs.qWarning(
                    _("A file with the same name already exists in the repository.")
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
            self.fswatch_clear(filename, EVENT_TYPE_CREATED)
            return True

        dialogs.qWarning(_(
            "The file you selected is already present in the repository. "
            "It may exists under a different name.\nHashsum matched: {hashsum}"
        ).format(hashsum=hashsum))
        return False

    ##########################
    # Context Menu overrides #
    ##########################
    def _do_menu_actions(self, position):
        right_click_action = self._menu_obj.exec_(self.listWidget.mapToGlobal(position))
        item = self.listWidget.item(self.listWidget.indexAt(position).row())
        if right_click_action == self._install_action:
            self._do_install_selected_mod(item)
        if right_click_action == self._uninstall_action:
            self._do_uninstall_selected_mod(item)
        if right_click_action == self._delete_action:
            self._do_delete_selected_file(item)

    #########################
    # Drag & Drop overrides #
    #########################
    def _on_drop_action(self, e):
        """Handle the drag&drop event.

        Filter input files through valid suffixes.
        """
        if not e.mimeData().urls():  # Makes sure we have urls
            logger.debug("Received drag&drop event with empty url list.")
            return False

        logger.info("Received drop event with files %s", [f.path for f in e.mimeData().urls()])
        for uri in e.mimeData().urls():
            pl = pathlib.PurePath(uri.path())
            if pl.suffix in valid_suffixes(output_format="pathlib"):
                logger.debug("Processing file %s", uri.path())
                self.fswatch_ignore(uri.path(), EVENT_TYPE_CREATED)
                self._on_action_open_done(uri.path())
        return True

    ######################
    # WatchDog callbacks #
    ######################
    def _on_fs_modified(self, e):
        filename = e[1]
        logger.info("New archive detected in the repository folder: %s", filename)
        self._on_action_open_done(filename, archive=pathlib.Path(filename).name)

    def _on_fs_deleted(self, e):
        item = pathlib.Path(e[1])
        rows = self.listWidget.findItems(item.name, Qt.MatchExactly)
        if rows:
            row = rows[0]
            self._remove_row(row.filename, self.listWidget.row(row))
            del row, rows
        # for idx in self.listWidget.count():
        #     row_item = self.listWidget.index(idx)
        #     if row_item.filename == item.name:
        #         self._remove_row(item.filename, self.listWidget.row(row_item))
        # del row_item


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
        # set_gettext() install's gettext _ in the builtins
        set_gettext()
        app = QApplication(sys.argv)
        QtGui.QFontDatabase.addApplicationFont(":/unifont.ttf")  # noqa PyCallByClass, PyArgumentList
        mainwindow = MainWindow()
        mainwindow.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.exception("Critical error occurred: %s", e)
        raise
    finally:
        logger.info("Application shutdown complete.")
