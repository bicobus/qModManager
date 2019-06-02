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

resource_path = os.path.join(os.path.dirname(__file__), 'resources')


def file_from_resource_path(file):
    return os.path.join(resource_path, file)
