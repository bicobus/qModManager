# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import os
import platform


is_windows = platform.system() in ('Windows', 'Microsoft')
is_linux = platform.system() == 'Linux'


def get_config_dir(filename=None):
    if is_windows:
        def save_config_path(resource):
            appdata_path = os.environ.get('APPDATA')
            if not appdata_path:
                raise UserWarning("I'm on windows but APPDATA is empty.")
            return os.path.join(appdata_path, resource)
    else:
        from xdg.BaseDirectory import save_config_path

    if not filename:
        filename = ''

    try:
        if not os.path.exists(save_config_path('qmm')):
            os.makedirs(save_config_path('qmm'))
    except OSError as e:
        pass

    return os.path.join(save_config_path('qmm'), filename)


def resources_directory():
    return os.path.realpath("qmm/resources/")
