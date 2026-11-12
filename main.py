import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QLockFile, QPointF, QSettings, QSize, QStandardPaths, Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QLinearGradient, QPainter, QPainterPath, QPalette, QRadialGradient, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow, QMenu,
    QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget
)

from cove.browser import Browser
from cove.icons import dock_icon
from cove.native import focus_window, installed_apps, open_windows


WALLPAPERS = {
    "Tide": ("#0a143a", "#292b75", "#5064dc", "#a6c5ff", "#aea0ff"),
    "Dusk": ("#231337", "#6a3469", "#b0567f", "#ffc4a3", "#eb91ac"),
    "Glacier": ("#081c31", "#174b66", "#228a9a", "#a6efdd", "#71d7df"),
}
ACCENTS = {"Sea glass": "#79ddc6", "Sky": "#9bc8ff", "Lilac": "#c5adff", "Peach": "#ffc2a5"}
ACTIONS = ("Apps", "Files", "Browser", "Windows", "Appearance")


class Wallpaper(QWidget):
    def __init__(self, desktop):
        super().__init__()
        self.desktop = desktop

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        first, second, third, fourth, glow = WALLPAPERS[self.desktop.wallpaper]
        gradient = QLinearGradient(QPointF(0, h * .12), QPointF(w, h))
        gradient.setColorAt(0, QColor(first))
        gradient.setColorAt(.7, QColor(second))
        gradient.setColorAt(1, QColor(first))
        painter.fillRect(self.rect(), gradient)
        halo = QRadialGradient(QPointF(w * .72, h * .30), w * .62)
        color = QColor(glow)
        color.setAlpha(100)
        halo.setColorAt(0, color)
        color.setAlpha(0)
        halo.setColorAt(1, color)
        painter.fillRect(self.rect(), halo)
        for offset, opacity in ((-.15, .36), (0, .94), (.12, .82), (.28, .85)):
            wave = QPainterPath(QPointF(-w * .08, h * (.77 + offset)))
            wave.cubicTo(w * .15, h * (1.21 + offset), w * .38, h * (.65 + offset),
                         w * .53, h * (.50 + offset))
            wave.cubicTo(w * .72, h * (.29 + offset), w * .88, h * (.42 + offset),
                         w * 1.08, h * (-.13 + offset))
            wave.lineTo(w * 1.08, h * 1.6)
            wave.lineTo(-w * .08, h * 1.6)
            wave.closeSubpath()
            painter.setOpacity(opacity)
            ribbon = QLinearGradient(w * .7, h * (.32 + offset), w * .49, h * (1.04 + offset))
            ribbon.setColorAt(0, QColor(fourth))
            ribbon.setColorAt(.32, QColor(third))
            ribbon.setColorAt(.7, QColor(second))
            ribbon.setColorAt(1, QColor(first))
            painter.fillPath(wave, ribbon)


class Desktop(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.browser = None
        self.wallpaper = self.option("wallpaper", WALLPAPERS)
        self.accent = self.option("accent", ACCENTS)
        self.mode = self.option("theme", ("Dark", "Light"))
        self.dock_size = min(120, max(86, settings.value("dockSize", 100, type=int)))
        self.dock_hidden = {
            name for name in ACTIONS[1:-1] if not settings.value("dock/" + name, True, type=bool)
        }
        self.setWindowTitle("Cove Desktop")
        self.setMinimumSize(620, 440)
        self.resize(1150, 760)
        self.surface = Wallpaper(self)
        self.surface.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCentralWidget(self.surface)
        stage = QVBoxLayout(self.surface)
        stage.setContentsMargins(0, 0, 0, 20)
        stage.setSpacing(0)
        self.header = QFrame(objectName="menuBar")
        top = QHBoxLayout(self.header)
        top.setContentsMargins(16, 2, 18, 2)
        top.setSpacing(4)
        menu = QPushButton("◒  Cove", objectName="brand")
        system_menu = QMenu(menu)
        for label, handler in (
            ("Enter / exit full screen", self.fullscreen), ("Windows Settings", self.windows_settings),
            ("Minimize desktop", self.showMinimized), ("Quit Cove", self.close),
        ):
            system_menu.addAction(label).triggered.connect(handler)
        menu.setMenu(system_menu)
        top.addWidget(menu)
        for label in ("Apps", "Windows"):
            top.addWidget(self.button(label, lambda name=label: self.run_action(name)))
        top.addStretch()
        for glyph, label, handler in (
            ("\ue721", "Search apps (Ctrl+Space)", self.search),
            ("\ue713", "Appearance", self.appearance),
        ):
            control = self.button(glyph, handler)
            control.setObjectName("menuIcon")
            control.setAccessibleName(label)
            control.setToolTip(label)
            top.addWidget(control)
        self.clock = QLabel(objectName="clock")
        top.addWidget(self.clock)
        stage.addWidget(self.header)
        stage.addStretch()
        self.dock = QFrame(objectName="dock")
        self.dock_layout = QHBoxLayout(self.dock)
        self.dock_layout.setContentsMargins(10, 9, 10, 9)
        self.dock_layout.setSpacing(9)
        stage.addWidget(self.dock, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.shortcuts = []
        for key, handler in (
            ("Ctrl+Space", self.search), ("Ctrl+Shift+Space", lambda: self.search(True)),
            ("F11", self.fullscreen),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(handler)
            self.shortcuts.append(shortcut)
        self.timer = QTimer(self, interval=1000)
        self.timer.timeout.connect(self.update_clock)
        self.timer.start()
        self.update_clock()
        self.build_dock()
        self.apply_theme()
        self.surface.setFocus()

    def option(self, key, values):
        choice = self.settings.value(key, next(iter(values)), type=str)
        return choice if choice in values else next(iter(values))

    def button(self, label, handler):
        button = QPushButton(label)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: handler())
        return button

    def update_clock(self):
        now = datetime.now()
        self.clock.setText(f"{now:%a %b} {now.day}   {now.strftime('%I:%M %p').lstrip('0')}")

    def build_dock(self):
        while self.dock_layout.count():
            self.dock_layout.takeAt(0).widget().deleteLater()
        for name in ACTIONS:
            if name in self.dock_hidden:
                continue
            button = self.button("", lambda name=name: self.run_action(name))
            button.setObjectName("dockIcon")
            button.setAccessibleName(name)
            button.setToolTip(name)
            size = round(50 * self.dock_size / 100)
            artwork_size = size - 4
            button.setIcon(dock_icon(name, artwork_size, self.devicePixelRatioF()))
            button.setIconSize(QSize(artwork_size, artwork_size))
            button.setFixedSize(size, size)
            self.dock_layout.addWidget(button)

    def apply_theme(self):
        dark = self.mode == "Dark"
        ink, muted, surface, elevated, border, hover = (
            ("#f4f5fb", "#aeb7cd", "#141a2a", "#1d263b", "#3b465f", "#293650") if dark else
            ("#172037", "#52617b", "#f4f6fc", "#ffffff", "#c7d0e0", "#e3eaf8")
        )
        chrome = "rgba(14, 20, 38, 213)" if dark else "rgba(243, 247, 255, 226)"
        chrome_border = "rgba(213, 225, 255, 64)" if dark else "rgba(255, 255, 255, 226)"
        accent = ACCENTS[self.accent]
        palette = QPalette()
        for role, color in {
            QPalette.ColorRole.Window: surface, QPalette.ColorRole.WindowText: ink,
            QPalette.ColorRole.Base: elevated, QPalette.ColorRole.Text: ink,
            QPalette.ColorRole.Button: surface, QPalette.ColorRole.ButtonText: ink,
            QPalette.ColorRole.Highlight: accent, QPalette.ColorRole.HighlightedText: "#14252b",
            QPalette.ColorRole.PlaceholderText: muted,
        }.items():
            palette.setColor(role, QColor(color))
        app = QApplication.instance()
        app.setPalette(palette)
        app.setStyleSheet(f"""
            QWidget {{font-family:'Segoe UI'; font-size:14px; color:{ink};}}
            QDialog, QMenu, QMainWindow, QToolBar {{background:{surface};}}
            QFrame#menuBar {{background:{chrome};border-bottom:1px solid {chrome_border};}}
            QPushButton, QToolButton {{background:transparent;border:1px solid transparent;
                border-radius:7px;padding:6px 10px;}}
            QPushButton:hover, QToolButton:hover, QMenu::item:selected {{background:{hover};}}
            QPushButton:focus, QToolButton:focus, QLineEdit:focus {{border-color:{accent};}}
            QPushButton#brand {{font-weight:700;}}
            QPushButton#brand::menu-indicator {{width:0;}}
            QPushButton#menuIcon {{font-family:'Segoe MDL2 Assets';font-size:15px;padding:6px 8px;}}
            QLabel#clock {{font-size:13px;padding-left:9px;}}
            QFrame#dock {{background:{chrome};border:1px solid {chrome_border};border-radius:21px;}}
            QLineEdit {{background:{elevated};border:1px solid {border};
                border-radius:9px;padding:9px 13px;}}
            QPushButton#dockIcon {{border-radius:13px;border:1px solid transparent;padding:0;}}
            QPushButton#dockIcon:hover {{background:{hover};}}
            QPushButton#dockIcon:focus {{border-color:{accent};}}
            QMenu {{border:1px solid {border};padding:5px;}}
            QMenu::item {{padding:7px 18px;}}
            QListWidget {{background:{elevated};border:1px solid {border};border-radius:9px;padding:5px;}}
            QListWidget::item {{padding:8px;}}
            QListWidget::item:selected {{background:{accent};color:#14252b;border-radius:5px;}}
            QDialog#launcher {{background:transparent;}}
            QFrame#launcherPanel {{background:{surface};border:1px solid {border};border-radius:21px;}}
            QLabel#panelTitle {{font-size:19px;font-weight:600;}}
            QLabel#panelHint {{font-size:12px;color:{muted};}}
            QLineEdit#launcherInput {{font-size:19px;padding:12px 15px;}}
            QListWidget#launcherResults {{background:transparent;border:0;padding:0;outline:0;}}
            QListWidget#launcherResults::item {{padding:9px 12px;}}
            QListWidget#launcherResults::item:selected {{
                background:{hover};color:{ink};border-radius:8px;border-left:3px solid {accent};}}
            QListWidget#launcherResults QScrollBar:vertical {{
                width:7px;background:transparent;margin:3px 0;}}
            QListWidget#launcherResults QScrollBar::handle:vertical {{
                min-height:24px;background:{border};border-radius:3px;}}
            QListWidget#launcherResults QScrollBar::add-line:vertical,
            QListWidget#launcherResults QScrollBar::sub-line:vertical {{height:0;}}
            QListWidget#launcherResults QScrollBar::add-page:vertical,
            QListWidget#launcherResults QScrollBar::sub-page:vertical {{background:transparent;}}
            QComboBox {{padding:5px 8px;}}
            QToolBar {{border:0;padding:6px;spacing:5px;}}
            QTabBar::tab {{background:{surface};padding:8px 12px;min-width:84px;}}
            QTabBar::tab:selected {{background:{elevated};border-bottom:2px solid {accent};}}
        """)
        self.surface.update()

    def run_action(self, action):
        if action == "Apps":
            self.search()
        elif action == "Files":
            subprocess.Popen(["explorer.exe"])
        elif action == "Browser":
            self.show_browser()
        elif action == "Windows":
            self.search(True)
        elif action == "Appearance":
            self.appearance()

    def show_browser(self):
        if self.browser is None:
            self.browser = Browser(self.settings, self)
        if self.browser.isMinimized():
            self.browser.showNormal()
        self.browser.show()
        self.browser.raise_()
        self.browser.activateWindow()
        return self.browser

    def search(self, windows=False):
        title = "Switch windows" if windows else "App launcher"
        dialog = QDialog(self, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setObjectName("launcher")
        dialog.setWindowTitle(title)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dialog.resize(min(590, self.width() - 40), min(420, self.height() - 55))
        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame(objectName="launcherPanel")
        outer.addWidget(panel)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 14, 20, 13)
        layout.setSpacing(10)
        header = QHBoxLayout()
        header.addWidget(QLabel(title, objectName="panelTitle"))
        header.addStretch()
        close = self.button("Esc", dialog.reject)
        close.setAccessibleName("Close launcher")
        close.setAutoDefault(False)
        header.addWidget(close)
        layout.addLayout(header)
        field = QLineEdit(placeholderText="Find an open window…" if windows else "Find an app…",
                          clearButtonEnabled=True, objectName="launcherInput")
        field.setAccessibleName(field.placeholderText())
        results = QListWidget(objectName="launcherResults")
        results.setAccessibleName("Results")
        results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(field)
        layout.addWidget(results)
        layout.addWidget(QLabel("↑ ↓  Navigate     Enter  Open", objectName="panelHint"))
        entries = open_windows() if windows else [
            ("Cove Browser", self.show_browser), ("File Explorer", lambda: self.run_action("Files")),
            ("Windows Settings", self.windows_settings), *installed_apps()
        ]
        if windows and self.browser and self.browser.isVisible():
            entries.insert(0, ("Cove Browser", self.show_browser))
        matches = []

        def filter_results():
            tokens = field.text().casefold().split()
            matches[:] = [(name, value) for name, value in entries if all(token in name.casefold() for token in tokens)]
            results.clear()
            results.addItems([name for name, _ in matches])
            if matches:
                results.setCurrentRow(0)
            else:
                results.addItem("No matches" if tokens else "No open windows")
                results.item(0).setFlags(Qt.ItemFlag.NoItemFlags)

        selected = []

        def choose():
            row = results.currentRow()
            if 0 <= row < len(matches):
                selected.append(matches[row][1])
                dialog.accept()

        field.textChanged.connect(filter_results)
        field.returnPressed.connect(choose)
        results.itemActivated.connect(lambda item: choose())
        for key, offset in (("Down", 1), ("Up", -1)):
            shortcut = QShortcut(QKeySequence(key), field, context=Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(
                lambda offset=offset: results.setCurrentRow(max(0, min(len(matches) - 1, results.currentRow() + offset)))
            )
        filter_results()
        field.setFocus()
        if dialog.exec() and selected:
            target = selected[0]
            try:
                if callable(target):
                    target()
                elif windows:
                    if not focus_window(target):
                        self.showMinimized()
                        focus_window(target)
                else:
                    os.startfile(target)
            except OSError as error:
                QMessageBox.warning(self, "Could not open app", str(error))

    def appearance(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Cove appearance")
        dialog.resize(460, 335)
        form = QFormLayout(dialog)
        form.setContentsMargins(22, 22, 22, 22)
        form.setVerticalSpacing(14)
        form.addRow(QLabel("Appearance", objectName="panelTitle"))
        for label, key, values, attribute in (
            ("Theme", "theme", ("Dark", "Light"), "mode"),
            ("Accent", "accent", ACCENTS, "accent"),
            ("Wallpaper", "wallpaper", WALLPAPERS, "wallpaper"),
        ):
            combo = QComboBox()
            combo.addItems(values)
            combo.setCurrentText(getattr(self, attribute))
            combo.currentTextChanged.connect(
                lambda value, key=key, attribute=attribute: self.update_appearance(key, attribute, value)
            )
            form.addRow(label, combo)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(86, 120)
        slider.setValue(self.dock_size)
        slider.valueChanged.connect(lambda value: self.update_appearance("dockSize", "dock_size", value))
        form.addRow("Dock size", slider)
        row = QHBoxLayout()
        for name in ACTIONS[1:-1]:
            check = QCheckBox(name)
            check.setChecked(name not in self.dock_hidden)
            check.toggled.connect(lambda checked, name=name: self.set_dock_item(name, checked))
            row.addWidget(check)
        form.addRow("Dock apps", row)
        done = self.button("Done", dialog.accept)
        form.addRow("", done)
        dialog.exec()

    def set_dock_item(self, name, checked):
        if checked:
            self.dock_hidden.discard(name)
        else:
            self.dock_hidden.add(name)
        self.settings.setValue("dock/" + name, checked)
        self.build_dock()

    def update_appearance(self, key, attribute, value):
        setattr(self, attribute, value)
        self.settings.setValue(key, value)
        if key == "dockSize":
            self.build_dock()
        self.apply_theme()

    def fullscreen(self):
        self.showMaximized() if self.isFullScreen() else self.showFullScreen()

    def windows_settings(self):
        os.startfile("ms-settings:")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    app = QApplication([sys.argv[0]])
    app.setApplicationName("Cove")
    app.setOrganizationName("CoveDesktop")
    app.setStyle("Fusion")
    lock_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_dir / "application.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock():
        QMessageBox.information(None, "Cove is open", "Open Cove Browser from the running Cove Desktop.")
        return 0
    desktop = Desktop(QSettings())
    if args.browser:
        desktop.show_browser()
    else:
        desktop.showMaximized()
    try:
        return app.exec()
    finally:
        if desktop.browser:
            desktop.browser.shutdown()


if __name__ == "__main__":
    sys.exit(main())
