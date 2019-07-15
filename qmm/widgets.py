# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from datetime import datetime
from . import file_from_resource_path, areSettingsSet, INFORMATIVE
from . import dialogs
from .common import loadQtStyleSheetFile
from .ui_customlist import Ui_CustomList
from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSlot

logger = logging.getLogger(__name__)


def contructButton(label=None, callback=None):
    button = QtWidgets.QPushButton()
    if label:
        button.setText(label)
        button.setObjectName(label.lower())
    if callback:
        button.clicked.connect(callback)
    button.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                         QtWidgets.QSizePolicy.Fixed)
    return button


def timestampToString(timestamp):
    return datetime.strftime(datetime.fromtimestamp(timestamp), "%c")


class fileWidgetAbstract:
    def __init__(self, label, callback=None):
        self.widgets = uic.loadUi(file_from_resource_path("fileInput.ui"))
        self.widgets.pushButton.clicked.connect(self.click)
        self.widgets.pushButton.setIcon(QIcon())
        self.widgets.label.setText(label)
        self.label = label

        if callback:
            self.callback = callback
        self._value = None

    def click(self):
        raise NotImplemented("click() must be overriden")

    @property
    def value(self):
        return self._value if self._value else ''

    # XXX: using 2 variables might be redundant.
    @value.setter
    def value(self, value):
        self.widgets.lineEdit.setText(value)
        self._value = value


class directoryChooserButton(QtWidgets.QWidget, fileWidgetAbstract):
    def __init__(self, label, parent, default, callback=None):
        super().__init__(parent=parent, label=label, callback=callback)
        if default:
            self.value = default

    def click(self):
        value = QtWidgets.QFileDialog.getExistingDirectory(
            parent=self,
            caption=self.label,
            directory=self.value
        )
        logger.debug("File selected: %s", value)
        if value and len(value) > 0:
            self.value = value
            self.callback(value)

    def test(self, file):
        logger.debug("On selection:", file)


class fileChooserButton(QtWidgets.QWidget, fileWidgetAbstract):
    def __init__(self, label, parent, default=None, callback=None):
        super().__init__(parent=parent, label=label, callback=callback)
        if default:
            self.value = default

    def click(self):
        qd = QtWidgets.QFileDialog(self)
        filters = ["Archives (*.7z *.zip)"]
        qd.setNameFilters(filters)
        qd.selectNameFilter(filters[0])
        qd.fileSelected.connect(self._set_value)
        qd.exec_()

    def _set_value(self, file):
        logger.debug(file)
        if file and len(file) > 0:
            self.value = file
            if self.callback:
                self.callback(file)


class ExtraInfoLabel(QtWidgets.QWidget):
    """Create a VBoxLayout filled with two labels
    """

    def __init__(self, parentWgt, installed, added):
        super().__init__()
        self.setProperty('cname', 'extra_info')

        self._installedStr = None
        self._addedStr = None
        self._installedLabel = None
        self._addedLabel = None
        self.installed = installed
        self.added = added

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        layout.addWidget(self._installedLabel)
        layout.addWidget(self._addedLabel)
        self.setLayout(layout)

    @property
    def installed(self):
        return self._installedStr

    @installed.setter
    def installed(self, value):
        if not self._installedLabel:
            self._installedLabel = QtWidgets.QLabel(parent=self)

        self._installedStr = f"Installed on the: {value}"
        self._installedLabel.setText(self._installedStr)

    @property
    def added(self):
        return self._addedStr

    @added.setter
    def added(self, value):
        if not self._addedLabel:
            self._addedLabel = QtWidgets.QLabel(parent=self)

        self._addedStr = f"Added to list: {value}"
        self._addedLabel.setText(self._addedStr)


class fileChooserWindow(QtWidgets.QWidget):
    def __init__(self, callback=None):
        super().__init__()
        self.setWindowTitle("qModManager: archive selection")
        loadQtStyleSheetFile('style.css', self)
        self._fileWidget = fileChooserButton(
            label="Archive selection",
            parent=self,
            callback=self._on_file_selected
        )
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._fileWidget.widgets)
        self.setLayout(layout)
        self._callback = callback

    def _on_file_selected(self, file):
        logger.debug("Installing mod to local repository: %s", file)
        if self._callback:
            self._callback(file, self)

    def closeWindow(self):
        """
        Contrarian to its name, this method just hides the window
        """
        self.close()

    def closeEvent(self, event):
        """
        Tell callback that the user closed the window without doing anything
        """
        if self._callback:
            self._callback(None, None)
        super().closeEvent(event)


class ListRowItem(QtWidgets.QListWidgetItem):
    """Represent a managed archive to be inserted into a QtListView.
    """

    def __init__(self, archive_handler, enabled, file_data):
        """
        archive_handler: Must be an instance of filehandler.ArchiveHandler
        enabled (bool): pre-tick the checkbox
        file_data: copy of the extended information about the managed archive
        """
        super().__init__()
        self.archive_handler = archive_handler
        if self.archive_handler.metadata['name'] == '':
            self._name = self.archive_handler.metadata['filename']
        else:
            self._name = self.archive_handler.metadata['name']

        self._ref_fdata = file_data
        self.refresh_fdata(True)

        self._widget = QtWidgets.QWidget()
        self._enabled = QtWidgets.QCheckBox()
        label = QtWidgets.QLabel(self.name)
        self._enabled.setChecked(enabled)
        self._extraInfo = ExtraInfoLabel(
            self,
            installed=self.file_data['archive_installed'],
            added=self.file_data['file_added']
        )
        layout = QtWidgets.QHBoxLayout()
        # add different widgets to the row
        layout.addWidget(self._enabled)
        layout.addWidget(label, stretch=1)
        layout.addWidget(self._extraInfo)
        layout.addStretch()
        # layout.setSizeConstraint(QLayout.SetFixedSize)
        self._widget.setLayout(layout)
        self.setSizeHint(self._widget.sizeHint())

    def _decode_fdata(self, file_data):
        if ('archive_installed' not in file_data.keys() or
                not file_data['archive_installed']):
            string = "Never"
        else:
            string = timestampToString(file_data['archive_installed'])
        file_data['archive_installed'] = string

        if ('file_added' not in file_data.keys() or
                not file_data['file_added']):
            logger.warning(
                "'file_added' key for file %s was not set or not initialized.",
                file_data['filename']
            )
            string = datetime.today()
        else:
            string = timestampToString(file_data['file_added'])

        file_data['file_added'] = string

        return file_data

    def refresh_fdata(self, init=None):
        self.file_data = self._decode_fdata(self._ref_fdata.copy())
        if not init:
            self._extraInfo.installed = self.file_data['archive_installed']
            self._extraInfo.added = self.file_data['file_added']

    def add_to_list(self, QList):
        QList.addItem(self)
        QList.setItemWidget(self, self._widget)

    @property
    def enabled(self):
        return self._enabled.isChecked()

    @enabled.setter
    def enabled(self, enabled=False):
        return self._enabled.setChecked(enabled)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def hash(self):
        """Proxy for ArchiveHandler.hash
        returns the sha256 hash of the file.
        """
        return self.archive_handler.hash


class CustomList(QtWidgets.QWidget):
    def __init__(self, parent=None, label=None, *args, **kwargs):
        super(CustomList, self).__init__(parent)

        self._archive_manager = parent._archive_manager
        self._adding_files_flag = False
        self.ui = Ui_CustomList()
        self.ui.setupUi(self)

        self.ui.labelWidget.setText("Use the + or - button to add or remove items from the list")
        self.autoscroll = kwargs.get('autoscroll', True)

    def clear(self):
        self.ui.listWidget.clear()

    @pyqtSlot(bool)
    def on_minusButton_clicked(self):
        items = self.ui.listWidget.selectedItems()
        if len(items) == 0:
            return
        else:
            print(repr(items))

        cont = dialogs.qWarningYesNo("Do you really want to permanently remove the selected mod?")

        if not cont:
            return

        for item in self.ui.listWidget.selectedItems():
            logger.info("Removal of file: %s ...", item.hash)
            if self._archive_manager.get_state_by_hash(item.hash):
                logger.info("Uninstalling file: %s ...", item.hash)
                self._archive_manager.uninstall_mod(item.hash)
            self.remove_widget_from_list(item)
            self._archive_manager.remove_file(item.hash)
            logger.info("Removal done for: %s", item.hash)

    @pyqtSlot(bool)
    def on_plusButton_clicked(self):
        settingsNotOk = areSettingsSet()
        if settingsNotOk:
            dialogs.qWarning(
                settingsNotOk,
                informative=INFORMATIVE
            )
            return
        if self._adding_files_flag:
            return
        self._adding_files_flag = True
        add_file = fileChooserWindow(callback=self._do_copy_archive)
        add_file.show()

    @pyqtSlot(QtWidgets.QListWidgetItem)
    def on_listWidget_itemDoubleClicked(self, item):
        if item.enabled:
            item.enabled = False
        else:
            item.enabled = True

    def _do_copy_archive(self, file, widget):
        if not file:
            self._adding_files_flag = False
        else:
            file_hash = self._archive_manager.add_file(file)
            self.create_and_add_item(
                self._archive_manager.get_file_by_hash(file_hash),
                False,
                self._archive_manager.get_fileinfo_by_hash(file_hash)
            )
            widget.closeWindow()
            self._adding_files_flag = False
            dialogs.qInformation("The archive was properly installed into your list.")

    def create_and_add_item(self, archive_handler, state, data):
        item = ListRowItem(archive_handler, state, data)
        self.add_item_to_list(item)

    def add_item_to_list(self, item):
        if not hasattr(item, 'add_to_list'):
            logger.exception("Trying to add an item that isn't a ListRowItem")
            return False

        item.add_to_list(self.ui.listWidget)
        if self.autoscroll:
            item = self.ui.listWidget.item(self.ui.listWidget.count() - 1)
            self.ui.listWidget.scrollToItem(item)
        return True

    def remove_widget_from_list(self, item):
        if not isinstance(item, ListRowItem):
            logger.exception("Trying to remove an invalid item from the list.")
            return False

        idx = self.ui.listWidget.indexFromItem(item).row()
        self.ui.listWidget.takeItem(idx)
        return True

    def __len__(self):
        return self.ui.listWidget.count()

    def __getitem__(self, key):
        if len(self.ui.listWidget) == 0 or len(self.ui.listWidget) == key:
            raise StopIteration
        return self.ui.listWidget.item(key)

    def findItems(self, text):
        for item in self.ui.listWidget:
            if item.name.find(text) != -1:
                return item
        return False

    @property
    def autoscroll(self):
        return self._autoscroll

    @autoscroll.setter
    def autoscroll(self, value):
        self._autoscroll = value
