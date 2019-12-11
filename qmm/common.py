# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
from datetime import datetime
from . import is_windows
from .config import Config


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
