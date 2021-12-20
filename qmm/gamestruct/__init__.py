# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
import sys


class GameStructure:
    def __init__(self, validators):
        self._validators = validators

    def validate(self, path):
        for validator in self._validators:
            try:
                validator(path)
            except ValueError:
                pass  # failure is assumed by default
            else:
                return True
        return False


def as_validator(fn):
    mod = sys.modules[fn.__module__]
    if hasattr(mod, "validators"):
        mod.validators.append(fn)  # type: ignore
    else:
        mod.validators = [fn]  # type: ignore
    if hasattr(mod, "main_folders"):
        mod.main_folders.append(fn.primary())
    else:
        mod.main_folders = [fn.primary()]
    if fn.secondary():  # Optional
        if hasattr(mod, "sub_folders"):
            mod.sub_folders.update({fn.primary(): fn.secondary()})
        else:
            mod.sub_folders = {fn.primary(): fn.secondary()}
    return fn
