# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtWidgets import QLabel
from . import dialogs
from . import widgets
from .config import Config
from . import filehandler
from .common import get_config_dir
logging.getLogger('PyQt5').setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(module)s:%(funcName)s:%(message)s',
    filename=get_config_dir("error.log"),
    filemode='w'
)
logger = logging.getLogger(__name__)
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


def _loadStyleSheetFile(file, window):
    try:
        with open(file, 'r') as f:
            window.setStyleSheet(f.read() + '\n')
    except Exception as e:
        logger.debug("Could not load style sheet because: %s", e)


def areSettingsSet():
    if not settings['local_repository']:
        return LOCAL_REPO_NOT_SET
    elif not settings['game_folder']:
        return GAME_FOLDER_NOT_SET
    else:
        return False


class fileChooserWindow(QWidget):
    def __init__(self, callback=None):
        super().__init__()
        self.setWindowTitle("qModManager: archive selection")
        _loadStyleSheetFile('style.css', self)
        self._fileWidget = widgets.fileChooserButton(
            label="Archive selection",
            parent=self,
            callback=self._on_file_selected
        )
        layout = QVBoxLayout()
        layout.addWidget(self._fileWidget.widgets)
        self.setLayout(layout)
        self._callback = callback

    def _on_file_selected(self, file):
        logger.debug("Installing mod to local repository: %s", file)
        if self._callback:
            self._callback(file, self)

    def closeWindow(self):
        """
        Contrarian to its name, this method just hides the window
        """
        self.close()


class dirChooserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qModManager: Settings")
        _loadStyleSheetFile('style.css', self)
        self._gameFolderWidget = widgets.directoryChooserButton(
            label="Game folder",
            parent=self,
            callback=self.on_game_selected,
            default=settings['game_folder']
        )
        self._localRepositoryWidget = widgets.directoryChooserButton(
            label="Local repository",
            parent=self,
            callback=self.on_repo_selected,
            default=settings['local_repository']
        )
        self._doneButton = widgets.contructButton("Done", callback=self.closeWindow)

        layout = QVBoxLayout()
        layout.addWidget(self._gameFolderWidget.widgets)
        layout.addWidget(self._localRepositoryWidget.widgets)
        layout.addWidget(self._doneButton)
        self.setLayout(layout)

    def on_game_selected(self, file):
        settings['game_folder'] = file
        # settings.save()

    def on_repo_selected(self, file):
        settings['local_repository'] = file
        # settings.save()

    def closeWindow(self):
        """
        Contrarian to its name, this method just hides the window
        """
        self.hide()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qModManager")
        _loadStyleSheetFile('style.css', self)

        self._fileList = widgets.CustomList(
            label="Use the + or - button to add or remove items from the list",
            add_function=self._add_mod_action,
            remove_function=self._remove_mod_action,
            itemDoubleClicked=self._on_list_doubleclick
        )
        plainTextEdit = QLabel(parent=self)
        plainTextEdit.setWordWrap(True)
        plainTextEdit.setObjectName("HelpLabel")
        plainTextEdit.setText(
            (
                "Double click an element to set it as active, then click the "
                "apply button to commit your changes. The mod will only be "
                "installed after the apply button get clicked. The discard "
                "button restore your mod list to its last known state.\n"
                "The check left of your mod indicate that it is either "
                "installed, or set to be installed. Its absence means the "
                "contrary."
            )
        )
        self._settings_window = None
        self._adding_files_flag = False
        layout = QVBoxLayout()
        layout.addWidget(self._fileList)
        layout.addWidget(plainTextEdit)
        layout.addWidget(self._initMainButtons())
        self.setLayout(layout)

        self._archive_manager = filehandler.ArchiveManager(settings)
        for item in self._archive_manager.get_files():
            self._fileList += widgets.ListRowItem(
                item,
                self._archive_manager.get_state_by_hash(file_hash=item.hash)
            )

    def _loadStyleSheetFile(self, file):
        try:
            with open(file, 'r') as f:
                self.setStyleSheet(f.read() + '\n')
        except Exception as e:
            logger.debug("Could not load style sheet because: %s", e)

    def _initMainButtons(self):
        self._button_apply = widgets.contructButton("Apply changes", self._do_button_apply)
        self._button_apply.setToolTip("Commits the changes you've made to the list.")
        self._button_discard = widgets.contructButton("Discard changes", self._do_button_discard)
        self._button_discard.setToolTip("Reverts the list to the last known state.")
        self._button_settings = widgets.contructButton("Settings", self._do_button_settings)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self._button_apply)
        buttonLayout.addWidget(self._button_discard)
        buttonLayout.addWidget(self._button_settings)
        buttonWidget = QWidget()
        buttonWidget.setLayout(buttonLayout)
        return buttonWidget

    def _do_button_apply(self):
        """Install and/or uninstalled based on the checkbox state and last known state
        """
        installed_items, uninstalled_items = [], []
        for item in self._fileList:
            installed = self._archive_manager.get_state_by_hash(item.archive_handler.hash)
            if item.enabled:
                if not installed:
                    self._archive_manager.install_mod(item.archive_handler.hash)
                    installed_items.append(item.archive_handler.name)
            else:
                if installed:
                    self._archive_manager.uninstall_mod(item.archive_handler.hash)
                    uninstalled_items.append(item.archive_handler.name)

        detail = ""
        if installed_items:
            message = "Your mods have properly been installed."
            x = ", ".join(installed_items)
            detail = f"Installed: {x}\n"
        if uninstalled_items:
            if installed_items:
                message = "Your mods have successfully been installed and uninstalled."
            else:
                message = "Your mods have properly been uninstalled."
            x = ", ".join(uninstalled_items)
            detail = f"{detail}Uninstalled: {x}"
        if not detail:
            detail = None
        else:
            dialogs.qInformation(
                message,
                detailed=detail
            )

    def _do_button_discard(self):
        """Reinitialize the list to the last known saved state.
        """
        for item in self._fileList:
            installed = self._archive_manager.get_state_by_hash(item.archive_handler.hash)
            if item.enabled and not installed:
                item.enabled = False
            elif not item.enabled and installed:
                item.enabled = True

    def _do_button_settings(self):
        if self._settings_window:
            self._settings_window.show()
        else:
            self._settings_window = dirChooserWindow()
            self._settings_window.show()

    def _do_copy_archive(self, file, widget):
        file_hash = self._archive_manager.add_file(file)
        self._fileList += widgets.ListRowItem(
            self._archive_manager.get_file(file_hash),
            False
        )
        widget.closeWindow()
        self._adding_files_flag = False
        dialogs.qInformation("The archive was properly installed into your list.")

    def _add_mod_action(self):
        settingsNotOk = areSettingsSet()
        if settingsNotOk:
            dialogs.qWarning(
                settingsNotOk,
                informative=INFORMATIVE
            )
            return
        if self._adding_files_flag:
            return
        self._adding_files_flag = True
        add_file = fileChooserWindow(callback=self._do_copy_archive)
        add_file.show()

    def _remove_mod_action(self):
        for item in self._fileList.listWidget.selectedItems():
            logger.info("Removal of file: %s ...", item.archive_handler.hash)
            if self._archive_manager.get_state_by_hash(item.archive_handler.hash):
                logger.info("Uninstalling file: %s ...", item.archive_handler.hash)
                self._archive_manager.uninstall_mod(item.archive_handler.hash)
            self._fileList -= item
            self._archive_manager.remove_file(item.archive_handler.hash)
            logger.info("Removal done for: %s", item.archive_handler.hash)

    def _on_list_doubleclick(self, item, *args):
        if item.enabled:
            item.enabled = False
        else:
            item.enabled = True
