# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2020-2021 bicobus <bicobus@keemail.me>
"""Contains a bunch of helper function to display Qt's dialogs."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, QDialog

from qmm.ui_qprogress import Ui_Dialog  # pylint: disable=no-name-in-module


def q_error(message, **kwargs):
    """Helper function to show an error dialog."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(_("An error occurred"))
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def q_warning(message, **kwargs):
    """Helper function to show a warning dialog."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(_("An warning occurred"))
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def q_warning_yes_no(message, **kwargs):
    """Helper function to show an Y/N warning dialog."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle(_("Warning"))
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    r = _do_message(msg, **kwargs)
    return bool(r == QMessageBox.Ok)


def q_information(message, **kwargs):
    """Helper function to show an informational dialog."""
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle(_("Information"))
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def _do_message(mobject, informative=None, detailed=None, title=None):
    if informative:
        mobject.setInformativeText(informative)
    if detailed:
        mobject.setDetailedText(detailed)
    if title:
        mobject.setWindowTitle(title)

    return mobject.exec_()


class SplashProgress(QDialog, Ui_Dialog):
    def __init__(self, parent, title, message):
        super().__init__(parent=parent)
        from PyQt5.QtWidgets import qApp  # noqa

        self.qapp = qApp
        self.setupUi(self)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(title)
        self.message.setText(message)
        self.category.setText("Booting")
        self.informative.setText("Booting")

    def progress(self, text: str, category: str = None):

        if category:
            self.category.setText(f"{category}: ")
        self.informative.setText(text)
        # processEvents needs to be called in order to touch QT event's loop.
        # Without it, the event loop will stall until all progress call have
        # been made.
        self.qapp.processEvents()
        # sleep(0.005)
