#!/usr/bin/env python
# Licensed under the EUPL v1.2
# © 2020 bicobus <bicobus@keemail.me>

from qmm.lang import set_gettext
# set_gettext() install's gettext _ in the builtins
# doing this before anything has a chance to be called.
set_gettext()

if __name__ == "__main__":
    from qmm import manager
    manager.main()
