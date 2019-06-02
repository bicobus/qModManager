= qModManager

Simple tool to manage a set of archives.

 * Track their state
 * Unpack into a designated directory

== Requirements

To install system wide:

```
~$ pip -r requirements.txt
```

To install in a virtual environement:
```
~$ pipenv install
```

If you chose pipenv, you can then start the application using the following, provided you are in the same path as the main.py file.
```
~$ pipenv run ./main.py
```

If you chose to install the dependencies system wide, you can simply start the main.py file:
```
~$ python main.py
```