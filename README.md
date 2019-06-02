# qModManager

Simple tool to manage a set of archives.

 * Track their state
 * Unpack into a designated directory

## Requirements

On a windows machine, you might need to use `python -m pip [cmd]` instead of pip. It'll depend whether or not the python binaries are present in your `%PATH%`.

On a windows OS, you'll have to download and install the pre-compiled wheel for pylzma as the library has a C++ component to it. They are available there: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pylzma

To install system wide:

```
~$ pip install name_of_wheel.whl # if your OS is windows
~$ pip install -r requirements.txt
```

To install in a virtual environment:
```
~$ pipenv install
```

## Running the app

If you chose pipenv, you can then start the application using the following, provided you are in the same path as the main.py file.
```
~$ pipenv run ./main.py
```

If you chose to install the dependencies system wide, you can simply start the main.py file:
```
~$ python main.py
```

## Known issues

The manager does not verify if the files to be installed already exists, it'll simply fail to install them and continue as if nothing happened.