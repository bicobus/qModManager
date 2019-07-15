# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
__author__ = "Bicobus"
__credits__ = ["bicobus"]
__license__ = "EUPL V1.2"
__version__ = "0.0"
__maintainer__ = "bicobus"
__email__ = "bicobus@keemail.me"
__status__ = "Development"

import os
from .config import Config

settings = Config(
    filename="settings.json",
    defaults={
        "local_repository": None,
        "game_folder": None
    }
)
LOCAL_REPO_NOT_SET = """The location of your local repository of archives is unknown.

That folder will be used to store the different archives."""
GAME_FOLDER_NOT_SET = """The location of your game folder is unknown.

It has to be the folder containing the game 'res' folder, <b>NOT</b> the res/mods folder."""
INFORMATIVE = "Click on the 'settings' button on the bottom of the main window."

resource_path = os.path.join(os.path.dirname(__file__), 'resources')


def file_from_resource_path(file):
    return os.path.join(resource_path, file)


def areSettingsSet():
    if not settings['local_repository']:
        return LOCAL_REPO_NOT_SET
    elif not settings['game_folder']:
        return GAME_FOLDER_NOT_SET
    else:
        return False
