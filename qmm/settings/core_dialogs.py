# -*- coding: utf-8 -*-
#  Licensed under EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

"""Constructors for the setting window.

Some of the design and code were influenced by `Spyder Ide <https://www.spyder-ide.org/>`_. Spyder
IDE is released under MIT.

The setting window has two major elements:
1. A side bar listing the different pages
2. A content area with the selected page

 +----------+---------------+
 |          |               |
 |  Pages   | Pages content |
 |  names   |               |
 |          | sections      |
 |          | contains      |
 |          | widgets       |
 |          |               |
 +----------+---------------+
 |                 Yes / No |
 +--------------------------+

"""
from PyQt5.QtCore import QSize, Qt, pyqtSignal  # , pyqtSlot
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qmm.common import settings
from qmm.settings.validators import IsDirValidator, make_html_list


def create_button(text, callback):
    button = QPushButton(text)
    button.clicked.connect(callback)
    return button


def make_layout(parent, align, *widgets):
    layout = QVBoxLayout(parent) if align == Qt.Vertical else QHBoxLayout(parent)
    for widget in widgets:
        layout.addWidget(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    return layout


class Page(QWidget):
    NAME = None
    ICON = None

    show_this_page = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent)
        self.main = parent
        self.pages = {}

        self.validators = {}
        self.lineedits = {}
        self.comboboxes = {}

        self.init_page()

    def init_page(self):
        self.setup_ui()
        self.load_configuration()

    def setup_ui(self):
        raise NotImplementedError()

    def get_name(self):
        return self.NAME

    def get_icon(self):
        return self.ICON

    def load_configuration(self):
        for widget, confkey in self.lineedits.items():
            try:
                text = settings[confkey]
            except KeyError:
                text = ""
            widget.setText(text)

        for combobox, confkey in self.comboboxes.items():
            try:
                data = settings[confkey]
            except KeyError:
                data = None

            idx = combobox.findData(data)
            if idx != -1:
                combobox.setCurrentIndex(idx)

    def save(self):
        for lineedit, confkey in self.lineedits.items():
            data = lineedit.text()
            if data != settings[confkey]:
                settings[confkey] = data

    def validate(self):
        # NOTE: validation might only work for text input, either QLineEdit or
        #   QPlainTextEdit
        for widget, validators in self.validators.items():
            msgs = []
            if not isinstance(validators, list):
                validators = [validators]
            for validator in validators:
                try:
                    validator(widget.text())
                except ValueError as e:
                    msgs.append(e.args[0])
            if msgs:
                QMessageBox.critical(
                    self,
                    self.get_name(),
                    "{}:<br><b>{}</b>".format(widget.text(), make_html_list(msgs)),
                )
                return False
        return True

    def c_lineedit(self, text, confkey, **qtparams):
        wordwrap = qtparams.setdefault("wordwrap", False)
        alignment = qtparams.setdefault("alignment", Qt.Vertical)
        tip = qtparams.setdefault("tip", None)
        placeholder = qtparams.setdefault("placeholder", None)

        label = QLabel(text)
        label.setWordWrap(wordwrap)
        edit = QLineEdit()
        layout = make_layout(self, alignment, label, edit)
        if tip:
            edit.setToolTip(tip)
        if placeholder:
            edit.setPlaceholderText(placeholder)
        self.lineedits[edit] = confkey
        widget = QWidget(self)
        widget.label = label
        widget.textbox = edit
        widget.setLayout(layout)
        edit.label_text = text
        return widget

    def c_browsedir(self, text, confkey, tip=None, placeholder=None):
        widget = self.c_lineedit(
            text, confkey, tip=tip, alignment=Qt.Horizontal, placeholder=placeholder,
        )

        edit = None
        for edit in self.lineedits:
            if widget.isAncestorOf(edit):
                break
        if not edit:
            return None
        self.validators[edit] = [IsDirValidator]
        button = QPushButton(self)
        button.setText(_("Browse..."))
        button.setToolTip(_("Select a directory"))
        button.clicked.connect(lambda: self.select_directory(edit))
        layout = make_layout(self, Qt.Horizontal, widget, button)
        browsedir = QWidget(self)
        browsedir.setLayout(layout)
        return browsedir

    def select_directory(self, lineedit):
        path = lineedit.text()
        value = QFileDialog.getExistingDirectory(
            parent=self,
            caption=_("Select a directory"),  # caption := window title
            directory=path,
        )
        lineedit.setText(value)

    def c_combobox(self, text, choices, confkey, tip=None):
        label = QLabel(text)
        combobox = QComboBox()
        if tip:
            combobox.setToolTip(tip)
        for name, key in choices:
            if name and key:
                combobox.addItem(name, key)
        i = 0
        for idx, item in enumerate(choices):
            name, key = item
            if not name and not key:
                combobox.insertSeparator(idx + i)
                i += 1
        self.comboboxes[combobox] = confkey
        layout = make_layout(self, Qt.Horizontal, label, combobox)
        layout.addStretch(1)
        widget = QWidget(self)
        widget.label = label
        widget.combobox = combobox
        widget.setLayout(layout)
        return widget


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent

        self.pages_widget = QStackedWidget()
        self.pages_widget.setMinimumSize(600, 0)
        self.contents_widget = QListWidget()

        bbox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        self.apply_btn = bbox.button(QDialogButtonBox.Apply)
        self.ok_btn = bbox.button(QDialogButtonBox.Ok)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle(_("Settings"))
        self.contents_widget.setMovement(QListView.Static)
        self.contents_widget.setSpacing(1)
        self.contents_widget.setCurrentRow(0)
        self.contents_widget.setMinimumWidth(220)
        self.contents_widget.setMinimumHeight(400)

        hsplitter = QSplitter()
        hsplitter.addWidget(self.contents_widget)
        hsplitter.addWidget(self.pages_widget)
        hsplitter.setStretchFactor(0, 1)
        hsplitter.setStretchFactor(1, 2)

        btnlayout = QHBoxLayout()
        btnlayout.addStretch(1)
        btnlayout.addWidget(bbox)

        vlayout = QVBoxLayout()
        vlayout.addWidget(hsplitter)
        vlayout.addLayout(btnlayout)
        self.setLayout(vlayout)

        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        bbox.clicked.connect(self.button_clicked)

        self.contents_widget.currentRowChanged.connect(self.pages_widget.setCurrentIndex)

    def accept(self):
        """Go through all the pages and save everything."""
        for idx in range(0, self.pages_widget.count()):
            page = self.get_page(idx)
            if not page.validate():
                return
            page.save()
        super().accept()

    def button_clicked(self, button):
        """Save a specific page"""
        if button is self.apply_btn:
            page = self.get_page()
            if not page.validate():
                return
            page.save()

    def add_page(self, widget):
        widget.show_this_page.connect(
            lambda row=self.contents_widget.count(): self.contents_widget.setCurrentRow(row)
        )
        scrollarea = QScrollArea(self)
        scrollarea.setWidgetResizable(True)
        scrollarea.setWidget(widget)
        self.pages_widget.addWidget(scrollarea)
        page_row = QListWidgetItem(self.contents_widget)
        page_row.setText(widget.get_name())
        page_row.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
        page_row.setSizeHint(QSize(0, 25))

    def get_page(self, index=None):
        if not index:
            widget = self.pages_widget.currentWidget()
        else:
            widget = self.pages_widget.widget(index)

        if widget:
            return widget.widget()
        return None
