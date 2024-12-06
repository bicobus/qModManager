===============
Version History
===============

`1.0.1`_ - 6-12-24
--------------------------
Fixes
~~~~~
* Workaround build issue from pyinstaller

`1.0.0`_ - 6-12-24
--------------------------
Fixes
~~~~~
* Add support for characters as mod location
* support subfolders for the sex actions and managers

Other
~~~~~
* Moved from python 3.8 to python 3.12
* Solved issues due to API changes from dependencies

`1.0.0-beta10`_ - 09-01-23
--------------------------
Fixes
~~~~~
* xml files present directly under ``namespace/txt/`` weren't considered.

`1.0.0-beta9`_ - 26-12-21
-------------------------
The complexity of mods supported by Lilith Throne made it apparent that the
current way of verifying mods' file structure is lacking. This version introduce
somewhat of a major change in how mods structure are verified. It is much more
modular and precise.

Changed
~~~~~~~
* (internals) Path verification is now strictly matching with what Lilith's
  Throne expects to see.

Added
~~~~~
* Progress information when user uninstall and delete mods

`1.0.0-beta8`_ - 01-12-21
-------------------------
Fixes
~~~~~
* All file contained in archives had their CRC set to 0, leading to them be
  resolved as mismatched.

`1.0.0-beta7`_ - 30-11-21
-------------------------
Fixes
~~~~~
* A typo would allow files that shouldn't be installed to be installed none the
  less.

Added
~~~~~
* Support for new mod location:

  * Dialogue, flags and nodes (``namespace/dialogue/*``)
  * Encounters (``namespace/encounters/*``)
  * Sex actions and managers (``namespace/sex/{managers,actions}/*``)
  * Maps (``namespace/maps/*``)
  * txt folder necessary for the encounter files. (``namespace/txt/*``)

* Allow PNG files to be installed, as they are required for maps.
* Allow users to install, uninstall or remove several mods in one action. Use
  the shift key or the control key to add or remove mods to your selection.


`1.0.0-beta6`_ - 11-07-21
-------------------------
Fixed
~~~~~
* Crash when opening the Settings window introduced by previous version.

`1.0.0-beta5`_ - 11-07-21
-------------------------
Fixed
~~~~~
* (Windows) Crash on launch due to a string mismatch between stored settings and
  python path manipulation. Resolution uses pathlib to handle path manipulation.

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
* Foundations for the internationalization (l10n) of the software through
  gettext
* A Watchdog to monitor both the module's repository and the game's module path

  * The software will automatically add whatever archive dropped in the
    module's repository
  * The software will automatically determine if the game's module directory
    has been modified and regenerate it's database the next time the
    application gain focus
  * A checkbox exists to disable this behavior if unchecked.

* Internal dev stuff: changes of libraries used, reworking codebase, etc


.. _`1.0.2`: https://github.com/bicobus/qModManager/compare/v1.0.1...development
.. _`1.0.1`: https://github.com/bicobus/qModManager/compare/v1.0.0...v1.0.1
.. _`1.0.0`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta11...v1.0.0
.. _`1.0.0-beta10`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta9...v1.0.0-beta10
.. _`1.0.0-beta9`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta8...v1.0.0-beta9
.. _`1.0.0-beta8`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta7...v1.0.0-beta8
.. _`1.0.0-beta7`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta6...v1.0.0-beta7
.. _`1.0.0-beta6`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta5...v1.0.0-beta6
.. _`1.0.0-beta5`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta4...v1.0.0-beta5
.. _`1.0.0-beta4`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta2...v1.0.0-beta4
.. _`1.0.0-beta3`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta2...v1.0.0-beta3
.. _`1.0.0-beta2`: https://github.com/bicobus/qModManager/compare/v1.0.0-beta1...v1.0.0-beta2
.. _`1.0.0-beta1`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha13...v1.0.0-beta1
.. _`1.0.0-alpha13`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha12...v1.0.0-alpha13
.. _`1.0.0-alpha12`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha11...v1.0.0-alpha12
.. _`1.0.0-alpha11`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha10...v1.0.0-alpha11
.. _`1.0.0-alpha10`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha9...v1.0.0-alpha10
.. _`1.0.0-alpha9`: https://github.com/bicobus/qModManager/compare/v1.0.0-alpha8...v1.0.0-alpha9
