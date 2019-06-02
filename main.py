#!/usr/bin/env python
# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import sys
from PyQt5.QtWidgets import QApplication
from qmm.manager import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())
