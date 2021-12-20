#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>

from qmm.lang import set_gettext


def main():
    # set_gettext() install's gettext _ in the builtins
    # doing this before anything has a chance to be called.
    set_gettext()
    from qmm import manager
    manager.main()


if __name__ == "__main__":
    main()
