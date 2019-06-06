from PyQt5.QtWidgets import QMessageBox


def qError(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle("An error occured")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def qWarning(message, **kwargs):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("An warning occured")
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
    msg.setWindowTitle("An error occured")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    _do_message(msg, **kwargs)


def _do_message(mobject, informative=None, detailed=None):
    if informative:
        mobject.setInformativeText(informative)
    if detailed:
        mobject.setDetailedText(detailed)

    return mobject.exec_()
