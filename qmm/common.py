# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019-2021 bicobus <bicobus@keemail.me>
import logging
import os
import pathlib
import subprocess
from datetime import datetime
from typing import List, Tuple, Union

from qmm import get_data_path, is_linux, is_windows, running_ci
from qmm.config import Config
from qmm.settings.validators import IsDirValidator

logger = logging.getLogger(__name__)


#: instance of the Config object that governs the user's preferences. Can be imported anywhere
#: in the app
settings = Config(
    filename="settings.json" if not running_ci() else "test.json",
    defaults={
        "local_repository": None,
        "game_folder": None,
        "language": "system"
    },
    on_load_validators={
        "local_repository": IsDirValidator,
        "game_folder": IsDirValidator,
    },
)


if is_windows:

    def _command():
        return r"C:\Program Files", r"C:\Program Files (x86)"

    def startfile(file):
        return os.startfile(file)  # pylint: disable=no-member

    toolsalias = {
        "svgedit": "Inkscape",
        "svgpreview": "inkview",
        "xmledit": "Notepad++",
    }
    toolspaths = {
        "Inkscape": ("Inkscape", "inkscape.exe"),
        "inkview": ("Inkscape", "inkview.exe"),
        "Notepad++": ("Notepad++", "notepad++.exe"),
    }
elif is_linux:

    def _command():
        return os.environ["PATH"].split(":")

    # NOTE: funky shit is going on between xfce4 and gnome based software
    def startfile(file):
        return subprocess.Popen(
            ("/usr/bin/xdg-open", file),
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            shell=False,
        )

    toolsalias = {
        "svgedit": "Inkscape",
        "svgpreview": "inkview",
        "xmledit": None,
    }
    toolspaths = {
        "Inkscape": ["inkscape"],
        "inkview": ["inkview"],
    }


def command(binary, alias=False):
    """Return path to binary or None if not found.

    Analogous to bash's command, but do not actually execute anything.

    Args:
        binary (str): Name of binary to find in PATH
        alias (bool): True if the name is an alias to be looked up the pre-made
            dict. `alias` is only useful for windows OS as the binary can be
            a tuple. Aliases are also used to find predefined software without
            the need of calling them by name, good for cross platform.

    Returns:
        os.Pathlike or None: Path to the binary or None if not found.
    """
    if alias:
        binary = "/".join(toolspaths[toolsalias[binary]])
    for path in _command():
        check = pathlib.Path(path, binary)
        if check.exists():
            return check
    return None


def acommand(alias):
    return command(alias, True)


def settings_are_set():
    """Returns False if either 'local_repository' or 'game_folder' isn't set."""
    if not settings["local_repository"] or not settings["game_folder"]:
        return False
    return True


def bundled_tools_path():
    """Returns the path to the bundled 7z executable."""
    if is_windows:
        return os.path.join(get_data_path("tools"), "7z.exe")
    return "7z"


def timestamp_to_string(timestamp):
    """Takes a UNIX timestamp and return a vernacular date."""
    return datetime.strftime(datetime.fromtimestamp(timestamp), "%c")


def valid_suffixes(output_format="qfiledialog",) -> Union[List[str], Tuple[str, str, str], bool]:
    """Properly format a list of filters for QFileDialog.

    Args:
        output_format (str): Accepts either 'qfiledialog' or 'pathlib'.
            'pathlib' returns a simple list of suffixes, whereas 'qfiledialog'
            format the output to be an acceptable filter for QFileDialog.

    Returns:
        list: a list of valid suffixes.
    """
    if output_format not in ("qfiledialog", "pathlib"):
        return False

    labels = ("7Zip Files", "Zip Files", "Rar Files")
    suffixes = (".7z", ".zip", ".rar")
    if output_format == "qfiledialog":
        filter_on, tpl = [], []
        for s in suffixes:
            tpl.append(f"*{s}")  # *.ext
        string = "All Archives({})".format(" ".join(tpl))
        filter_on.append(string)
        for label, s in zip(labels, tpl):
            filter_on.append(f"{label} ({s})")
        return filter_on
    return suffixes
