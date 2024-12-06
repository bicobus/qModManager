# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019-2021 bicobus <bicobus@keemail.me>
__author__ = "Bicobus"
__credits__ = ["bicobus"]
__license__ = "EUPL V1.2"
__version__ = "1.0.3"
__maintainer__ = "bicobus"
__email__ = "bicobus@keemail.me"
__status__ = "stable"

import os
import sys
import platform
import logging


def running_ci():
    """Return True if currently running in a CI environment.

    This function is used to alter the behavior of the software for specific CI runs.

    Returns:
        boolean
    """
    return bool(os.environ.get('QMM_CI'))


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def get_base_path() -> str:
    if getattr(sys, "frozen", False):
        r = os.path.dirname(sys.executable)
    elif "sphinx" in sys.modules:
        r = os.path.abspath("..")
    elif __file__:
        if not sys.argv[0] == 'run.py':
            r = os.path.join(os.path.dirname(__file__), '..')
        else:
            r = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        raise Exception("Unable to find application's path.")
    return r


def get_data_path(relpath):
    path: list[str] = [get_base_path()]
    if is_frozen():
        path.append("_internal")
    path.append(relpath)
    return os.path.join(*path)


# Uncomment if PyQt5 floods the log file.
# logging.getLogger("PyQt5").setLevel(logging.WARNING)
hdlrs = [
    logging.FileHandler(filename=os.path.join(get_base_path(), "error.log"), mode="w")
]
if running_ci():
    hdlrs.append(logging.StreamHandler(sys.stdout))
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s:%(name)s:%(module)s:%(funcName)s:%(message)s",
    handlers=hdlrs,
)
logger = logging.getLogger(__name__)
logger.info("Base path is %s", get_base_path())

is_windows = platform.system() in ("Windows", "Microsoft")
is_linux = platform.system() == "Linux"
