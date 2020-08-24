#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

from enum import Enum
from os import path
from typing import Union

from PyQt5 import QtGui, QtWidgets

from common import timestamp_to_string
from filehandler import ArchivesCollection

#: Gradients of colors for each file of the tree widget.
FILESTATE_COLORS = {
    "matched": (91, 135, 33, 255),  # greenish
    "mismatched": (132, 161, 225, 255),  # blueish
    "missing": (237, 213, 181, 255),  # (225, 185, 132, 255),  # yellowish
    "conflicts": (135, 33, 39, 255),  # red-ish
    "ignored": (219, 219, 219, 255),  # gray
}


# TODO: Unify all FileState / FileStatus enum and literals
#  Related to qmm/fileutils.py and qmm/filehandler.py constants
class FileState(Enum):
    matched = (91, 135, 33, 255)  # greenish
    mismatched = (132, 161, 225, 255)  # blueish
    missing = (237, 213, 181, 255)  # (225, 185, 132, 255),  # yellowish
    conflicts = (135, 33, 39, 255)  # red-ish
    ignored = (219, 219, 219, 255)  # gray

    def __init__(self, r, g, b, a):
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    @property
    def qcolor(self):
        return QtGui.QColor(self.r, self.g, self.b, self.a)


class ABCListRowItem(QtWidgets.QListWidgetItem):
    def __init__(self, filename: Union[str, None], archive_manager: ArchivesCollection):
        super().__init__()
        self._filename = filename
        self.am = archive_manager
        self.archive_instance = None
        self._key = None
        self._stat = None
        self._name = None
        self._modified = None
        self._hashsum = None
        self._post_init()

    def _post_init(self):
        self.archive_instance = self.am[self._filename]
        self._key = path.basename(self._filename)
        self._stat = self.am.stat(self._filename)
        self._hashsum = self.am.hashsums(self._filename)
        self.setText(self.filename)
        self.set_gradients()
        self.set_text_color()

    def set_gradients(self):
        gradient = QtGui.QLinearGradient(75, 75, 150, 150)
        if self.archive_instance.has_mismatched:
            gradient.setColorAt(0, FileState.mismatched.qcolor)
        elif self.archive_instance.all_matching and not self.archive_instance.all_ignored:
            gradient.setColorAt(0, FileState.matched.qcolor)
        elif self.archive_instance.has_matched and self.archive_instance.has_missing:
            gradient.setColorAt(0, FileState.missing.qcolor)
        else:
            gradient.setColorAt(0, QtGui.QColor(0, 0, 0, 0))
        if self.archive_instance.has_conflicts:
            gradient.setColorAt(1, FileState.conflicts.qcolor)
        brush = QtGui.QBrush(gradient)
        self.setBackground(brush)

    def set_text_color(self):
        if self.archive_instance.all_ignored:
            self.setForeground(QtGui.QColor("gray"))

    def refresh_strings(self):
        """Called when the game's folder state changed.

        Reinitialize the widget's strings, recompute the conflicts then redo
        all triaging and formatting.
        """
        self.archive_instance.reset_status()
        self.archive_instance.reset_conflicts()
        self.set_gradients()

    @property
    def name(self):
        """Return the name of the archive, formatted for GUI usage.

        Transfrom the '_' character into space.
        """
        if not self._name:
            self._name = self._key.replace("_", " ")
        return self._name

    @property
    def filename(self):
        """Returns the name of the archive filename, suitable for path manipulations."""
        return self._key

    @property
    def modified(self):
        """Return last modified time for an archive, usually time of creation."""
        if not self._modified:
            self._modified = timestamp_to_string(self._stat.st_mtime)
        return self._modified

    @property
    def hashsum(self):
        """Returns the sha256 hashsum of the archive."""
        if self._hashsum:
            return self._hashsum
        return ""
