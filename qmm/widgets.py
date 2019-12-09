# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from os import path
from collections import deque
from . import file_from_resource_path
from .common import timestampToString
from .filehandler import (FILE_MISSING, FILE_MATCHED, FILE_MISMATCHED,
                          FILE_IGNORED)
from .conflictbucket import ConflictBucket
from .ui_detailedview import Ui_DetailedView
from PyQt5 import uic
from PyQt5 import QtWidgets
from PyQt5.QtGui import QIcon

# from PyQt5.QtGui import QIcon, QPixmap
# _detailViewButton = QtWidgets.QPushButton()
# icon = QIcon()
# icon.addPixmap(QPixmap(":/icons/info.svg"), QIcon.Normal, QIcon.Off)
# _detailViewButton.setIcon(icon)

logger = logging.getLogger(__name__)


def constructButton(label=None, callback=None):
    button = QtWidgets.QPushButton()
    if label:
        button.setText(label)
        button.setObjectName(label.lower())
    if callback:
        button.clicked.connect(callback)
    button.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                         QtWidgets.QSizePolicy.Fixed)
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
        raise NotImplementedError("click() must be overriden")

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
        if value:
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
        if file:
            self.value = file
            if self.callback:
                self.callback(file)


# widgets name:
#  * content_name
#  * content_author
#  * content_version
#  * content_url
#  * content_description
#  * content_tags
#  * filetreeWidget
#
#  FIXME: Unfinished, will need to be revisited
class DetailedView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(DetailedView, self).__init__(parent)
        self.ui = Ui_DetailedView()
        self.ui.setupUi(self)
        self.ui.button_hide.hide()
        self.ui.filetreeWidget.hide()

    def prepare_directoryList(self, directories):
        """Returns a dict of lists of files indexed on a tuple of directories.
        Example: dict(
         ('res/TheShyGuy995/', 'weapons', 'Fire Emblem'): ['/Sheathed Sword.svg', '/Sword.xml']
        )
        """
        dlist = list()
        for file in directories:
            dirname, _ = path.split(file)
            if dirname not in dlist and "/" in dirname:
                dlist.append(dirname)

        prefix = path.commonpath(dlist)
        if "/" in prefix:
            prefix = prefix.split("/")

        ddir = dict()
        for dirname in dlist:
            sdir = dirname.split('/')
            if isinstance(prefix, list):
                for p in prefix:
                    sdir.remove(p)
            else:
                sdir.remove(prefix)
            dir_str = "/".join(sdir)

            for ofile in directories:
                if dir_str in ofile:
                    start, tmp, cfile = ofile.partition(dir_str)
                    path_to_file = tmp.split("/")
                    pfile = list()
                    pfile.append(start)
                    pfile.extend(path_to_file)
                    pfile = tuple(pfile)
                    if pfile not in ddir.keys():
                        ddir[pfile] = deque()
                    ddir[pfile].append(cfile)

        return ddir

    def build_dirlist(self, pathAndFiles):
        dir_map = dict()
        for directories, files in pathAndFiles.items():
            for directory in directories:
                if directory not in dir_map.keys():
                    index = directories.index(directory)
                    if index > 0:
                        previous = directories[index - 1]
                    else:
                        previous = self.ui.filetreeWidget

                dir_map[directory] = QtWidgets.QTreeWidgetItem(previous, directory)

            for file in files:
                dir_map[directory].addChild(QtWidgets.QTreeWidgetItem(None, file.strip('/')))

    def closeEvent(self, event):
        """Ignore the close event and hide the widget instead

        If the window gets closed, Qt will prune its data and renders it
        unavailable for further usage.
        """
        self.hide()
        event.ignore()


class listRowItem(QtWidgets.QListWidgetItem):
    """ListWidgetItem representing one single archive.
    Needs to retrieve metadata and provide a facility to access it.
    """

    def __init__(self, filename, data, stat, hashsum):
        super().__init__()
        self._key = path.basename(filename)
        self._data = data
        self._stat = stat
        self._name = None
        self._added = None
        self._hashsum = hashsum

        self._matched = []
        self._matched_str = None
        self._missing = []
        self._missing_str = None
        self._mismatched = []
        self._mismatched_str = None
        self._ignored = []
        self._ignored_str = None
        self._conflicts = {}
        self._conflicts_str = None

        self.setText(self.filename)

    def _set_item_status(self, item, status):
        if status == FILE_MATCHED:
            self._matched.append(item)
        elif status == FILE_MISMATCHED:
            self._mismatched.append(item)
        elif status == FILE_MISSING:
            self._missing.append(item)
        elif status == FILE_IGNORED:
            self._ignored.append(item)
        else:
            return False
        return True

    def _conflict_triage(self, item):
        c = []
        # Check other archives
        if item.Path in ConflictBucket().conflicts.keys():
            c.extend(ConflictBucket().conflicts[item.Path])
        # Check against existing files
        if item.CRC in ConflictBucket().looseconflicts.keys():
            c.extend(ConflictBucket().looseconflicts[item.CRC])
        # Check against game files (Path and CRC)
        if (item.Path in ConflictBucket().gamefiles.values()
                or item.CRC in ConflictBucket().gamefiles.keys()):
            c.append(ConflictBucket().gamefiles[item.CRC])
        if c:
            self._conflicts[item.Path] = c

    @property
    def name(self):
        if not self._name:
            self._name = self._key.replace('_', ' ')
        return self._name

    @property
    def filename(self):
        return self._key

    @property
    def added(self):
        if not self._added:
            self._added = timestampToString(self._stat.st_mtime)
        return self._added

    @property
    def hashsum(self):
        if self._hashsum:
            return self._hashsum
        return ""

    @property
    def files(self):
        top = []
        strings = ["== Archive's content:\n"]
        errstring = "ERR: Following file has unknown status → {}"
        for item, status in self._data:
            if not self._set_item_status(item, status):
                top.append(errstring.format(item.Path))

            self._conflict_triage(item)

            # Add only files to avoid clutter
            if 'D' not in item.Attributes:
                strings.append(f"   - {item.Path}\n")

        rstr = ""
        if top:
            rstr = "".join(top) + "\n\n"
        rstr += "".join(strings)

        return rstr

    @property
    def matched(self):
        if not self._matched_str:
            self._matched_str = self._format(
                title="Files installed",
                items=self._matched)
        return self._matched_str

    @property
    def has_matched(self):
        if self._matched:
            return True
        return False

    @property
    def missing(self):
        if not self._missing_str:
            self._missing_str = self._format(
                title="Missing from the game folder",
                items=self._missing)
        return self._missing_str

    @property
    def has_missing(self):
        if self._missing:
            return True
        return False

    @property
    def mismatched(self):
        if not self._mismatched_str:
            self._mismatched_str = self._format(
                title="Same name and different CRC or same CRC with different names",
                items=self._mismatched)
        return self._mismatched_str

    @property
    def has_mismatched(self):
        if self._mismatched:
            return True
        return False

    @property
    def conflicts(self):
        if not self._conflicts_str:
            strings = [f"== Conflicting files between archives:\n"]
            for filepath, archives in self._conflicts.items():
                strings.append(f"  - {filepath}\n        -> ")
                strings.append("\n        -> ".join(archives) + "\n")
            self._conflicts_str = "".join(strings)
        return self._conflicts_str

    @property
    def has_conflicts(self):
        if self._conflicts:
            return True
        return False

    @property
    def skipped(self):
        if not self._ignored_str:
            self._ignored_str = self._format(
                title="Files present in the archive but ignored",
                items=self._ignored)
        return self._ignored_str

    @property
    def has_skipped(self):
        if self._ignored:
            return True
        return False

    # staticmethod used for methods that do not use their bound instances (self)
    @staticmethod
    def _format(self, title, items):
        strings = [f"== {title}:\n"]
        for item in items:
            if 'D' in item.Attributes:
                continue
            crc = hex(item.CRC)
            strings.append(f"  - {item.Path} ({crc})\n")
        strings.append("\n")
        return "".join(strings)
