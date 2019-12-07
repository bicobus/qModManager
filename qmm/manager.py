# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>

import logging
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QMainWindow, QFileDialog
from PyQt5 import QtGui
from . import dialogs, widgets, filehandler
from .ui_mainwindow import Ui_MainWindow
from .config import get_config_dir
from .common import dirChooserWindow, settings_are_set, settings

logging.getLogger('PyQt5').setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(module)s:%(funcName)s:%(message)s',
    filename=get_config_dir("error.log"),
    filemode='w'
)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.setWindowTitle("qModManager")
        # Will do style using QT, see TODO file
        # loadQtStyleSheetFile('style.css', self)

        self._adding_files_flag = False
        self._settings_window = None
        self._qc = {}

        pDialog = dialogs.qProgress(
            parent=self, title="Computing data",
            message="Please wait for the software to initialize it's data."
        )
        pDialog.show()

        filehandler.build_game_files_crc32(pDialog.progress)
        filehandler.build_loose_files_crc32(pDialog.progress)
        self.managed_archives = filehandler.ArchivesCollection()
        self.managed_archives.build_archives_list(pDialog.progress)
        pDialog.done()

        filehandler.detect_conflicts_between_archives(self.managed_archives)

        # self.ui.listWidget
        for archive_name in self.managed_archives.keys():
            item = widgets.listRowItem(
                filename=archive_name,
                data=filehandler.missing_matched_mismatched(self.managed_archives[archive_name]),
                stat=self.managed_archives._stat[archive_name],
                hashsum=self.managed_archives._hashsums[archive_name]
            )
            self._add_item_to_list(item)

    def _add_item_to_list(self, item):
        self.listWidget.addItem(item)
        # Sets the widget to be displayed in the given item .
        # self.ui.listWidget.setItemWidget(item, item._widget)

    def do_settings(self):
        if self._settings_window:
            self._settings_window.show()
        else:
            self._settings_window = dirChooserWindow()
            self._settings_window.show()

    def set_tab_color(self, index, color=None):
        if index not in self._qc.keys():  # Cache default color
            self._qc[index] = self.tabWidget.tabBar().tabTextColor(index)

        if not color:
            self.tabWidget.tabBar().setTabTextColor(index, self._qc[index])
        else:
            assert isinstance(color, QtGui.QColor), type(color)
            self.tabWidget.tabBar().setTabTextColor(index, color)

    @pyqtSlot()
    def on_listWidget_itemSelectionChanged(self):
        """
        rgb(135, 33, 39) # redish
        rgb(78, 33, 135) # blueish
        rgb(91, 135, 33) # greenish
        """
        items = self.listWidget.selectedItems()
        if len(items) == 0:
            return
        else:
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

        self.tab_skipped_content.setPlainText(item.skipped)

        conflict_idx = self.tabWidget.indexOf(self.tab_conflicts)
        if item.has_conflicts:
            self.set_tab_color(conflict_idx, QtGui.QColor(135, 33, 39))
        else:
            self.set_tab_color(conflict_idx)
        self.tab_conflicts_content.setPlainText(item.conflicts)

    @pyqtSlot()
    def on_actionOpen_triggered(self):
        if self._adding_files_flag:  # TODO find a way to make a blocking window
            return
        else:
            self._adding_files_flag = True

        if not settings_are_set():
            dialogs.qWarning(
                "You must set your game folder location."
            )
            return

        qfd = QFileDialog(self)
        filters = ["Archives (*.7z *.zip, *.rar)"]
        qfd.setNameFilters(filters)
        qfd.selectNameFilter(filters[0])
        qfd.fileSelected.connect(self._on_actionOpen_done)
        qfd.exec_()

    @pyqtSlot()
    def on_actionRemove_file_triggered(self):
        items = self.listWidget.selectedItems()
        if len(items) == 0:
            return

        for item in items:
            if item.key in filehandler.managed_archives.keys():
                filehandler.delete_archive(item.key)

    @pyqtSlot()
    def on_actionInstall_Mod_triggered(self):
        items = self.listWidget.selectedItems()
        if len(items) == 0:
            return

        for item in items:
            filehandler.install_archive(item.filename)

    @pyqtSlot()
    def on_actionUninstall_Mod_triggered(self):
        items = self.listWidget.selectedItems()
        if len(items) == 0:
            return

        for item in items:
            filehandler.uninstall_archive(item.filename)

    @pyqtSlot()
    def on_actionSettings_triggered(self):
        self.do_settings()

    def _on_actionOpen_done(self, filename):
        """Callback to QFileDialog once a file is selected.
        """
        if not filename:
            self._adding_files_flag = False
            return
        hashsum = filehandler._hash(filename)
        if not self.managed_archives.find(hashsum=hashsum):
            archive_name = filehandler.copy_archive_to_repository(filename)

            item = widgets.listRowItem(
                filename=archive_name,
                data=filehandler.missing_matched_mismatched(self.managed_archives[archive_name]),
                stat=self.managed_archives._stat[archive_name],
                hashsum=self.managed_archives._hashsums[archive_name]
            )
            self._add_item_to_list(item)
            self._adding_files_flag = False
            self.listWidget.scrollToItem(item)
            return True
        else:
            dialogs.qWarning("The selected archive is already managed.")
            self._adding_files_flag = False
            return False
