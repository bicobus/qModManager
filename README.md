# qModManager

[![DeepSource](https://static.deepsource.io/deepsource-badge-light.svg)](https://deepsource.io/gh/bicobus/qModManager/?ref=repository-badge)

Simple tool to manage a set of archives. Written to manage mods available for
[Lilith's Throne](https://github.com/Innoxia/liliths-throne-public)

 * Track the state of the different files bundled with each archives
 * Unpack into a designated directory

## Requirements

On a windows machine, you might need to use `python -m pip [cmd]` instead of
pip. It'll depend whether or not the python binaries are present in your `%PATH%`.

To install dependencies system wide:

```
~$ pip install -r requirements.txt
```

To install in a virtual environment:
```
~$ pip install pipenv
~$ pipenv install
```

## Running the app

If you chose pipenv, you can then start the application using the following,
provided you are in the same path as the main.py file.
```
~$ pipenv run ./main.py
```

If you chose to install the dependencies system wide, you can simply start the main.py file:
```
~$ python main.py
```

Under windows, builds will be provided for each releases.

## Known issues

The software is currently being rewritten, this will be populated at a later date.

