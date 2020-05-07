.. image:: https://static.deepsource.io/deepsource-badge-light-mini.svg
    :target: https://deepsource.io/gh/bicobus/qModManager/?ref=repository-badge

.. image:: https://ci.appveyor.com/api/projects/status/hn7a0oa12qhg62ds?svg=true
    :target: https://ci.appveyor.com/project/bicobus/qmodmanager

.. image:: https://readthedocs.org/projects/qmodmanager/badge/?version=latest
    :target: https://qmodmanager.readthedocs.io/en/latest/?badge=latest

=============
PyQModManager
=============

Simple tool to manage a set of archives. Written to manage mods available for
the game `Lilith's Throne`_.

* Track the state of the different files bundled with each archives
* Unpack into a designated directory

Installation and Requirements
------------------------------

Windows
^^^^^^^

If you are running windows, a self contained binary is provided at each release.
Please check the releases_
page to download the archive. Running the application is a simple as double
clicking the .exe file present in the archive.

Linux
^^^^^

You'll need to install python3 with whatever package manager your distribution
provides you. This application has been developped using python 3.7, any prior
version might work, but untested. If you feel adventurous, you can checkout
pyenv_.

This software being a python script, it doesn't need to be installed. However
requirements are needed for that purpose.

You'll need whatever is presesent in the `requirements.txt`_. As
Linux distributions such as debian are commonly out of date, I'd recommend
installing the requirement locally, under your user directory, with the
following command.

::

    ~$ pip install --user -r requirements.txt


You could also opt to install in a virtual environment through pipenv.
``pipenv install`` will use the Pipfile already present in the repository.

::

    ~$ pip install pipenv
    ~$ pipenv install


Running the app
+++++++++++++++
If you chose pipenv, you can then start the application using the following,
provided you are in the same folder as the run.py file.

::

    ~$ pipenv run ./run.py


If you opted for the simple pip install, simply execute run.py.

::

    ~$ python run.py


Known issues
------------
The software is currently being rewritten, as such no known limitation exists.
This might change once we get out of alpha.

Hacking
-------
If you want to hack around, you only require the dependencies listed in the
`requirements.txt`_ file. The Pipfile has a list of dev-packages,
which is unneeded to actually run and develop the software. They're helper
tools, like pylint or flake8

Documentation generator
^^^^^^^^^^^^^^^^^^^^^^^
The documentation is currently available at https://qmodmanager.rtfd.io/

The generation of the documentation on readthedocs.org necessitate some extra
steps in order to successfuly generate the api documentation. We have to
generate ui files at build time, which are not included in the repository nor
available to rtd. Therefore a script apidoc_ has been provided as helper.

The apidoc_ script will forcefully generate the required files for the
api. In addition of that, it will also parse the various UI files present in the
resources folder and generate stubs in the `_ext folder`_. Those
stubs needs to be regenerated whenever a UI file is added to the resources
folder.

.. _apidoc: docs/apidoc.sh
.. _\_ext folder: docs/_ext/
.. _requirements.txt: requirement.txt
.. _releases: https://github.com/bicobus/qModManager/releases
.. _lilith's throne: https://github.com/Innoxia/liliths-throne-public
.. _pyenv: https://github.com/pyenv/pyenv