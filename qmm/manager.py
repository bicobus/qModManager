# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2019-2021 bicobus <bicobus@keemail.me>
"""Handles the Qt main window."""
import enum
import logging
import os
import pathlib
from collections import deque
from typing import Tuple, Union

import watchdog.events
from PyQt5 import QtGui
from PyQt5.QtCore import QEvent, QObject, Qt, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
)
from watchdog.observers import Observer

from qmm import bucket, dialogs, filehandler, get_base_path, running_ci
from qmm.common import settings, settings_are_set, valid_suffixes
from qmm.config import get_config_dir
from qmm.fileutils import ArchiveEvents, FileStateColor
from qmm.settings.core_dialogs import PreferencesDialog
from qmm.settings.pages import GeneralPage
from qmm.ui_mainwindow import Ui_MainWindow  # pylint: disable=no-name-in-module
from qmm.version import VERSION_STRING
from qmm.widgets import (
    ListRowItem,
    ListRowVirtualItem,
    QAbout,
    TreeWidgetMenu,
    autoresize_columns,
    build_conflict_tree_widget,
    build_ignored_tree_widget,
    build_tree_widget,
)

logger = logging.getLogger(__name__)
HELP_URL = "https://qmodmanager.readthedocs.io/"


class UnknownContext(Exception):
    pass


@enum.unique
class WatchDogSchedules(enum.Enum):
    ARCHIVES = "archives"
    MODULES = "modules"


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
            if e.type() == QEvent.Drop:
                return self._on_drop_action(e)
        # return false ignores the event and allow further propagation
        return False

    def _on_drop_action(self, e):
        raise NotImplementedError()


class MainWindow(QMainWindow, QEventFilter, Ui_MainWindow):
    fswatch_ignore = pyqtSignal(["QString", "QString"])
    fswatch_clear = pyqtSignal(["QString", "QString"])

    def __init__(self):
        super().__init__()
        self._is_mod_repo_dirty = False

        self.setupUi(self)
        self.setWindowTitle("qModManager v{}".format(VERSION_STRING))
        # self.listWidget is part of the UI file, so we need to take extra
        # steps in order to setup the widget with the various required
        # facilities.
        self.setup_filters([self.listWidget])
        # Install menu onto widgets
        self.listWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.listWidget.customContextMenuRequested.connect(self._do_menu_actions)
        treewidgetmenu = TreeWidgetMenu(self.tab_files_content)
        self.tab_files_content.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_files_content.customContextMenuRequested.connect(treewidgetmenu.show_menu)

        self._cb_post_show = deque()
        self._settings_window = None
        self.settings_index = None
        self._about_window = None
        self.managed_archives = filehandler.ArchivesCollection()
        self._qc = {}
        self._window_was_active = None
        self._wd_watchers = {WatchDogSchedules.ARCHIVES: None, WatchDogSchedules.MODULES: None}
        self._ar_handler = None
        self._mod_handler = None
        self._observer = Observer()

        self.actionHelp.triggered.connect(
            lambda: QtGui.QDesktopServices.openUrl(QUrl(HELP_URL)),  # noqa pycharm
            type=Qt.QueuedConnection,
        )

    def post_show_setup(self):
        """Actions to be triggered only after mainwindow `show` method is triggered"""
        while self._cb_post_show:
            item = self._cb_post_show.pop()
            logger.debug("Calling %s", item)
            item()

        if settings_are_set():
            self._init_mods()
        else:
            if running_ci():
                print("No settings files and running within CI. Abording.")
                return
            msg = _(
                "One or more parameters required for the proper usage of "
                "this application are undefined.<br>"
                "Would you like to open the Preferences window and define them now?"
            )
            answer = QMessageBox().information(
                self, _("Information"), msg, QMessageBox.Yes | QMessageBox.No
            )
            if answer == QMessageBox.Yes:
                self.do_settings()

    def on_window_activate(self):
        if not self._ar_handler or not self._mod_handler:  # handlers not init
            return False
        if (
            not self._wd_watchers[WatchDogSchedules.ARCHIVES]
            and self.autorefresh_checkbox.isChecked()
        ):
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
            if etype == ArchiveEvents.FILE_ADDED:
                self.listWidget.addItem(
                    ListRowItem(filename=archive_name, archive_manager=self.managed_archives)
                )
            if etype == ArchiveEvents.FILE_REMOVED:
                idx = self.get_row_index_by_name(archive_name)
                self._remove_row(archive_name, idx, preserve_managed=True)

        if etype or self.is_mod_repo_dirty:
            filehandler.generate_conflicts_between_archives(self.managed_archives)
            self.managed_archives.initiate_conflicts_detection()
            self.refresh_list_item_state()
            self._is_mod_repo_dirty = False

        msg = " "
        msg.join([self.statusbar.currentMessage(), _("Refresh done.")])
        self.statusbar.showMessage(msg, 10000)
        return False

    def on_window_deactivate(self):
        if self._wd_watchers[WatchDogSchedules.ARCHIVES]:
            logger.debug("Unscheduling archive watch.")
            self._observer.unschedule(self._wd_watchers[WatchDogSchedules.ARCHIVES])
            self._wd_watchers[WatchDogSchedules.ARCHIVES] = None

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
        # HACK: pylint doesn't recognize aliased objects, which Typing's MutableMapping are.
        for archive_name in self.managed_archives.keys():  # pylint: disable=no-member
            p_dialog.progress(archive_name)
            item = ListRowItem(filename=archive_name, archive_manager=self.managed_archives)
            self.listWidget.addItem(item)
        self.managed_archives.diff_matched_with_loosefiles()
        self.listWidget.addItem(ListRowVirtualItem(self.managed_archives))

        if item:
            self.listWidget.setCurrentItem(item)
            self.listWidget.scrollToItem(item)
        self.setup_schedulers()
        p_dialog.done(1)

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

    def add_callbacks_post_show(self, items):
        if not isinstance(items, list):
            items = [items]
        self._cb_post_show.extend(items)

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
            return self.listWidget.row(self.listWidget.findItems(name, Qt.MatchExactly)[0])
        except IndexError:
            return None

    def _remove_row(self, filename: str, row: int, preserve_managed: bool = False):
        """Remove a row from the interface's list.

        The `filename` argument is only needed if `preserved_managed` is set to
        `False` (the default). It is needed to remove information stored in the
        `managed_archives` object.

        Will refresh the conflicting files once done.

        Args:
            filename: Only needed if preserve_managed is False
            row: integer matching the row to remove
            preserve_managed: if False, delete information from the managed_archives
                object
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
    def on_selection_change(self) -> None:
        """Change the tab color to match the selected element in linked list."""
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
        build_ignored_tree_widget(self.tab_skipped_content, item.archive_instance.ignored())

        autoresize_columns(self.tab_files_content)
        autoresize_columns(self.tab_conflicts_content)
        autoresize_columns(self.tab_skipped_content)

        skipped_idx = self.tabWidget.indexOf(self.tab_skipped)
        if item.archive_instance.has_ignored:
            self.set_tab_color(skipped_idx, FileStateColor.tab_ignored.qcolor)
        else:
            self.set_tab_color(skipped_idx)

        conflict_idx = self.tabWidget.indexOf(self.tab_conflicts)
        if item.archive_instance.has_conflicts:
            self.set_tab_color(conflict_idx, FileStateColor.tab_conflict.qcolor)
        else:
            self.set_tab_color(conflict_idx)

    @pyqtSlot(name="on_actionOpen_triggered")
    def _do_add_new_mod(self):
        if not settings_are_set():
            dialogs.q_warning(_("You must set your game folder location."))
            return

        qfd = QFileDialog(self)
        filters = valid_suffixes()
        qfd.setNameFilters(filters)
        qfd.selectNameFilter(filters[0])
        qfd.fileSelected.connect(self._on_action_open_done)
        qfd.exec_()

    @pyqtSlot(name="on_actionRemove_file_triggered")
    def _do_delete_selected_file(self, widgetslist=None):
        """Method to remove an archive file."""
        if not widgetslist:  # called from a non-contextual call
            widgetslist = self.listWidget.selectedItems()
            if not widgetslist:
                logger.error("_do_install_selected_mod called without selection.")
                return
        if isinstance(widgetslist, ListRowItem):
            widgetslist = [widgetslist]

        items = [
            item for item in filter(
                lambda x: not isinstance(x, ListRowVirtualItem) and not x.archive_instance.has_matched,
                widgetslist
            )
        ]

        if not items:
            logger.error("Triggered _do_delete_selected_file but couldn't process anything.")
            return

        ret = dialogs.q_warning_yes_no(
            _(
                "This action will uninstall the mod, then move the archive to your "
                "trashbin.\n\nDo you want to continue?"
            ),
            detailed="Files to be removed:\n * {}".format(
                "\n * ".join([item.filename for item in items])
            )
        )
        if not ret:
            return

        maximum = len(items)
        pd = QProgressDialog(_("Moving files to the trashbin..."), "", 0, maximum)
        pd.setAutoClose(True)
        steps = pd.minimum()
        pd.setValue(steps)
        for item in items:
            logger.info("Deletion of archive %s", item.filename)
            # Tell watchdog to ignore the file we are about to remove
            self.fswatch_ignore.emit(item.filename, watchdog.events.EVENT_TYPE_DELETED)
            filehandler.delete_archive(item.filename)
            self._remove_row(item.filename, self.listWidget.row(item))
            steps += 1
            pd.setValue(steps)
            # Clear the ignore flag for the file
            self.fswatch_clear.emit(item.filename, watchdog.events.EVENT_TYPE_DELETED)
            del item

    @pyqtSlot(name="on_actionInstall_Mod_triggered")
    def _do_install_selected_mod(self, widgetslist=None):
        """Method to install an archive's files to the game location."""
        if not widgetslist:  # called from a non-contextual call
            widgetslist = self.listWidget.selectedItems()
            if not widgetslist:
                logger.error("_do_install_selected_mod called without selection.")
                return
        if isinstance(widgetslist, ListRowItem):
            widgetslist = [widgetslist]
        self._do_enable_autorefresh(False)
        names = [item.filename for item in widgetslist]
        skipped, conflictors = [], []
        changes = False

        p_dialog = dialogs.SplashProgress(
            parent=None,
            title=_("Installing modules"),
            message=_("Please wait for the software to initialize it's data."),
        )
        p_dialog.show()

        for item in widgetslist:
            p_dialog.progress("Processing {}".format(item.filename))
            if item.archive_instance.all_matching or item.archive_instance.empty:
                continue
            if item.archive_instance.has_matched:
                skipped.append(item.filename)
                continue
            if any(name in item.archive_instance.known_conflictors() for name in names):
                conflictors.append(item.filename)
                continue
            logger.info("Installing file %s", item.filename)
            files = filehandler.install_archive(item.filename, item.archive_instance.install_info())
            if not files:
                dialogs.q_warning(_(
                    "The archive {filename} extracted with errors.\n"
                    "Please refer to {loglocation} for more information."
                ).format(
                    filename=item.filename, loglocation=os.path.join(get_base_path(), "error.log")
                ))
            else:
                changes = True

        self._do_enable_autorefresh(True)

        if changes:
            p_dialog.category.setText(_("Recomputing conflicts:"))
            filehandler.generate_conflicts_between_archives(self.managed_archives, p_dialog.progress)
            self.refresh_list_item_state()
        else:
            dialogs.q_information(
                "You tried to install an archive, but the state of your game "
                "res/mods/ folder hasn't changed. This would indicate that your "
                "archive contains no recognized file able to be installed."
            )
            logger.warning("Tried to install something, but no changes were made on the drive.")
        p_dialog.done(1)

        if skipped:
            dialogs.q_information(
                _(
                    "Some archives couldn't be installed during the process. "
                    "Some of the files in those archives are already present "
                    "on the disk."
                ),
                detailed="\n".join(skipped)
            )

        if conflictors:
            dialogs.q_information(
                _(
                    "Some archives have conflicting files with each others and "
                    "couldn't be installed alongside each other. You should "
                    "selectively install one or manually resolve the "
                    "problematic files."
                ),
                detailed="\n".join(conflictors)
            )
        self.on_selection_change()

    @pyqtSlot(name="on_actionUninstall_Mod_triggered")
    def _do_uninstall_selected_mod(self, widgetslist=None):
        """Delete all the archive matched files from the filesystem.

        Will not process archives with known mismatch.
        """
        if not widgetslist:  # called from a non-contextual triggers
            widgetslist = self.listWidget.selectedItems()
            if not widgetslist:
                logger.error("_do_uninstall_selected_mod called without selection.")
                return
        if isinstance(widgetslist, ListRowItem):
            widgetslist = [widgetslist]

        pd = QProgressDialog("Uninstalling mods...", "", 0, 100, parent=self)
        pd.setAutoClose(True)
        pd.setWindowModality(Qt.WindowModal)
        pd.setValue(pd.minimum())
        step = int(100 / len(widgetslist))  # increase progress by `step`
        mismatched = []
        failure = False
        self._do_enable_autorefresh(False)
        for item in widgetslist:
            if item.archive_instance.has_mismatched:
                mismatched.append(item.filename)
                continue
            logger.info("Uninstalling files from archive %s", item.filename)
            uninstall_status = filehandler.uninstall_files(
                item.archive_instance.uninstall_info(),
                pd,
                step
            )
            if not uninstall_status:
                failure = True
        pd.reset()

        self._do_enable_autorefresh(True)
        if mismatched:
            dialogs.q_information(
                _(
                    "Some module couldn't be uninstalled, some of their files are mismatched.\n"
                    "This is most likely due to another installed mod conflicting "
                    "or changes occurred on the drive outside of the control of this software."
                ),
                detailed="\n".join(mismatched)
            )

        sp = dialogs.SplashProgress(
            parent=None,
            title=_("Computing data"),
            message=_("Please wait for the software to initialize it's data."),
        )
        sp.show()
        sp.category.setText(_("Conflict detection:"))
        filehandler.generate_conflicts_between_archives(self.managed_archives, progress=sp.progress)
        self.refresh_list_item_state()
        self.on_selection_change()
        sp.done(1)

        if failure:
            dialogs.q_warning(
                _(
                    "The uninstallation process failed at some point. Please report "
                    "this happened to the developper alongside with the error file "
                    "{logfile}."
                ).format(logfile=get_config_dir("error.log"))
            )
            return False
        return True

    @pyqtSlot(name="on_actionSettings_triggered")
    def do_settings(self):
        """Show the settings window."""

        def _d_finished(e):  # pylint: disable=unused-argument
            self._settings_window = None

        if not self._settings_window:
            try:
                verbosity = settings['ck_descriptive_text']
            except KeyError:
                verbosity = False
            dlg = PreferencesDialog(self)
            self._settings_window = dlg
            gpage = GeneralPage(dlg, verbosity)
            dlg.add_page(gpage)

            if self.settings_index:
                dlg.contents_widget.setCurrentIndex(self.settings_index)
            dlg.show()

            dlg.pages_widget.currentChanged.connect(self._settings_index_changed)
            dlg.finished.connect(_d_finished)
        else:
            self._settings_window.show()
            self._settings_window.activateWindow()
            self._settings_window.raise_()
            self._settings_window.setFocus()

    def _settings_index_changed(self, index):
        self.settings_index = index

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
            if self._wd_watchers[WatchDogSchedules.MODULES]:
                self._observer.unschedule(self._wd_watchers[WatchDogSchedules.MODULES])
                logger.debug("Modules watcher disabled")
            if self._wd_watchers[WatchDogSchedules.ARCHIVES]:
                self._observer.unschedule(self._wd_watchers[WatchDogSchedules.ARCHIVES])
                logger.debug("Archives watcher disabled")
            self._wd_watchers[WatchDogSchedules.MODULES] = None
            self._wd_watchers[WatchDogSchedules.ARCHIVES] = None
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
            self._wd_watchers[WatchDogSchedules.ARCHIVES] = self._observer.schedule(
                event_handler=self._ar_handler,
                path=settings["local_repository"],
                recursive=False,
            )
        elif context == "modules":
            if not self._mod_handler:
                raise UnknownContext("Handler is NoneType, must be otherwise.")
            self._wd_watchers[WatchDogSchedules.MODULES] = self._observer.schedule(
                event_handler=self._mod_handler,
                path=str(filehandler.get_mod_folder(prepend_modpath=True)),
                recursive=True,
            )
        else:
            raise UnknownContext("Unknown context '{}' for scheduler.".format(context))

    def refresh_list_item_state(self):
        """Refresh the listwidget whenever an item is added or removed."""
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
                dialogs.q_warning(
                    _("A file with the same name already exists in the repository."))
                return False
            self.managed_archives.add_archive(filename, hashsum)
            filehandler.conflicts_process_files(
                files=self.managed_archives[archive_name].files,
                archives_list=self.managed_archives,
                current_archive=archive_name,
                processed=None,
            )

            item = ListRowItem(filename=archive_name, archive_manager=self.managed_archives)

            self.listWidget.addItem(item)
            self.refresh_list_item_state()
            self.listWidget.scrollToItem(item)
            self.listWidget.setCurrentItem(item)
            # Clear the ignore flag for the file
            self.fswatch_clear.emit(filename, watchdog.events.EVENT_TYPE_CREATED)
            return True

        dialogs.q_warning(_(
            "The file you selected is already present in the repository. "
            "It may exists under a different name.\nHashsum matched: {hashsum}"
        ).format(hashsum=hashsum))
        return False

    ##########################
    # Context Menu overrides #
    ##########################
    def _do_menu_actions(self, position):
        items = [
            item
            for item in filter(
                lambda x: not isinstance(x, ListRowVirtualItem) and not x.archive_instance.empty,
                self.listWidget.selectedItems()
            )
        ]
        if not items:  # Nothing to do here.
            return

        install = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-install.svg")),
            _("Install"),
        )
        uninstall = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/file-uninstall.svg")),
            _("Uninstall"),
        )
        delete = QAction(
            QtGui.QIcon(QtGui.QPixmap(":/icons/trash.svg")),
            _("Delete"),
        )
        # if there is a partial match, don't allow install
        install.triggered.connect(lambda: self._do_install_selected_mod(items))
        if any(item.archive_instance.has_matched for item in items):
            # install.setDisabled(True)
            uninstall.triggered.connect(lambda: self._do_uninstall_selected_mod(items))
        else:
            uninstall.setDisabled(True)
        delete.triggered.connect(lambda: self._do_delete_selected_file(items))
        menu = QMenu()
        menu.addAction(install)
        menu.addAction(uninstall)
        menu.addAction(delete)
        menu.exec_(self.listWidget.mapToGlobal(position))

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

        logger.debug("Received drop event with files %s", [f.path for f in e.mimeData().urls()])
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
        if not self._wd_watchers[WatchDogSchedules.MODULES]:
            return
        logger.debug(
            "Module repository got dirty, flagging as so and disabing unscheduling watchdog."
        )
        self._is_mod_repo_dirty = True
        self._observer.unschedule(self._wd_watchers[WatchDogSchedules.MODULES])
        self._wd_watchers[WatchDogSchedules.MODULES] = None

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

    def closeEvent(self, close_event: QtGui.QCloseEvent):
        # Ensure we remove any references before closing the window.
        if self._observer.is_alive():
            self._observer.unschedule_all()
            self._observer.stop()
        self._settings_window = None
        # By default, the event is accepted and the widget is closed.
        super().closeEvent(close_event)


class QAppEventFilter(QObject):
    """Detect if the application is active then triggers to appropriate events.

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
        self._mainwindow.add_callbacks_post_show([self.set_coords, self.set_geometry])
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
        if not self._mainwindow or not self._mainwindow.autorefresh_checkbox.isChecked():
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
                logger.debug("The application is visible, but **not** selected to be in front.")
                if self.get_coords() != self._coords or self.get_geometry() != self._geometry:
                    return False
                logger.debug("(D) Window isn't in focus, disabling WatchDog")
                self._previous_state = False
                self._mainwindow.on_window_deactivate()
        return False


# pylint: disable=import-outside-toplevel
def main():
    """Start the application proper."""
    import locale
    import signal
    import sys

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
        mainwindow.post_show_setup()
        if running_ci():
            return app
        sys.exit(app.exec_())
    except Exception as e:  # Catchall, log then crash.
        logger.exception("Critical error occurred: %s", e, exc_info=True)
        raise RuntimeError("Unrecoverable error.") from e
    finally:
        logger.info("Application shutdown complete.")
