:Authors:
    Bicobus <bicobus@keemail.me>

:Version:
    1.1 of 12/05/2020

.. |fileadd| image:: ../resources/icons/file-add-line.svg
.. |filedel| image:: ../resources/icons/delete-bin-5-line.svg
.. |installfile| image:: ../resources/icons/install-line.svg
.. |uninstallfile| image:: ../resources/icons/uninstall-line.svg

=====
Usage
=====
In this document will inform you about various elements of the graphical user
interface of PyQModManager.

Settings
--------
The software needs to know two on disk locations: where the game is located and
a space to store the modules you've downloaded.

The game location should be the folder containing the .jar or .exe of the game.
The archive repository for your module should be a random *empty* folder of your
choice.

Adding modules to be tracked by the software
--------------------------------------------
The software keeps track of 3 types of archives: Rar files, 7z files and Zip
files. Two ways exists to have the game track modules:

1. Drop an archive in the repository folder.
2. Use the |fileadd| button from the toolbar.

If you use |fileadd|, the archive file will be copied over the repository folder
leaving the original file untouched.

Removing an archive
-------------------
Select the archive you wish to delete and click on the trashbin (|filedel|)
button. Alternatively, right-click on the archive and select the appropriate
option. PyQModManager sends all removed archives to your trashbin, which you
will need to empty manually.

Installing a module
-------------------
Select the archive you wish to install then click on the install
(|installfile|) button of the toolbar. Alternatively, you can right-click the
archive and select the install option.

Only files natively handled by Lilith's Throne mod system are supported. Any
other file or folder will be ignored.

Supported paths structure
~~~~~~~~~~~~~~~~~~~~~~~~~
A proper structure for a mod would be the following::

    namespace/
    |-- items
    |   |-- clothing
    |   |   `-- category
    |   |       |-- cloth_test.svg
    |   |       `-- cloth_test.xml
    |   |-- items
    |   |   `-- category
    |   |       |-- itemName.svg
    |   |       `-- itemName.xml
    |   |-- patterns
    |   |   |-- pattern_name.svg
    |   |   `-- pattern_name.xml
    |   |-- tattoos
    |   |   `-- category
    |   |       |-- tattoo_test.svg
    |   |       `-- tattoo_test.xml
    |   `-- weapons
    |       `-- category
    |           |-- weapon_test.svg
    |           `-- weapon_test.xml
    |-- outfits
    |   `-- OutfitName
    |       `-- outfit_test.xml
    |-- setBonuses
    |   `-- template.xml
    `-- statusEffects
        |-- set_itemName.svg
        `-- set_itemName.xml


The first folder must be the namespace, or colloquially the name of the modder.
The module will be ignored if it is packaged with the initial ``/res/mods``
folders. The software will look for the existence of the sub-folders ``items``,
``setBonuses``, ``statusEffects`` and ``outfits``.

If the ``items`` folder is found, the software will then verify the existence of
the following sub-folders: ``clothing``, ``weapons``, ``tattoos``, ``patterns``
and ``items``.

Uninstalling a module
---------------------
Select the archive you wish to uninstall then click on the uninstall
(|uninstallfile|) button of the toolbar. Alternatively, you can right-click the
archive and select the uninstall option.

Monitoring of the hard drive
----------------------------
The software will monitor file-system changes on both the game's module folder
and the folder you designated as repository. The software will automatically
scan any archive dropped in your repository folder, as well as making sure
the game's module folder remains known even if you unpack files through other
means than PyQModManager.

You can toggle off that behavior through the auto-refresh checkbox located above
the list of your available modules. Doing so will activate a refresh button,
located right next to the checkbox, which will allow you to manually refresh the
internal database if you make changes to the file system.

The monitoring of the file-system is designed to be as lightweight as possible.
It disable itself whenever PyQModManager becomes inactive (alt-tab or
minimized), and reactive itself whenever the software gain focus. Gaining back
focus will force a refresh of the database on a needed basis: if nothing has
changed, nothing is done.
