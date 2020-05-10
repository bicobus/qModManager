# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2020 bicobus <bicobus@keemail.me>
"""Handles the Qt main window."""
import logging
import pathlib
from collections import deque
from typing import Tuple, Union

import watchdog.events
from PyQt5 import QtGui
from PyQt5.QtCore import QEvent, QObject, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
)
from watchdog.observers import Observer

from qmm import bucket, dialogs, filehandler
from qmm.common import settings, settings_are_set, valid_suffixes
from qmm.config import get_config_dir
from qmm.ui_mainwindow import Ui_MainWindow
from qmm.widgets import (
    ListRowItem,
    QAbout,
    QSettings,
    autoresize_columns,
    build_conflict_tree_widget,
    build_ignored_tree_widget,
    build_tree_widget,
)

logger = logging.getLogger(__name__)


class UnknownContext(Exception):
    pass


class QmmWdEventHandler:
    sgn_moved = pyqtSignal([tuple])
    sgn_created = pyqtSignal([tuple])
    sgn_deleted = pyqtSignal([tuple])
    sgn_modified = pyqtSignal([tuple])

    def __init__(self, moved_cb, created_cb, deleted_cb, modified_cb):
        super().__init__()
        self._active = True
        self._ignored = {
            watchdog.events.EVENT_TYPE_MOVED: [],
            watchdog.events.EVENT_TYPE_CREATED: [],
            watchdog.events.EVENT_TYPE_DELETED: [],
            watchdog.events.EVENT_TYPE_MODIFIED: [],
        }
        if moved_cb:
            self.sgn_moved.connect(moved_cb)
        if created_cb:
            self.sgn_created.connect(created_cb)
        if deleted_cb:
            self.sgn_deleted.connect(deleted_cb)
        if modified_cb:
            self.sgn_modified.connect(modified_cb)

    def ignore(self, src_path, event_type):
        """Ignore an event if path is found in it's ignore tuple."""
        if src_path in self._ignored[event_type]:
            return
        self._ignored[event_type].append(src_path)

    def clear(self, src_path, event_type):
        """Remove a path from the event's ignore tuple."""
        if src_path not in self._ignored[event_type]:
            return
        self._ignored[event_type].remove(src_path)


class GameModEventHandler(
    QmmWdEventHandler, watchdog.events.PatternMatchingEventHandler, QObject
):
    def __init__(self, moved_cb, created_cb, deleted_cb, modified_cb):
        super().__init__(
            moved_cb=moved_cb,
            created_cb=created_cb,
            deleted_cb=deleted_cb,
            modified_cb=modified_cb,
        )
        self._was_created = []
        self._patterns = ["*.svg", "*.xml"]
        self._ignore_directories = False

    def on_any_event(self, event):
        logger.debug(event)

    def on_moved(self, event):  # rename events
        if not self._active:
            return
        self.sgn_moved.emit(event.key)

    def on_created(self, event):
        if not self._active:
            return
        self._was_created.append(event.src_path)
        self.sgn_created.emit(event.key)

    def on_deleted(self, event):
        if not self._active:
            return
        self.sgn_deleted.emit(event.key)

    def on_modified(self, event):
        if not self._active:
            return
        if event.src_path in self._was_created:
            self._was_created.remove(event.src_path)
        self.sgn_modified.emit(event.key)


class ArchiveAddedEventHandler(
    QmmWdEventHandler, watchdog.events.PatternMatchingEventHandler, QObject
):
    def __init__(self, moved_cb, created_cb, deleted_cb, modified_cb):
        super().__init__(
            moved_cb=moved_cb,
            created_cb=created_cb,
            deleted_cb=deleted_cb,
            modified_cb=modified_cb,
        )
        self._accept = []
        self._patterns = [f"*{x}" for x in valid_suffixes("pathlib")]
        self._ignore_directories = True

    def on_moved(self, event):
        if event.is_directory or not self._active:
            return
        self.sgn_moved.emit(event)

    def on_created(self, event):
        if event.is_directory or not self._active:
            return
        self._accept.append(event.src_path)
        self.sgn_created.emit(event.key)

    def on_deleted(self, event):
        if event.is_directory or not self._active:
            return
        self.sgn_deleted.emit(event.key)

    def on_modified(self, event):
        if not self._active:
            return
        # We ignore any modified event unless it went through a created event
        # beforehand.
        if event.src_path in self._accept:
            self._accept.remove(event.src_path)
            self.sgn_modified.emit(event.key)


class CustomMenu:
    def __init__(self):
        super().__init__()
        self._menu_obj = QMenu()
        self._install_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-install.svg")), _("Install")
        )
        self._uninstall_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-uninstall.svg")), _("Uninstall")
        )
        self._delete_action = self._menu_obj.addAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/trash.svg")), _("Delete")
        )

    def setup_menu(self, obj):
        """Register self as obj's context menu"""
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
    fswatch_ignore = pyqtSignal(["QString", "QString"])
    fswatch_clear = pyqtSignal(["QString", "QString"])

    def __init__(self):
        super().__init__()
        self._is_mod_repo_dirty = False

        self.setupUi(self)
        self.setWindowTitle("qModManager")
        # self.listWidget is part of the UI file, so we need to take extra
        # steps in order to setup the widget with the various required
        # facilities.
        self.setup_filters([self.listWidget])
        self.setup_menu(self.listWidget)
        # Will do style using QT, see TODO file
        # loadQtStyleSheetFile('style.css', self)

        self._cb_after_init = deque()
        self._settings_window = None
        self._about_window = None
        self.managed_archives = filehandler.ArchivesCollection()
        self._qc = {}
        self._connection_link = None  # Connect to the settings's save button
        self._window_was_active = None
        self._wd_watchers = {"archives": None, "modules": None}
        self._ar_handler = None
        self._mod_handler = None
        self._observer = Observer()
        self._init_settings()

    def show(self):
        super().show()
        while self._cb_after_init:
            item = self._cb_after_init.pop()
            logger.debug("Calling %s", item)
            item()

    def on_window_activate(self):
        if not self._ar_handler or not self._mod_handler:  # handlers not init
            return False
        if not self._wd_watchers["archives"] and self.autorefresh_checkbox.isChecked():
            self._schedule_watchdog("archives")
        if self.is_mod_repo_dirty:
            logger.debug("Loose files are dirty, reparsing...")
            bucket.loosefiles = {}
            self.statusbar.showMessage(_("Refreshing loose files..."))
            filehandler.build_loose_files_crc32()
            if self.autorefresh_checkbox.isChecked():
                self._schedule_watchdog("modules")

        logger.debug("Refreshing managed archives...")
        msg = " "
        msg.join([self.statusbar.currentMessage(), _("Refreshing managed archive...")])
        self.statusbar.showMessage(msg)

        etype = None
        for etype, archive_name in self.managed_archives.refresh():
            if etype == self.managed_archives.FileAdded:
                self._add_item_to_list(
                    ListRowItem(
                        filename=archive_name, archive_manager=self.managed_archives
                    )
                )
            if etype == self.managed_archives.FileRemoved:
                idx = self.get_row_index_by_name(archive_name)
                self._remove_row(archive_name, idx, preserve_managed=True)

        if etype or self.is_mod_repo_dirty:
            filehandler.generate_conflicts_between_archives(self.managed_archives)
            self.managed_archives.initiate_conflicts_detection()
            self._refresh_list_item_state()
            self._is_mod_repo_dirty = False

        msg = " "
        msg.join([self.statusbar.currentMessage(), _("Refresh done.")])
        self.statusbar.showMessage(msg, 10000)
        return False

    def on_window_deactivate(self):
        if self._wd_watchers["archives"]:
            logger.debug("Unscheduling archive watch.")
            self._observer.unschedule(self._wd_watchers["archives"])
            self._wd_watchers["archives"] = None

    def _init_settings(self):
        if not settings_are_set():
            dialogs.qWarning(
                _(
                    "This software requires two path to be set in order to be "
                    "able to run. You <b>must</b> fill in the game folder and "
                    "repository folder. The game will crash if either is empty."
                ),
                # Translators: This is a messagebox's title
                title=_("First run"),
            )
            self.do_settings(first_launch=True)
        else:  # On first run, the _init_mods method is called by QSettings
            self._init_mods()

    def _init_mods(self):
        p_dialog = dialogs.SplashProgress(
            parent=None,
            title=_("Computing data"),
            message=_("Please wait for the software to initialize it's data."),
        )
        p_dialog.show()

        filehandler.build_game_files_crc32(p_dialog.progress)
        filehandler.build_loose_files_crc32(p_dialog.progress)
        self.managed_archives.build_archives_list(p_dialog.progress)

        p_dialog.progress("", category=_("Conflict detection"))
        filehandler.generate_conflicts_between_archives(
            self.managed_archives, progress=p_dialog.progress
        )
        self.managed_archives.initiate_conflicts_detection()

        item = None
        p_dialog.progress("", category=_("Parsing archives"))
        for archive_name in self.managed_archives.keys():
            p_dialog.progress(archive_name)
            item = ListRowItem(
                filename=archive_name, archive_manager=self.managed_archives
            )
            self._add_item_to_list(item)
        if item:
            self.listWidget.setCurrentItem(item)
            self.listWidget.scrollToItem(item)
        self.setup_schedulers()
        p_dialog.done(1)
        if self._connection_link:
            self._settings_window.disconnect_from_savebutton(self._connection_link)
            self._connection_link = None

    def setup_schedulers(self):
        # File watchers
        # Handlers emitting from the watcher to this class
        self._ar_handler = ArchiveAddedEventHandler(
            moved_cb=self._on_fs_moved,
            created_cb=None,
            deleted_cb=self._on_fs_deleted,
            modified_cb=self._on_fs_modified,
        )

        self._mod_handler = GameModEventHandler(
            moved_cb=self._mod_repo_watch_cb,
            created_cb=self._mod_repo_watch_cb,
            deleted_cb=self._mod_repo_watch_cb,
            modified_cb=self._mod_repo_watch_cb,
        )

        # Emitters from this class to the handler
        self.fswatch_ignore.connect(self._ar_handler.ignore)
        self.fswatch_clear.connect(self._ar_handler.clear)
        # WatchDog Observer
        self._schedule_watchdog("archives")
        self._schedule_watchdog("modules")
        self._observer.start()

    def callback_at_show(self, item):
        self._cb_after_init.append(item)

    def get_row_index_by_name(self, name):
        """Return row if name is found in the list.

        Args:
            name (str): Filename of the archive to find, matches content of the
                :py:meth:`ListRowItem <PyQt5.QtWidgets.QListWidgetItem.text>`
                text method.

        Returns:
            int or None: index of item found, `None` if `name` matches nothing.
        """
        try:
            return self.listWidget.row(
                self.listWidget.findItems(name, Qt.MatchExactly)[0]
            )
        except IndexError:
            return None

    def _add_item_to_list(self, item):
        self.listWidget.addItem(item)

    def _remove_row(self, filename: str, row: int, preserve_managed: bool = False):
        """Remove a row from the interface's list.

        The `filename` argument is only needed if `preserved_managed` is set to
        `False` (the default). It is needed to remove information stored in the
        `managed_archives` object.
        Will refresh the conflicting files once done.

        Args:
            filename: Only needed if preserve_managed is False
            row: integer matching the row to remove
            preserve_managed:
                if False, delete information from the managed_archives object
        """
        if not preserve_managed:
            del self.managed_archives[filename]
        self.listWidget.takeItem(row)
        filehandler.generate_conflicts_between_archives(self.managed_archives)

    def set_tab_color(self, index, color: QtGui.QColor = None) -> None:
        """Manage tab text color.

        Helper to :obj:`MainWindow._on_selection_change`.

        Store the default text color of a tab in order to restore it
        whenever the selected element in the linked list changes.

        Args:
            index (int): index of the tab
            color (QtGui.QColor): new color of the text
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

        item: ListRowItem = items[0]
        self.content_name.setText(item.name)
        self.content_modified.setText(item.modified)
        self.content_hashsum.setText(item.hashsum)

        # Hoping it's lost to the GC.
        self.tab_files_content.clear()
        self.tab_conflicts_content.clear()
        self.tab_skipped_content.clear()

        # tab_files, tab_conflicts, tab_skipped
        build_tree_widget(self.tab_files_content, item.archive_instance)
        build_conflict_tree_widget(self.tab_conflicts_content, item.archive_instance)
        build_ignored_tree_widget(
            self.tab_skipped_content, item.archive_instance.ignored()
        )

        autoresize_columns(self.tab_files_content)
        autoresize_columns(self.tab_conflicts_content)
        autoresize_columns(self.tab_skipped_content)

        skipped_idx = self.tabWidget.indexOf(self.tab_skipped)
        if item.archive_instance.has_ignored:
            self.set_tab_color(skipped_idx, QtGui.QColor(135, 33, 39))
        else:
            self.set_tab_color(skipped_idx)

        conflict_idx = self.tabWidget.indexOf(self.tab_conflicts)
        if item.archive_instance.has_conflicts:
            self.set_tab_color(conflict_idx, QtGui.QColor(135, 33, 39))
        else:
            self.set_tab_color(conflict_idx)

    @pyqtSlot(name="on_actionOpen_triggered")
    def _do_add_new_mod(self):
        if not settings_are_set():
            dialogs.qWarning(_("You must set your game folder location."))
            return

        qfd = QFileDialog(self)
        filters = valid_suffixes()
        qfd.setNameFilters(filters)
        qfd.selectNameFilter(filters[0])
        qfd.fileSelected.connect(self._on_action_open_done)
        qfd.exec_()

    def _get_selected_item(self, default: ListRowItem = None) -> ListRowItem:
        items = self.listWidget.selectedItems()
        if not items or default in items:
            return default
        return items[0]

    @pyqtSlot(name="on_actionRemove_file_triggered")
    def _do_delete_selected_file(self, menu_item=None):
        """Method to remove an archive file."""
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_delete_selected_file without a selection")
            return

        ret = dialogs.qWarningYesNo(
            _(
                "This action will uninstall the mod, then move the archive to your "
                "trashbin.\n\nDo you want to continue?"
            )
        )
        if not ret:
            return

        logger.info("Deletion of archive %s", item.filename)
        if item.has_matched:
            ret = self._do_uninstall_selected_mod()
            if not ret:
                return
        # Tell watchdog to ignore the file we are about to remove
        self.fswatch_ignore.emit(item.filename, watchdog.events.EVENT_TYPE_DELETED)
        filehandler.delete_archive(item.filename)
        self._remove_row(item.filename, self.listWidget.row(item))
        # Clear the ignore flag for the file
        self.fswatch_clear.emit(item.filename, watchdog.events.EVENT_TYPE_DELETED)
        del item

    @pyqtSlot(name="on_actionInstall_Mod_triggered")
    def _do_install_selected_mod(self, menu_item=None):
        """Method to install an archive's files to the game location."""
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("Triggered _do_install_selected_mod without a selection")
            return

        self._do_enable_autorefresh(False)
        logger.info("Installing file %s", item.filename)
        files = filehandler.install_archive(
            item.filename, item.archive_instance.install_info()
        )
        self._do_enable_autorefresh(True)
        if not files:
            dialogs.qWarning(
                _(
                    "The archive {filename} extracted with errors.\n"
                    "Please refer to {loglocation} for more information."
                ).format(
                    filename=item.filename, loglocation=get_config_dir("error.log")
                )
            )
        else:
            filehandler.generate_conflicts_between_archives(self.managed_archives)
            self._refresh_list_item_state()
            self._on_selection_change()

    @pyqtSlot(name="on_actionUninstall_Mod_triggered")
    def _do_uninstall_selected_mod(self, menu_item=None):
        """Delete all of the archive matched files from the filesystem.

        Stops if any mismatched item is found.
        """
        item = self._get_selected_item(menu_item)
        if not item:
            logger.error("triggered without item to process")
            return False

        if item.archive_instance.has_mismatched:
            dialogs.qInformation(
                _(
                    "Unable to uninstall mod: mismatched items exists on drive.\n"
                    "This is most likely due to another installed mod conflicting "
                    "with this mod.\n"
                )
            )
            return False

        self._do_enable_autorefresh(False)
        logger.info("Uninstalling files from archive %s", item.filename)
        uninstall_status = filehandler.uninstall_files(
            item.archive_instance.uninstall_info()
        )
        self._do_enable_autorefresh(True)
        if uninstall_status:
            filehandler.generate_conflicts_between_archives(self.managed_archives)
            self._refresh_list_item_state()
            self._on_selection_change()
            return True

        dialogs.qWarning(
            _(
                "The uninstallation process failed at some point. Please report "
                "this happened to the developper alongside with the error file "
                "{logfile}."
            ).format(logfile=get_config_dir("error.log"))
        )
        return False

    @pyqtSlot(name="on_actionSettings_triggered")
    def do_settings(self, first_launch=False):
        """Show the settings window.

        Args:
            first_launch (bool): If true, disable cancel button and bind the
                save button to :obj:`qmm.MainWindow._init_mods`
        """
        if not self._settings_window:
            self._settings_window = QSettings()
        if first_launch:
            self._connection_link = self._settings_window.connect_to_savebutton(
                self._init_mods
            )
            self._settings_window.set_mode(first_run=True)
        else:
            if self._connection_link:
                self._settings_window.disconnect_from_savebutton(self._connection_link)
                self._settings_window.set_mode(first_run=False)
        self._settings_window.show()

    @pyqtSlot(name="on_actionAbout_triggered")
    def do_about(self):
        """Show the about window."""
        if not self._about_window:
            self._about_window = QAbout()
        self._about_window.show()

    @pyqtSlot(bool, name="on_autorefresh_checkbox_toggled")
    def _do_enable_autorefresh(self, value: bool):
        if value:
            logger.debug("Enabling WatchDog Subsystem.")
            self._schedule_watchdog("modules")
            self._schedule_watchdog("archives")
            self.list_refresh_button.setEnabled(False)
        else:
            logger.debug("Disabling WatchDog Subsystem.")
            if self._wd_watchers["modules"]:
                self._observer.unschedule(self._wd_watchers["modules"])
                logger.debug("Modules watcher disabled")
            if self._wd_watchers["archives"]:
                self._observer.unschedule(self._wd_watchers["archives"])
                logger.debug("Archives watcher disabled")
            self._wd_watchers["modules"] = None
            self._wd_watchers["archives"] = None
            self.list_refresh_button.setEnabled(True)

    @pyqtSlot(name="list_refresh_button_triggered")
    def _do_list_refresh_button_triggered(self):
        if not self.autorefresh_checkbox.isChecked():
            logger.debug("Forcing refresh.")
            self._is_mod_repo_dirty = True
            self.on_window_activate()

    def _schedule_watchdog(self, context):
        if context == "archives":
            if not self._ar_handler:
                raise UnknownContext("Handler is NoneType, must be otherwise.")
            self._wd_watchers["archives"] = self._observer.schedule(
                event_handler=self._ar_handler,
                path=settings["local_repository"],
                recursive=False,
            )
        elif context == "modules":
            if not self._mod_handler:
                raise UnknownContext("Handler is NoneType, must be otherwise.")
            self._wd_watchers["modules"] = self._observer.schedule(
                event_handler=self._mod_handler,
                path=str(filehandler.get_mod_folder(prepend_modpath=True)),
                recursive=True,
            )
        else:
            raise UnknownContext("Unknown context '{}' for scheduler.".format(context))

    def _refresh_list_item_state(self):
        for idx in range(0, self.listWidget.count()):
            item: ListRowItem = self.listWidget.item(idx)
            item.archive_instance.reset_status()
            item.archive_instance.reset_conflicts()
            item.set_gradients()

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
                files=self.managed_archives[archive_name].files,
                archives_list=self.managed_archives,
                current_archive=archive_name,
                processed=None,
            )

            item = ListRowItem(
                filename=archive_name, archive_manager=self.managed_archives
            )

            self._add_item_to_list(item)
            self._refresh_list_item_state()
            self.listWidget.scrollToItem(item)
            self.listWidget.setCurrentItem(item)
            # Clear the ignore flag for the file
            self.fswatch_clear.emit(filename, watchdog.events.EVENT_TYPE_CREATED)
            return True

        dialogs.qWarning(
            _(
                "The file you selected is already present in the repository. "
                "It may exists under a different name.\nHashsum matched: {hashsum}"
            ).format(hashsum=hashsum)
        )
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

        logger.debug(
            "Received drop event with files %s", [f.path for f in e.mimeData().urls()]
        )
        for uri in e.mimeData().urls():
            pl = pathlib.PurePath(uri.path())
            if pl.suffix in valid_suffixes(output_format="pathlib"):
                logger.debug("Processing file %s", uri.path())
                # Tell watchdog to ignore the file we are about to move
                self.fswatch_ignore(uri.path(), watchdog.events.EVENT_TYPE_CREATED)
                self._on_action_open_done(uri.path())
        return True

    ######################
    # WatchDog callbacks #
    ######################
    def _mod_repo_watch_cb(self):
        # Ignore subsequent calls, happens for each file of a directory when
        # that directory gets renamed.
        if not self._wd_watchers["modules"]:
            return
        logger.debug(
            "Module repository got dirty, flagging as so and disabing "
            "unscheduling watchdog."
        )
        self._is_mod_repo_dirty = True
        self._observer.unschedule(self._wd_watchers["modules"])
        self._wd_watchers["modules"] = None

    def _on_fs_moved(self, e):
        src_path = e.src_path
        dest_path = e.dest_path
        logger.info("Archive renamed from %s to %s", src_path, dest_path)
        self.managed_archives.rename_archive(src_path, dest_path)

    def _on_fs_modified(self, e):
        filename = e[1]
        logger.info("New archive detected in the repository folder: %s", filename)
        self._on_action_open_done(filename, archive=pathlib.Path(filename).name)

    def _on_fs_deleted(self, e):
        item = pathlib.Path(e[1])
        logger.debug("WATCHDOG: file deleted on file system: %s", item)
        rows = self.listWidget.findItems(item.name, Qt.MatchExactly)
        if not rows:
            logger.debug("WATCHDOG: deleted file not managed, ignoring")
            return
        logger.debug("WATCHDOG: Number of file matching exactly: %s", len(rows))
        row = rows[0]
        self._remove_row(row.filename, self.listWidget.row(row))
        del row, rows

    ################
    # WatchDog End #
    ################
    @property
    def is_mod_repo_dirty(self):
        return self._is_mod_repo_dirty

    def __del__(self):
        if self._observer.is_alive():
            self._observer.unschedule_all()
            self._observer.stop()
        self._settings_window = None


class QAppEventFilter(QObject):
    """Detect if the application is active then triggers to appropriate events

    The purpose of this object is to enable or disable WatchDog related
    procedures. We want to disable file system watch on the modules directory
    when the window is inactive (user has alt-tabbed outside of it or minimized
    the application), as such delay any activity until the user comes back to
    the application itself. The intent is to minimize uneeded operations as the
    user could move and rename multiple files in the folder. We only need to
    scan the module's repository once the user has finished, thus once the
    application becomes active.

    The detection of activity needs to be done at the Session Manager, namely
    :py:class:`PyQt5:QApplication` (:py:class:`PyQt5.QtGui.QGuiApplication`
    or :py:class:`PyQt5.QtCore.QCoreApplication`). That object handles every
    window and widgets of the application. Each of those window and widgets
    could become inactive regardless of the status of the whole application.
    Inactivity could be defined as whenever the application loose focus
    (keyboard input). This loss also happen whenever the window is being
    dragged around by the user, which means we need to make sure to not trigger
    any refresh of the database for those user cases. To achieve that we track
    the geometry and coordinates of the window and trigger the callback only if
    those parameters remains the same between an inactive and active event.

    Callbacks are ``on_window_activate`` and ``on_window_deactivate``.
    """

    _mainwindow: Union[MainWindow, None]

    def __init__(self):
        super().__init__()
        self._mainwindow = None
        self._coords = ()
        self._geometry = ()
        self._is_first_activity = True
        self._previous_state = True
        # Whitelisting event to avoid unnecessary eventFilter calls
        self.accepted_types = [
            QEvent.ApplicationStateChange,
        ]

    def set_top_window(self, window: MainWindow):
        """Define the widget that is considered as top window."""
        self._mainwindow = window
        self._mainwindow.callback_at_show(self.set_coords)
        self._mainwindow.callback_at_show(self.set_geometry)
        self.set_coords()
        self.set_geometry()

    def get_coords(self) -> Tuple[int, int]:
        """Return the coordinates of the top window."""
        return (
            self._mainwindow.frameGeometry().x(),
            self._mainwindow.frameGeometry().y(),
        )

    def get_geometry(self) -> Tuple[int, int]:
        """Return the geometry of the top window."""
        return (
            self._mainwindow.frameGeometry().width(),
            self._mainwindow.frameGeometry().height(),
        )

    def set_coords(self):
        self._coords = self.get_coords()

    def set_geometry(self):
        self._geometry = self.get_geometry()

    def eventFilter(self, o, e: QEvent) -> bool:
        if e.type() not in self.accepted_types:
            return False
        if (
            not self._mainwindow
            or not self._mainwindow.autorefresh_checkbox.isChecked()
        ):
            return False
        if isinstance(o, QApplication) and e.type() == QEvent.ApplicationStateChange:
            if o.applicationState() == Qt.ApplicationActive:
                if self._is_first_activity:
                    self._is_first_activity = False
                    self.set_coords()
                    self.set_geometry()
                    return False
                logger.debug("The application is visible and selected to be in front.")
                coords = self.get_coords() == self._coords
                geo = self.get_geometry() == self._geometry
                if self.get_coords() != self._coords:
                    self.set_coords()
                if self.get_geometry() != self._geometry:
                    self.set_geometry()
                if coords and geo and not self._previous_state:
                    logger.debug("(A) Window became active without moving around.")
                    self._mainwindow.on_window_activate()
                    self._previous_state = True
            if o.applicationState() == Qt.ApplicationInactive:
                logger.debug(
                    "The application is visible, but **not** selected to be in front."
                )
                if (
                    self.get_coords() != self._coords
                    or self.get_geometry() != self._geometry
                ):
                    return False
                logger.debug("(D) Window isn't in focus, disabling WatchDog")
                self._previous_state = False
                self._mainwindow.on_window_deactivate()
        return False


def main():
    """Start the application proper."""
    import sys  # pylint: disable=import-outside-toplevel
    import signal  # pylint: disable=import-outside-toplevel
    import locale  # pylint: disable=import-outside-toplevel

    # Sets locale according to $LANG variable instead of C locale
    locale.setlocale(locale.LC_ALL, "")
    # Ends the application on CTRL+c
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    logger.info("Starting application")
    try:
        app = QApplication(sys.argv)
        QtGui.QFontDatabase.addApplicationFont(":/unifont.ttf")  # noqa
        aef = QAppEventFilter()
        app.installEventFilter(aef)
        mainwindow = MainWindow()
        aef.set_top_window(mainwindow)
        mainwindow.show()
        sys.exit(app.exec_())
    except Exception as e:  # Catchall, log then crash.
        logger.exception("Critical error occurred: %s", e)
        raise
    finally:
        logger.info("Application shutdown complete.")
