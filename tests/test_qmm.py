# -*- coding: utf-8 -*-
# Licensed under the EUPL v1.2
# © 2021 bicobus <bicobus@keemail.me>
import logging, os

import pytest

# from qmm import manager


def test_qmm(qmm):
    logging.getLogger().warning(qmm.__dict__)
    qmm.main()
