# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import sys
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
    return True


def tools_path():
    if is_windows:
        if getattr(sys, 'frozen', False):
            rel = os.path.dirname(sys.executable)
        elif __file__:
            rel = os.path.dirname(__file__)
        else:
            raise Exception("Unable to find application's path.")
        return os.path.join(rel, 'tools', '7z.exe')
    return '7z'


def resources_directory():
    return os.path.realpath("qmm/resources/")


def timestamp_to_string(timestamp):
    """Takes a UNIX timestamp and return a vernacular date
    """
    return datetime.strftime(datetime.fromtimestamp(timestamp), "%c")
