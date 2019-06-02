#!/usr/bin/env python
# Licensed under the EUPL v1.2
# © 2019 bicobus <bicobus@keemail.me>
import sys
from PyQt5.QtWidgets import QApplication
from qmm.manager import MainWindow, logger

if __name__ == "__main__":
    logger.info("Starting application")
    try:
        app = QApplication(sys.argv)
        mw = MainWindow()
        mw.show()
        sys.exit(app.exec_())
    except Exception:
        logger.exception("Critical error occured:")
        raise
    finally:
        logger.info("Application shutdown complete.")
