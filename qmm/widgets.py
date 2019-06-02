# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from . import file_from_resource_path
from .config import Config
from PyQt5 import uic
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QLayout, QFileDialog
from PyQt5.QtWidgets import QSizePolicy
from PyQt5.QtWidgets import QListWidgetItem, QCheckBox, QLabel, QPushButton
from PyQt5.QtGui import QIcon
logger = logging.getLogger(__name__)


def contructButton(label=None, callback=None):
    button = QPushButton()
    if label:
        button.setText(label)
        button.setObjectName(label.lower())
    if callback:
        button.clicked.connect(callback)
    button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
    return button


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


class directoryChooserButton(QWidget, fileWidgetAbstract):
    def __init__(self, label, parent, default, callback=None):
        super().__init__(parent=parent, label=label, callback=callback)
        if default:
            self.value = default

    def click(self):
        value = QFileDialog.getExistingDirectory(
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


class fileChooserButton(QWidget, fileWidgetAbstract):
    def __init__(self, label, parent, default=None, callback=None):
        super().__init__(parent=parent, label=label, callback=callback)
        if default:
            self.value = default

    def click(self):
        qd = QFileDialog(self)
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


class ListRowItem(QListWidgetItem):
    def __init__(self, archive_handler, enabled):
        super().__init__()
        self.archive_handler = archive_handler
        if self.archive_handler.metadata['name'] == '':
            self._name = self.archive_handler.metadata['filename']
        else:
            self._name = self.archive_handler.metadata['name']

        self._widget = QWidget()
        self._enabled = QCheckBox()
        label = QLabel(self.name)
        self._enabled.setChecked(enabled)
        layout = QHBoxLayout()
        # add different widgets to the row
        layout.addWidget(self._enabled)
        layout.addWidget(label)
        layout.addStretch()
        layout.setSizeConstraint(QLayout.SetFixedSize)
        self._widget.setLayout(layout)
        self.setSizeHint(self._widget.sizeHint())

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


class CustomList(QWidget):
    def __init__(self, *args, **kwargs):
        QWidget.__init__(self)

        self._plusFunction = kwargs.get('add_function', None)
        self._minusFunction = kwargs.get('remove_function', None)
        self._label = kwargs.get('label', args[0] if len(args) > 0 else '')
        self._style = kwargs.get('style', None)
        self._value = kwargs.get('default', None)
        self._help = kwargs.get('helptext', None)
        self.init_form()

        self.autoscroll = kwargs.get('autoscroll', True)
        self.itemDoubleClicked = kwargs.get('itemDoubleClicked', self.itemDoubleClicked)

    def __repr__(self):
        return "MyList ".format(str(self._value))

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

        if self.help:
            self.form.setToolTip(self.help)
        if self._style:
            self.form.setStyleSheet(self._style)

    def clear(self):
        self.listWidget.clear()

    def __add__(self, item):
        item.add_to_list(self.listWidget)
        if self.autoscroll:
            self.listWidget.scrollToItem(self.listWidget.item(self.listWidget.count() - 1))
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
