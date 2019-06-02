# qModManager

Simple tool to manage a set of archives.

 * Track their state
 * Unpack into a designated directory

## Requirements

On a windows machine, you might need to use `python -m pip [cmd]` instead of pip. It'll depend wether or not the python binaries are present in your `%PATH%`.

To install system wide:

```
~$ pip -r requirements.txt
```

To install in a virtual environement:
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