#!/usr/bin/env python3
"""VJ GUI launcher — opens the mediaSwitcher web UI in a frameless window.
Auto-detects the TouchDesigner PC (localhost or a configurable IP).
"""
import socket
import sys
import threading
import time
import webbrowser

from PySide6 import QtCore, QtGui, QtWidgets

DEFAULT_PORT = 6060          # TD webserver (was 9090; 9090 is taken by the 909club venue node server on the show PC)
PORT_CANDIDATES = [6060, 9090, 8080]
SETTINGS_FILE = 'vj_gui_settings.txt'


def td_host():
    """Return the host to connect to (saved setting, or localhost)."""
    try:
        with open(SETTINGS_FILE) as f:
            return f.read().strip() or '127.0.0.1'
    except Exception:
        return '127.0.0.1'


def save_host(h):
    with open(SETTINGS_FILE, 'w') as f:
        f.write(h)


def is_alive(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


class QWebEngineView(QtWidgets.QWidget):
    """Minimal wrapper so we can fall back to a browser if WebEngine is missing."""

    def __init__(self):
        super().__init__()


class Launcher(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.host = td_host()
        self.port = DEFAULT_PORT
        self.init_ui()
        self.check_td()

    def init_ui(self):
        self.setWindowTitle('LEDS 909 — VJ')
        self.setWindowIcon(self.make_icon())
        self.resize(1280, 800)
        self.setStatusBar(QtWidgets.QStatusBar())

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # toolbar
        bar = QtWidgets.QHBoxLayout()
        self.host_edit = QtWidgets.QLineEdit(self.host)
        self.host_edit.setFixedWidth(140)
        self.host_edit.setPlaceholderText('TD ip')
        bar.addWidget(QtWidgets.QLabel('TD PC:'))
        bar.addWidget(self.host_edit)

        btn_reconnect = QtWidgets.QPushButton('Reconnect')
        btn_reconnect.clicked.connect(self.reconnect)
        bar.addWidget(btn_reconnect)

        btn_browser = QtWidgets.QPushButton('Open in browser')
        btn_browser.clicked.connect(self.open_browser)
        bar.addWidget(btn_browser)

        btn_fs = QtWidgets.QCheckBox('Always on top')
        btn_fs.setChecked(True)
        btn_fs.toggled.connect(
            lambda on: self.setWindowFlag(
                QtCore.Qt.WindowStaysOnTopHint, on) or self.show())
        bar.addWidget(btn_fs)
        bar.addStretch()
        layout.addLayout(bar)

        # status label (shown while connecting)
        self.status_lbl = QtWidgets.QLabel('Checking for TouchDesigner…')
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.status_lbl.setStyleSheet('color:#888; font-size:16px;')
        layout.addWidget(self.status_lbl)

        # web view (lazy import; falls back to browser)
        self.view = None
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
            self.view = QWebEngineView()
            self.view.loadFinished.connect(self.on_loaded)
            layout.addWidget(self.view)
        except ImportError:
            pass

    def make_icon(self):
        pix = QtGui.QPixmap(32, 32)
        pix.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pix)
        p.setBrush(QtGui.QColor('#4a8'))
        p.drawEllipse(4, 4, 24, 24)
        p.end()
        return QtGui.QIcon(pix)

    def check_td(self):
        """Non-blocking check + connect."""
        self.statusBar().showMessage('Connecting to %s:%d…' % (self.host, self.port))
        threading.Thread(target=self._check_thread, daemon=True).start()

    def _check_thread(self):
        # try the known ports in order; remember the one that answers
        for port in PORT_CANDIDATES:
            if is_alive(self.host, port):
                self.port = port
                QtCore.QMetaObject.invokeMethod(self, 'connect_ui',
                                               QtCore.Qt.QueuedConnection)
                return
        QtCore.QMetaObject.invokeMethod(self, 'show_fail',
                                       QtCore.Qt.QueuedConnection)

    @QtCore.Slot()
    def connect_ui(self):
        # cache-buster: QWebEngine disks-caches pages between runs
        url = 'http://%s:%d/?v=%d' % (self.host, self.port, int(time.time()))
        self.status_lbl.hide()
        if self.view:
            self.view.load(QtCore.QUrl(url))
        else:
            self.open_browser()
        self.statusBar().showMessage('Connected: ' + url)
        save_host(self.host)

    @QtCore.Slot()
    def show_fail(self):
        self.status_lbl.setText(
            'TouchDesigner not found at %s:%d\n'
            'Enter the TD PC\'s IP above and press Reconnect.' % (self.host, self.port))
        self.status_lbl.show()
        self.statusBar().showMessage('Not connected')

    def on_loaded(self, ok):
        if ok:
            self.statusBar().showMessage('Ready')

    def reconnect(self):
        self.host = self.host_edit.text().strip() or '127.0.0.1'
        self.check_td()

    def open_browser(self):
        url = 'http://%s:%d/?v=%d' % (self.host, self.port, int(time.time()))
        webbrowser.open(url)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')

    # dark palette
    pal = QtGui.QPalette()
    pal.setColor(QtGui.QPalette.Window, QtGui.QColor(16, 16, 22))
    pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(180, 180, 180))
    pal.setColor(QtGui.QPalette.Base, QtGui.QColor(24, 24, 30))
    pal.setColor(QtGui.QPalette.Text, QtGui.QColor(200, 200, 200))
    pal.setColor(QtGui.QPalette.Button, QtGui.QColor(36, 36, 44))
    pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(180, 180, 180))
    pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(60, 120, 80))
    app.setPalette(pal)

    win = Launcher()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
