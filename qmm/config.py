# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import json
import logging
import tempfile
import shutil
import atexit
import gzip

from codecs import getwriter
from collections.abc import MutableMapping
from appdirs import AppDirs
from PyQt5.QtCore import QTimer
from . import is_windows
logger = logging.getLogger(__name__)
dirs = AppDirs(appname='qmm', appauthor=False)


def get_config_dir(filename=None, extra_directories=None):
    config_path = []
    if extra_directories and isinstance(extra_directories, list):
        config_path.extend(extra_directories)
    if filename:
        config_path.append(filename)
    path = os.path.join(dirs.user_config_dir, *config_path)
    return path


class Config(MutableMapping):
    """
    Influenced by deluge's config object.
    """

    def __init__(self, filename, config_dir=None, defaults=None,
                 compress=False):
        self._data = dict()
        self._save_timer = False
        self._compress = compress

        if defaults:
            for key, val in defaults.items():
                self[key] = val

        if config_dir:
            self._filename = os.path.join(config_dir, filename)
        else:
            self._filename = get_config_dir(filename)

        if self._compress:
            self._filename = "{}.gz".format(self._filename)

        # self._timer = QTimer(parent)
        # Force saving config file at termination of the software
        atexit.register(self.save)

        self.load(self._filename)

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        if key not in self._data:
            self._data[key] = value
            return

        if self._data[key] == value:
            return
        self._data[key] = value

        logger.debug("Config key state changed, save timer state is: %s", self._save_timer)
        if not self._save_timer:
            self.delayed_save()

    def __delitem__(self, key):
        del(self._data[key])

        logger.debug("Deleting config key, save timer state is: %s", self._save_timer)
        if not self._save_timer:
            self.delayed_save()

    def _get_data_from_file(self, filename=None):
        if not os.path.exists(filename):
            return None

        try:
            if self._compress:
                with gzip.GzipFile(filename, 'r') as fp:
                    json_bytes = fp.read()
                data = json.loads(json_bytes.decode('utf-8'))
            else:
                with open(filename, 'r', encoding="utf-8") as f:
                    data = json.load(f)
        except IOError as e:
            logger.warning("Unable ti load config file %s: %s", filename, e)
            return None
        return data

    def load(self, filename=None):
        if not filename:
            filename = self._filename
        elif self._compress and os.path.splitext(filename)[1] != ".gz":
            filename = "{}.gz".format(filename)

        logger.debug("Loading information from settings file: %s", filename)
        data = self._get_data_from_file(filename)
        if data:
            self._data.update(data)

    def delayed_save(self, msec=5000):
        if not self._save_timer:
            QTimer.singleShot(msec, self.save)
            self._save_timer = True
            logger.debug("Changing save timer state to %s", self._save_timer)

    def save(self, filename=None):
        if not filename:
            filename = self._filename
        elif self._compress and os.path.splitext(filename) != ".gz":
            filename = "{}.gz".format(filename)

        logger.debug("Saving file %s", filename)
        # Do not save anything if the contents are the same.
        try:
            data = self._get_data_from_file(filename)
            if self._data == data:
                logger.debug("Save triggered but data is unchanged: doing nothing.")
                if self._save_timer:
                    # self._timer.stop()
                    self._save_timer = False
                    logger.debug("Changing save timer state to %s", self._save_timer)
                return True
        except IOError as e:
            logger.warning("Unable to load config file %s: %s", filename, e)

        try:
            with tempfile.NamedTemporaryFile(delete=False) as fp:
                filename_tmp = fp.name
                if self._compress:
                    fp.write(gzip.compress(json.dumps(self._data, indent=4).encode('utf-8')))
                else:
                    json.dump(self._data, getwriter('utf8')(fp), indent=4)
                fp.flush()
                os.fsync(fp)
        except IOError as e:
            logger.warning("Unable to write temporary config file: %s", e)
            return False

        filename = os.path.realpath(filename)

        try:
            shutil.move(filename, "{}.bak".format(filename))
        except IOError as e:
            logger.warning("Unable to backup old settings: %s", e)

        try:
            if is_windows:
                dirname = os.path.dirname(filename)
                if not os.path.exists(dirname):
                    os.makedirs(os.path.dirname(filename))
            shutil.move(filename_tmp, filename)
        except IOError as e:
            logger.error("Error moving new config file: %s", e)
            return False
        else:
            logger.debug("Check save timer at end of save method. State: %s", self._save_timer)
            if self._save_timer:  # Disable timed callback
                self._save_timer = False
                logger.debug("Changing save timer state to %s", self._save_timer)
                # self._timer.stop()
            return True
