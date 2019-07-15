# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import logging
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from PyQt5.QtWidgets import QLabel
from . import dialogs
from . import settings
from . import widgets
from . import filehandler
from .common import get_config_dir
from .common import loadQtStyleSheetFile
logging.getLogger('PyQt5').setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s:%(name)s:%(module)s:%(funcName)s:%(message)s',
    filename=get_config_dir("error.log"),
    filemode='w'
)
logger = logging.getLogger(__name__)


class dirChooserWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("qModManager: Settings")
        loadQtStyleSheetFile('style.css', self)
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
        loadQtStyleSheetFile('style.css', self)

        self._archive_manager = filehandler.ArchiveManager(settings)
        self._fileList = widgets.CustomList(
            parent=self,
            label="Use the + or - button to add or remove items from the list"
        )
        self._settings_window = None

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
        layout = QVBoxLayout()
        layout.addWidget(self._fileList)
        layout.addWidget(plainTextEdit)
        layout.addWidget(self._initMainButtons())
        self.setLayout(layout)

        # Load all known archives into the list
        for item in self._archive_manager.get_files():
            self._fileList.create_and_add_item(
                item,
                self._archive_manager.get_state_by_hash(file_hash=item.hash),
                self._archive_manager.get_fileinfo_by_hash(file_hash=item.hash)
            )

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
            installed = self._archive_manager.get_state_by_hash(item.hash)
            if item.enabled:
                if not installed:
                    self._archive_manager.install_mod(item.hash)
                    installed_items.append(item.name)
                    item.refresh_fdata()
            else:
                if installed:
                    self._archive_manager.uninstall_mod(item.hash)
                    uninstalled_items.append(item.name)
                    item.refresh_fdata()

        # Gui Stuff
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
