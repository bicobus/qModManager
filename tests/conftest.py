# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>

import os

import pytest


@pytest.fixture(scope="session")
def qmm():
    from qmm.lang import set_gettext
    set_gettext()
    from qmm import manager
    yield manager
