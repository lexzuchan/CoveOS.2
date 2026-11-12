from pathlib import Path
from urllib.parse import quote_plus, urlsplit

from PyQt6 import sip
from PyQt6.QtCore import QSettings, Qt, QUrl
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog, QLineEdit, QMainWindow, QMenu, QTabWidget, QToolBar, QToolButton
)
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView


HOME = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<style>
:root{color-scheme:light dark}body{margin:0;min-height:100vh;display:grid;
place-items:center;background:light-dark(#edf4f3,#102529);
font:16px 'Segoe UI',sans-serif;color:light-dark(#153a3c,#e7f3ef)}
main{text-align:center;padding:32px}h1{font-size:56px;letter-spacing:-3px;
font-weight:600;margin:0 0 12px}p{opacity:.8}form{margin-top:28px}
input{box-sizing:border-box;width:min(360px,80vw);padding:14px 18px;
border:1px solid #749694;border-radius:24px;font:inherit;background:Canvas}
</style><main><h1>Cove Browser</h1><p>Search the web</p>
<form action="https://duckduckgo.com/"><input name=q aria-label="Search the web"
placeholder="Search with DuckDuckGo" required></form></main>"""


def address_url(text):
    text = text.strip()
    try:
        parts = urlsplit(text)
        if parts.scheme.lower() in {"https", "http"} and parts.hostname:
            return QUrl(text)
        if " " not in text and (not parts.scheme or parts.scheme == "localhost"):
            candidate = QUrl.fromUserInput(text)
            host = candidate.host()
            if candidate.scheme() in {"http", "https"} and (host == "localhost" or "." in host):
                return candidate
    except ValueError:
        pass
    return QUrl("https://duckduckgo.com/?q=" + quote_plus(text))


class Browser(QMainWindow):
    def __init__(self, settings, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle("Cove Browser")
        self.resize(1100, 740)
        self.settings: QSettings = settings
        self.profile = QWebEngineProfile("CoveWeb", self)
        self.profile.downloadRequested.connect(self.download)
        self.tabs = QTabWidget(tabsClosable=True, movable=True, documentMode=True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.refresh_address)
        self.setCentralWidget(self.tabs)
        bar = QToolBar("Navigation", movable=False, floatable=False)
        self.addToolBar(bar)
        self.action(bar, "←", "Alt+Left", lambda: self.current().back(), "Back")
        self.action(bar, "→", "Alt+Right", lambda: self.current().forward(), "Forward")
        self.action(bar, "↻", "Ctrl+R", lambda: self.current().reload(), "Reload")
        self.address = QLineEdit(placeholderText="Search or enter a web address", clearButtonEnabled=True)
        self.address.setAccessibleName("Address and search")
        self.address.returnPressed.connect(self.navigate)
        bar.addWidget(self.address)
        self.action(bar, "＋", "Ctrl+T", self.new_tab, "New tab")
        self.action(bar, "☆", "Ctrl+D", self.bookmark, "Bookmark this page")
        self.saved = QToolButton(text="Bookmarks")
        self.saved.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bookmarks = QMenu(self.saved)
        self.bookmarks.aboutToShow.connect(self.populate_bookmarks)
        self.saved.setMenu(self.bookmarks)
        bar.addWidget(self.saved)
        self.action(None, "Close tab", "Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex()))
        self.action(None, "Address", "Ctrl+L", self.focus_address)
        self.new_tab()

    def action(self, bar, label, shortcut, handler, tooltip=None):
        action = QAction(label, self, shortcut=QKeySequence(shortcut))
        action.setToolTip(tooltip or label)
        action.triggered.connect(lambda: handler())
        (bar or self).addAction(action)

    def current(self):
        return self.tabs.currentWidget()

    def new_tab(self, url=None, *, show_home=True):
        view = QWebEngineView()
        page = QWebEnginePage(self.profile, view)
        view.setPage(page)
        page.newWindowRequested.connect(
            lambda request: request.openIn(self.new_tab(show_home=False).page())
        )
        view.urlChanged.connect(lambda _: self.refresh_address() if view is self.current() else None)
        view.titleChanged.connect(lambda title: self.title_changed(view, title))
        view.loadFinished.connect(lambda success: self.load_finished(view, success))
        self.tabs.setCurrentIndex(self.tabs.addTab(view, "New tab"))
        if url is not None:
            view.load(url)
        elif show_home:
            view.setHtml(HOME)
            self.focus_address()
        return view

    def close_tab(self, index):
        view = self.tabs.widget(index)
        if view is None:
            return
        if self.tabs.count() == 1:
            self.new_tab()
        self.tabs.removeTab(self.tabs.indexOf(view))
        view.deleteLater()

    def shutdown(self):
        # Pages must be destroyed before their shared Chromium profile.
        self.close()
        for view in self.tabs.findChildren(QWebEngineView):
            sip.delete(view)
        sip.delete(self.profile)

    def title_changed(self, view, title):
        index = self.tabs.indexOf(view)
        if index >= 0:
            self.tabs.setTabText(index, title[:36] or "New tab")
            self.tabs.setTabToolTip(index, title)

    def refresh_address(self, *_):
        view = self.current()
        if view:
            url = view.url()
            self.address.setText(url.toDisplayString() if url.scheme() in {"http", "https"} else "")

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def navigate(self):
        if self.address.text().strip():
            self.current().load(address_url(self.address.text()))
            self.current().setFocus()

    def load_finished(self, view, success):
        if not success and view is self.current():
            self.statusBar().showMessage("Page could not be loaded", 5000)

    def bookmark(self):
        view = self.current()
        url = view.url()
        if url.scheme() not in {"http", "https"}:
            return
        saved = self.settings.value("bookmarks", {}, type=dict)
        saved[url.toString()] = view.title() or url.host()
        self.settings.setValue("bookmarks", saved)
        self.statusBar().showMessage("Bookmark saved", 2500)

    def populate_bookmarks(self):
        self.bookmarks.clear()
        saved = self.settings.value("bookmarks", {}, type=dict)
        for url, title in saved.items():
            action = self.bookmarks.addAction(title)
            action.triggered.connect(lambda checked, url=url: self.new_tab(QUrl(url)))
        if not saved:
            self.bookmarks.addAction("No bookmarks yet").setEnabled(False)

    def download(self, request):
        suggested = Path(request.downloadDirectory()) / request.downloadFileName()
        name, _ = QFileDialog.getSaveFileName(self, "Save download", str(suggested))
        if not name:
            request.cancel()
            return
        destination = Path(name)
        request.setDownloadDirectory(str(destination.parent))
        request.setDownloadFileName(destination.name)
        request.isFinishedChanged.connect(
            lambda: self.statusBar().showMessage(f"{destination.name} · {request.state().name.removeprefix('Download')}", 6000)
        )
        request.accept()
        self.statusBar().showMessage(f"Downloading {destination.name}")
