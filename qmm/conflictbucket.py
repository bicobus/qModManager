# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>


class ConflictBucket:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConflictBucket, cls).__new__(cls)
            cls._instance._conflicts = {}
            cls._instance._looseconflicts = {}
            cls._instance._gamefiles = None
            cls._instance._loosefiles = None
        return cls._instance

    @property
    def conflicts(self):
        return self._conflicts

    @conflicts.setter
    def conflicts(self, value):
        self._conflicts = value

    @property
    def gamefiles(self):
        return self._gamefiles

    @gamefiles.setter
    def gamefiles(self, gamefiles):
        self._gamefiles = gamefiles

    @property
    def loosefiles(self):
        return self._loosefiles

    @loosefiles.setter
    def loosefiles(self, loosefiles):
        self._loosefiles = loosefiles

    @property
    def looseconflicts(self):
        return self._looseconflicts

    def has_loose_conflicts(self, file):
        self._looseconflicts.setdefault(file.CRC, [])
        self._looseconflicts[file.CRC].append(self.loosefiles[file.CRC])
