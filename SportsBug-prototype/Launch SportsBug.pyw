"""Double-click this launcher on Windows to start without a console window."""
import sys
from PySide6.QtWidgets import QApplication
from sportsbug import Bug, configure_windows_identity, sportsbug_icon

configure_windows_identity()
app = QApplication(sys.argv)
app.setWindowIcon(sportsbug_icon())
app.setQuitOnLastWindowClosed(True)
bug = Bug()
sys.exit(app.exec())
