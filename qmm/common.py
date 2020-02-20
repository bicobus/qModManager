# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import logging
from typing import List
from datetime import datetime
from . import is_windows, get_data_path
from .config import Config


logger = logging.getLogger(__name__)

settings = Config(
    filename="settings.json",
    defaults={
        "local_repository": None,
        "game_folder": None,
        "language": None
    }
)


def settings_are_set():
    """Returns False if either 'local_repository' or 'game_folder' isn't set."""
    if not settings['local_repository'] or not settings['game_folder']:
        return False
    return True


def tools_path():
    """Returns the path to the 7z executable.

    TODO: needs a better name
    """
    if is_windows:
        return os.path.join(get_data_path('tools'), '7z.exe')
    return '7z'


def timestamp_to_string(timestamp):
    """Takes a UNIX timestamp and return a vernacular date."""
    return datetime.strftime(datetime.fromtimestamp(timestamp), "%c")


def valid_suffixes(output_format="qfiledialog") -> List[str]:
    """Properly format a list of filters for QFileDialog.

    Args:
        output_format:
            Accepts either 'qfiledialog' or 'pathlib'. 'pathlib' returns a simple
            list of suffixes, whereas 'qfiledialog' format the output to be an
            acceptable filter for QFileDialog.

    Returns: list
    """
    if output_format not in ('qfiledialog', 'pathlib'):
        return False

    labels = ('7Zip Files', 'Zip Files', 'Rar Files')
    suffixes = ('.7z', '.zip', '.rar')
    if output_format == "qfiledialog":
        filter_on, tpl = [], []
        for s in suffixes:
            tpl.append(f"*{s}")
        string = 'All Archives (' + " ".join(tpl) + ')'
        filter_on.append(string)
        for l, s in zip(labels, tpl):
            filter_on.append(f"{l} ({s})")
        return filter_on
    return suffixes

