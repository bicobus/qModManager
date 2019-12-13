# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMessageBox, qApp, QDialog, QLabel, QVBoxLayout


def qError(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("An error occurred")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def qWarning(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("An warning occurred")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def qWarningYesNo(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("Warning")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
    r = _do_message(msg, **kwargs)
    return True if r == QMessageBox.Ok else False


def qInformation(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("An error occurred")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def _do_message(mobject, informative=None, detailed=None):
    if informative:
        mobject.setInformativeText(informative)
    if detailed:
        mobject.setDetailedText(detailed)

    return mobject.exec_()


class qProgress(QDialog):
    def __init__(self, parent, title, message):
        super().__init__(parent=parent)
        self.setWindowModality(Qt.WindowModal)
        self.setWindowTitle(title)
        label = QLabel(message)
        self.informative = QLabel("Initializing...")
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.addWidget(self.informative)
        self.setLayout(layout)

    def progress(self, text):
        self.informative.setText(text)
        # processEvents needs to be called in order to touch QT event's loop.
        # Without it, the event loop will stall until all progress call have
        # been made.
        qApp.processEvents()
        # sleep(0.005)

