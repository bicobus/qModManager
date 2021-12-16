# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020-2021 bicobus <bicobus@keemail.me>
import os.path as osp
from pathlib import Path

import attr


def make_html_list(elements):
    """Helper function to display a list of item within Qt."""
    if not isinstance(elements, list):
        return "<b>" + elements + "</b>"
    ul = "<ul>{}</ul>"
    li = "<li><b>{}</b></li>"
    felem = "".join(map(li.format, elements))
    return ul.format(felem)


@attr.s(frozen=True)
class IsDirValidator:
    """Validate a setting entry as an existing directory."""

    data: str = attr.ib(converter=Path)

    @data.validator
    def validate(self, a, v):
        if v and not osp.isdir(v):
            try:
                raise ValueError(_("Invalid directory path"))
            except NameError:  # settings and gettext not initialized yet
                raise ValueError("Invalid directory path")


@attr.s(frozen=True)
class IsFileValidator:
    """Validate a setting entry as an existing file."""

    data: str = attr.ib()

    @data.validator
    def validate(self, a, v):
        if v and not osp.exists(v):
            raise ValueError(_("Path does not point to a file"))
