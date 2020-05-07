# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
__author__ = "Bicobus"
__credits__ = ["bicobus"]
__license__ = "EUPL V1.2"
__version__ = "1.0"
__maintainer__ = "bicobus"
__email__ = "bicobus@keemail.me"
__status__ = "alpha"

import os
import sys
import platform
import logging


def is_frozen():
    return bool(getattr(sys, 'frozen', False))


def get_base_path():
    if getattr(sys, 'frozen', False):
        r = os.path.dirname(sys.executable)
    elif 'sphinx' in sys.modules:
        r = os.path.abspath('..')
    elif __file__:
        r = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        raise Exception("Unable to find application's path.")
    return r


def get_data_path(relpath):
    path = os.path.join(get_base_path(), relpath)
    return path


logging.getLogger('PyQt5').setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s:%(name)s:%(module)s:%(funcName)s:%(message)s',
    filename=os.path.join(get_base_path(), 'error.log'),
    filemode='w'
)
logger = logging.getLogger(__name__)
logger.debug("Base path is %s", get_base_path())

is_windows = platform.system() in ('Windows', 'Microsoft')
is_linux = platform.system() == 'Linux'
