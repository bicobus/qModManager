# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
from datetime import datetime
from . import SETTINGS_HELP, is_windows
from . import widgets
from .config import Config
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel


logger = logging.getLogger(__name__)

settings = Config(
    filename="settings.json",
    defaults={
        "local_repository": None,
        "game_folder": None
    }
)


def settings_are_set():
    if not settings['local_repository'] or not settings['game_folder']:
        return False
    else:
        return True


def areSettingsSet():
    return settings_are_set()


def tools_path():
    if is_windows:
        return os.path.join(os.path.dirname(__file__), 'tools', '7z.exe')
    else:
        return '7z'


def resources_directory():
    return os.path.realpath("qmm/resources/")


def timestampToString(timestamp):
    """Takes a UNIX timestamp and return a vernacular date
    """
    return datetime.strftime(datetime.fromtimestamp(timestamp), "%c")


def loadQtStyleSheetFile(file, window):
    try:
        with open(file, 'r') as f:
            window.setStyleSheet(f.read() + '\n')
    except Exception as e:
        logger.debug("Could not load style sheet because: %s", e)


class dirChooserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qModManager: Settings")
        loadQtStyleSheetFile('style.css', self)

        text = QLabel(parent=self)
        text.setWordWrap(False)
        text.setObjectName("settings_label")
        text.setText(SETTINGS_HELP)

        self._gameFolderWidget = widgets.directoryChooserButton(
            label="Game folder",
            parent=self,
            callback=self.on_game_selected,
            default=settings['game_folder']
        )

        self._localRepositoryWidget = widgets.directoryChooserButton(
            label="Local repository",
            parent=self,
            callback=self.on_repo_selected,
            default=settings['local_repository']
        )

        self._doneButton = widgets.constructButton("Done", callback=self.closeWindow)

        layout = QVBoxLayout()
        layout.addWidget(text)
        layout.addWidget(self._gameFolderWidget.widgets)
        layout.addWidget(self._localRepositoryWidget.widgets)
        layout.addWidget(self._doneButton)
        self.setLayout(layout)

    def on_game_selected(self, file):
        settings['game_folder'] = file
        # settings.save()

    def on_repo_selected(self, file):
        settings['local_repository'] = file
        # settings.save()

    def closeWindow(self):
        """
        Contrarian to its name, this method just hides the window
        """
        self.hide()
