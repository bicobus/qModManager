===============
Version History
===============

`1.0.0-beta4`_ - 11-07-21
-------------------------
* No changes, new release to have the build working.

`1.0.0-beta3`_ - 10-07-21
-------------------------
Fixed
~~~~~
* Crash if the directory structure of the game files was too short. Structure
  is expected to be ``category/namespace/**.xml``, the software used to crash
  if there was a dangling file under the *category* folder.
* Crash when parsing race mods file structures.
* Possible issue if users had their game within a path containing folders ending
  with res/

`1.0.0-beta2`_ - 16-12-20
-------------------------
Added
~~~~~
* Support for modded races
* Support for modded colours
* Support for modded combatMove
* Should scan game patterns

`1.0.0-beta1`_ - 09-09-20
-------------------------
Added
~~~~~
* Support items pattern (mods only)
* Descriptive text for each option of the settings window. Should help with
  confusing options.

Changed
~~~~~~~
* Ignore unrecognized sub-folders under ``namespace/items/``
* Prompt the user to restart the application if the specified settings options
  are changed.
* Prompt the user to open the settings window if required.

Fixed
~~~~~
* Crash: ZipFiles created using no compression method would crash the
  application. This is due to an absence of information within the attributes.
  Resolved by being less strict in normalizing file attributes read for the
  archive: if it is not explicitly a folder, then it is a file.
* Crash: If the paths stored in the user settings file did no longer point to an
  existing folder.

`1.0.0-alpha13`_ - 02-09-20
---------------------------
Fixed
~~~~~
* Crash on windows platform.

`1.0.0-alpha12`_ - 02-09-20
---------------------------
Added
~~~~~
* A context menu on the treeview if the file is present on disk:

  * Open containing folder
  * Open file using text editor, graphics editor or both (for svg)

* List untracked files present in the ``res/mods`` folder. It is understood by
  untracked that files existing in the folder weren't found in any of the
  archives.

* Support for new mod files

  * ``res/mods/statusEffects``
  * ``res/mods/setBonuses``
  * ``res/mods/items/items``

Changed
~~~~~~~
* Directories in the treeview now properly show their status.
* Context menus rewritten in a less stupid way.
* Archives context menu disable entries when they don't apply, an archive that
  is not installed cannot be uninstalled and so on.
* Got rid of the resources files for the setting window. It is now
  programatically built, which helps with maintenance.

`1.0.0-alpha11`_ - 20-05-12
---------------------------
Added
~~~~~
* Color code each managed item based on their status

  * Each line has a dual color: left and right
  * Right side can either be transparent or red, to show existing conflicts.
  * Left side can either be green, blue or yellow

    * Yellow is for missing files
    * Blue is for mismatched files
    * Green is when every files of the archive matches on the drive.

  * Greyed out text means the archive contains nothing that can be installed
  * The Help buttons will send users to the readthedocs website.

Changed
~~~~~~~

* Each file is now beautifully displayed in a tree instead of using a TextInput
* Files are color coded depending on their states.
* The conflicts tab details where a file as been found as duplicate: *GameFile*
  or *Archive*

Fixed
~~~~~

* Fix crash related to file system watch (watchdog)

`1.0.0-alpha10`_
----------------

* Same as alpha9, but working.

`1.0.0-alpha9`_
---------------

* Send archives to the trashbin instead of a full removal from the hard drive.
* Foundations for the internationalisation (l10n) of the software through
  gettext
* A Watchdog to monitor both the module's repository and the game's module path

  * The software will automatically add whatever archive dropped in the
    module's repository
  * The software will automatically determine if the game's module directory
    has been modified and regenerate it's database the next time the
    application gain focus
  * A checkbox exists to disable this behavior if unchecked.

* Internal dev stuff: changes of libraries used, reworking codebase, etc

.. _`1.0.0-beta4`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta2...v1.0.0-beta4
.. _`1.0.0-beta3`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta2...v1.0.0-beta3
.. _`1.0.0-beta2`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta1...v1.0.0-beta2
.. _`1.0.0-beta1`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha13...v1.0.0-beta1
.. _`1.0.0-alpha13`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha12...v1.0.0-alpha13
.. _`1.0.0-alpha12`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha11...v1.0.0-alpha12
.. _`1.0.0-alpha11`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha10...v1.0.0-alpha11
.. _`1.0.0-alpha10`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha9...v1.0.0-alpha10
.. _`1.0.0-alpha9`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha8...v1.0.0-alpha9
