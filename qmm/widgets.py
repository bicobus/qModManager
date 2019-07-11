# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from datetime import datetime
from . import file_from_resource_path
from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon
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

        self._installedStr = f"Installed to game: {value}"
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


class CustomList(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self)

        self._plusFunction = kwargs.get('add_function', None)
        self._minusFunction = kwargs.get('remove_function', None)
        self._label = kwargs.get('label', args[0] if len(args) > 0 else '')
        self._style = kwargs.get('style', None)
        self._value = kwargs.get('default', None)
        self._help = kwargs.get('helptext', None)
        self.init_form()

        self.autoscroll = kwargs.get('autoscroll', True)
        self.itemDoubleClicked = kwargs.get(
            'itemDoubleClicked', self.itemDoubleClicked)

    def init_form(self):
        """
        Load the control UI and initiate all the events.
        """
        uic.loadUi(file_from_resource_path("list-view.ui"), self)
        self.label = self._label

        self.listWidget.itemDoubleClicked.connect(self._listItemDoubleClicked)
        self.listWidget.setResizeMode(self.listWidget.Adjust)
        self.listWidget.installEventFilter(self)

        if self._plusFunction is None and self._minusFunction is None:
            self.plusButton.hide()
            self.minusButton.hide()
        elif self._plusFunction is None:
            self.plusButton.hide()
            self.minusButton.pressed.connect(self._minusFunction)
        elif self._minusFunction is None:
            self.minusButton.hide()
            self.plusButton.pressed.connect(self._plusFunction)
        else:
            self.plusButton.pressed.connect(self._plusFunction)
            self.minusButton.pressed.connect(self._minusFunction)

        self.plusButton.setToolTip("Add an archive to your list.")
        self.minusButton.setToolTip((
            "Remove an archive from the list, uninstall everything if it "
            "was active."))

        if self.help:
            self.form.setToolTip(self.help)
        if self._style:
            self.form.setStyleSheet(self._style)

    def clear(self):
        self.listWidget.clear()

    def __add__(self, item):
        item.add_to_list(self.listWidget)
        if self.autoscroll:
            item = self.listWidget.item(self.listWidget.count() - 1)
            self.listWidget.scrollToItem(item)
        return self

    def __sub__(self, item):
        if isinstance(item, ListRowItem):
            idx = self.listWidget.indexFromItem(item).row()
            self.listWidget.takeItem(idx)
        return self

    def __len__(self):
        return self.listWidget.count()

    def __getitem__(self, key):
        if len(self.listWidget) == 0 or len(self.listWidget) == key:
            raise StopIteration
        return self.listWidget.item(key)

    def _listItemDoubleClicked(self, row):
        self.itemDoubleClicked(row)

    def itemDoubleClicked(self, row):
        pass

    def findItems(self, text):
        for item in self:
            if item.name.find(text) != -1:
                return item
        return False

    @property
    def form(self):
        return self

    @property
    def autoscroll(self):
        return self._autoscroll

    @autoscroll.setter
    def autoscroll(self, value):
        self._autoscroll = value

    @property
    def value(self):
        """
        This property returns or set what the control should manage or store.
        """
        if hasattr(self, 'listWidget'):
            results = []
            for row in range(self.listWidget.count()):
                try:
                    results.append(self.listWidget.item(row))
                except Exception as e:
                    logger.debug("Couldn't return value because: %s", e)
                    results.append("")
            return results
        return self._value

    @value.setter
    def value(self, value):
        self.clear()
        for row in value:
            self += row

    @property
    def help(self):
        """
        Returns or set the tip box of the control.
        """
        return self._help if self._help else ''

    @property
    def label(self):
        return self.labelWidget.getText()

    @label.setter
    def label(self, value):
        if value.strip() != '':
            self.labelWidget.setText(value)
        else:
            self.labelWidget.hide()
