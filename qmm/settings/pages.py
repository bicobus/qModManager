# -*- coding: utf-8 -*-
#  Licensed under the EUPL v1.2
#  © 2020 bicobus <bicobus@keemail.me>

from PyQt5.QtWidgets import QGroupBox, QVBoxLayout

from qmm.settings.core_dialogs import Page
from qmm.lang import LANGUAGE_CODES


class GeneralPage(Page):
    NAME = _("General")

    def setup_ui(self):
        ggroup = QGroupBox(_("General"))

        repo_folder = self.c_browsedir(
            _("Archives repository"),
            "local_repository",
            _(
                "Path to the folder containing your collection of mod archives. This folder will "
                "contain a local copy of your mods. It should be its own empty folder, with "
                "nothing else than the game's mod archives."
            ),
            restart=True,
        )

        game_folder = self.c_browsedir(
            _("Game Location"),
            "game_folder",
            _(
                "Path to the folder containing the jar or exe of the game. It has to be the "
                "folder containing the res/ subdirectory."
            ),
            restart=True,
        )

        langs = [(_("System"), "system"), (None, None)] + LANGUAGE_CODES
        langw = self.c_combobox(_("Language"), langs, "language", restart=True)

        glayout = QVBoxLayout()
        glayout.addWidget(repo_folder)
        glayout.addWidget(game_folder)
        glayout.addWidget(langw)
        ggroup.setLayout(glayout)

        wlayout = QVBoxLayout()
        wlayout.addWidget(ggroup)
        self.setLayout(wlayout)
