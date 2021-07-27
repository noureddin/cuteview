#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

import configparser
import subprocess
import tempfile
import shutil
import sys
import os


poppler = shutil.which('pdfinfo') is not None
mutool  = shutil.which('mutool')  is not None
if mutool:
    render = lambda longdim, invert, outfile, outfile_base, pdfpath, pageidx: [
        'mutool', 'draw',
            '-w', str(longdim),
            '-h', str(longdim),
            *(['-I', '-c', 'g'] if invert else []),
            '-o', outfile,
            pdfpath, str(pageidx + 1),
        ]
else:
    render = lambda longdim, invert, outfile, outfile_base, pdfpath, pageidx: [
        'pdftoppm', '-singlefile',
            '-f', str(pageidx + 1),
            '-scale-to', str(longdim),
            *(['-gray'] if invert else []),
            pdfpath,
            outfile_base,
        ]
# mutool can invert, and saves to the gives name (including the extension).
# pdftoppm cannot invert, but forces the extension it sees fit (e.g., '.pgm' if grayscale).


# (XDG_DATA_HOME || ~/.local/share) + ./cuteview
DATA_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "cuteview")
HIST_INI = os.path.join(DATA_DIR, 'history')

if not os.path.exists(DATA_DIR):
    os.mkdir(DATA_DIR)


DEFAULT_INVERT = False
DEFAULT_TRIM   = False
(MIN_OPACITY, STEP_OPACITY, DEFAULT_OPACITY, MAX_OPACITY) = (0, 5, 255, 255)


class Pages(QWidget):

    fileChanged = pyqtSignal()

    def __init__(self, first, *rest):
        super().__init__()
        self.page = 0
        self.title = None
        self.invert = None
        self.invert_but_no_mutool = lambda: self.invert and not mutool
        # This being true implies that:
        #   the outfile extension is 'pgm' not 'ppm'; and
        #   the outfile is not inverted, although it's only grayscale instead.
        if len(rest) == 0 and first.lower().endswith('.pdf'):
            self.mode = 'PDF'  # pdf reader mode
            self.invert = DEFAULT_INVERT
            self.trim = DEFAULT_TRIM
            self.opacity = DEFAULT_OPACITY
            self.pdfpath = first
            self.ext = lambda: 'pgm' if self.invert_but_no_mutool() else 'ppm'
            self.__dir = tempfile.TemporaryDirectory()
            (self.origtitle, self.length) = self.__pdfInfo()
            self.__getPage = lambda longdim: self.__getPdfPage(self.page, longdim)
            self.dim = [0] * self.length
            self.inv = [DEFAULT_INVERT] * self.length
            self.toPrefetch = 1
            self.readHist()
            # monitoring file changes
            self.watcher = QFileSystemWatcher([first])
            def changed():
                (self.origtitle, self.length) = self.__pdfInfo()
                for page in range(self.length):
                    file = os.path.join(self.__dir.name, f"{page}.{self.ext()}")
                    if os.path.exists(file):
                        os.unlink(file)
                self.fileChanged.emit()
            self.watcher.fileChanged.connect(changed)
        else:
            self.mode = 'Images'  # image viewer mode
            self.opacity = MAX_OPACITY
            self.pages = [first, *rest]
            self.length = len(self.pages)
            self.__getPage = lambda _: self.__getImg(self.pages[self.page])
            self.__load(0, 1, 1024)

    def __getTitle(self):
        suf = " ({}/{})".format(self.page + 1, self.length)
        if self.mode == 'Images':
            return os.path.basename(self.pages[self.page]) + suf
        else:  # PDF
            return self.origtitle + suf

    def __load(self, page, toPrefetch, *a):
        self.page = page % self.length
        self.toPrefetch = toPrefetch % self.length
        self.title = self.__getTitle()
        return self.__getPage(*a)

    def getPage(self, *a):
        return self.__load(self.page, self.toPrefetch, *a)

    def next(self, *a): return self.__load(self.page + 1, self.page + 2, *a)
    def prev(self, *a): return self.__load(self.page - 1, self.page - 2, *a)

    def prefetch(self):
        if self.mode == 'PDF':
            self.__getPdfPage(self.toPrefetch, self.dim[self.page])

    def __getImg(self, path):
        # https://doc.qt.io/qt-5/qtwidgets-widgets-imageviewer-example.html
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        newimg = reader.read()
        if newimg == QImage():
            # TODO: show this error msg on the window
            print("Cannot load {}: {}".format(
                QDir.toNativeSeparators(path), reader.errorString()), file=sys.stderr)
        if self.invert_but_no_mutool():  # the user wants it inverted, but it's not
            newimg.invertPixels()
        return QPixmap.fromImage(newimg)

    def lessOpaque(self):
        if self.mode == 'PDF':
            self.opacity = max(MIN_OPACITY, self.opacity - STEP_OPACITY)
    def moreOpaque(self):
        if self.mode == 'PDF':
            self.opacity = min(MAX_OPACITY, self.opacity + STEP_OPACITY)

    def toggleInvert(self): self.invert = not self.invert
    def toggleTrim(self):   self.trim   = not self.trim

    def __getPdfPage(self, pageidx, longdim):
        pageidx %= self.length
        outfile_base = os.path.join(self.__dir.name, str(pageidx))
        outfile = outfile_base + '.' + self.ext()
        isdiff = self.dim[pageidx] < longdim or self.inv[pageidx] != self.invert
        if not os.path.exists(outfile) or isdiff:
            self.dim[pageidx] = longdim
            self.inv[pageidx] = self.invert
            subprocess.run(
                render(longdim, self.invert, outfile, outfile_base, self.pdfpath, pageidx),
                stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        self.__reducepdfcache(5, 5)
        return self.__getImg(outfile)

    def __pdfInfo(self):
        title = None
        count = 0
        for line in subprocess.run(['pdfinfo', self.pdfpath], capture_output=True).stdout.split(b'\n'):
            if line.startswith(b'Title:'):
                title = line.split(None, 1)[1].decode('utf-8')  # it's bytes
            if line.startswith(b'Pages:'):
                count = int(line.split()[1])
        if title is None:
            title = os.path.basename(self.pdfpath).split(os.path.extsep)[0]
        return (title, count)

    def __reducepdfcache(self, keepBefore, keepAfter):
        if keepBefore + keepBefore >= self.length + 1:
            return
        for page in range(self.page + keepAfter + 1,  self.page - keepBefore + self.length):
            file = os.path.join(self.__dir.name, f"{page % self.length}.{self.ext()}")
            if os.path.exists(file):
                os.unlink(file)

    # HISTORY

    def __getConfigAndSectionName(self):
        config = configparser.RawConfigParser(empty_lines_in_values=False)
        section = os.path.abspath(self.pdfpath).replace('[', '_').replace(']', '_').replace('\n', '_')
        # yes, I want the POSIX behavior of treating 'a/../b' as 'b' as if symlinks were not invented,
        # not the more correct behavior of pathlib.
        config.read(HIST_INI)
        return (config, section)

    def readHist(self):
        (config, section) = self.__getConfigAndSectionName()
        if section not in config:
            return
        this = config[section]
        self.page = this.getint('page', self.page)
        self.invert = this.getboolean('invert', self.invert)
        self.trim = this.getboolean('trim', self.trim)
        self.opacity = this.getint('opacity', self.opacity)
        #
        if self.page >= self.length:
            self.page = self.length - 1
        if self.page < 0:
            self.page = 0
        self.toPrefetch = (self.page + 1) % self.length

    def writeHist(self):
        if self.mode != 'PDF':
            return
        (config, section) = self.__getConfigAndSectionName()
        existed = section in config
        old = dict(config[section]) if existed else None
        config[section] = {
                'page':    self.page,
            **({'invert':  self.invert}  if self.invert  != DEFAULT_INVERT  else {}),
            **({'trim':    self.trim}    if self.trim    != DEFAULT_TRIM    else {}),
            **({'opacity': self.opacity} if self.opacity != DEFAULT_OPACITY else {}),
        }
        if dict(config[section]) == {'page': '0'}:  # there is nothing to save
            del config[section]
            dirty = existed  # to delete the history
        else:  # there is something to save
            dirty = dict(config[section]) != old
        if dirty:
            with open(HIST_INI, 'w') as configfile:
                config.write(configfile)


class TouchViewer(QWidget):

    def __init__(self, pages, setTitle):
        super().__init__()
        self.pages = pages
        self.setTitle = setTitle
        self.writeHist = self.pages.writeHist
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        #
        self.setAttribute(Qt.WA_AcceptTouchEvents)
        # self.grabGesture(Qt.PanGesture)
        self.grabGesture(Qt.PinchGesture)
        self.grabGesture(Qt.SwipeGesture)
        #
        self.initUI()
        #
        self.pages.fileChanged.connect(self.draw)
        self.draw()

    def initUI(self):
        (self.x, self.y, self.f) = (0, 0, 1)
        #
        self.darkstyle = lambda opacity=None: """
                * { background-color: rgba( 34,  34,  34, """ + \
                    str(opacity if opacity is not None else self.pages.opacity) + """) }
                QPushButton  { color: rgba(238, 238, 238, 128); font-size: 24pt }
            """
        self.lightstyle = lambda opacity=None: """
                * { background-color: rgba(238, 238, 238, 255) }
                QPushButton  { color: rgba( 17,  17,  17, 128); font-size: 24pt }
            """
        self.updateStyle()
        #
        self.lbl = QLabel()
        self.lbl.setAlignment(Qt.AlignCenter)
        #
        self.btns = QHBoxLayout()
        # todo? home (<<<) & end (>>>) for first page/img and last page/img
        self.prevBtn = QPushButton("<")
        self.prevBtn.clicked.connect(lambda ev: self.toggleInvert())
        self.btns.addWidget(self.prevBtn)
        #
        self.invBtn = QPushButton("☯️")
        self.invBtn.clicked.connect(lambda ev: self.prev())
        self.btns.addWidget(self.invBtn)
        #
        self.nextBtn = QPushButton(">")
        self.nextBtn.clicked.connect(lambda ev: self.next())
        self.btns.addWidget(self.nextBtn)
        # TODO: try to focus nextBtn by default (instead of prevBtn); these two doesn't work:
        # self.btns.itemAt(self.btns.count() - 1).widget().setFocus()
        # self.nextBtn.setFocus()
        # TODO: try toolbar instead of this layout, or may a floating toolbar on dblclick?
        #
        self.box = QVBoxLayout()
        self.box.setSpacing(0)
        self.box.setContentsMargins(0,0,0,0)
        self.box.addWidget(self.lbl)
        # self.box.addLayout(self.btns)
        self.setLayout(self.box)

    def updateStyle(self):
        self.setStyleSheet(self.darkstyle() if self.pages.invert else self.lightstyle())

    def toggleTrim(self):   self.pages.toggleTrim();   self.draw()
    def toggleInvert(self): self.pages.toggleInvert(); self.draw(); self.updateStyle()

    def draw(self): self.setPage(self.pages.getPage(self.longdim()))
    def prev(self): self.setPage(self.pages.prev   (self.longdim()))
    def next(self): self.setPage(self.pages.next   (self.longdim()))

    def longdim(self): return max(self.lbl.height(), self.lbl.width())

    def setPage(self, pix):
        self.pix = pix
        (self.x, self.y, self.f) = (0, 0, 1)
        self.setTitle(self.pages.title)
        self.__redraw()
        self.pages.prefetch()

    # takes a QPixmap
    # returns 4 Nones if null image or the four corner pixels aren't the same color.
    # otherwise returns the QImage, the corner QColor, the width, and the height.
    def __getImageCornerColor(self, p):
        img = QImage(p)
        (w, h) = (img.width(), img.height())
        if w == 0: return (None,) * 4
        clr = img.pixelColor(0,0)
        if clr != img.pixelColor(  0, h-1): return (None,) * 4
        if clr != img.pixelColor(w-1, h-1): return (None,) * 4
        if clr != img.pixelColor(w-1,   0): return (None,) * 4
        return img, clr, w, h

    def __getBoundingRectRatio(self, p, vmargin=0, hmargin=0):
        (img, clr, w, h) = self.__getImageCornerColor(p)
        if img is None: return
        #
        def chk(lr_or_tb, default, range1, range2):
            ret = default
            if lr_or_tb == 'lr':  # left or right
                for i in range1:
                    if any(img.pixelColor(i,j) != clr for j in range2): break
                    else: ret = i
            else:
                for i in range1:
                    if any(img.pixelColor(j,i) != clr for j in range2): break
                    else: ret = i
            return ret
        #
        top    = chk('tb', -1, range(     h//2    ), range(w))
        bottom = chk('tb',  h, range(h-1, h//2, -1), range(w))
        left   = chk('lr', -1, range(     w//2    ), range(top+1, bottom))
        right  = chk('lr',  w, range(w-1, w//2, -1), range(top+1, bottom))
        #
        top    = max( top    - vmargin,  -1 )
        bottom = min( bottom + vmargin,   h )
        left   = max( left   - hmargin,  -1 )
        right  = min( right  + hmargin,   w )
        #
        X = (left   + 1)
        Y = (top    + 1)
        W = (right  - X)
        H = (bottom - Y)
        # return QPixmap(img.copy(X, Y, W, H))
        return tuple(e/w for e in (X, Y, W, H))

    def __redraw(self):
        lw = self.lbl.width()
        lh = self.lbl.height()
        #
        def scale(p, w, h):
            return p.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        #
        if self.pages.mode == 'Images':
            iw = min(10000, int(max(1, self.f) * lw))
            ih = min(10000, int(max(1, self.f) * lh))
            self.f = max(iw/lw, ih/lh)
            x = max(0, min(iw-lw, int(self.x * self.f)))
            y = max(0, min(ih-lh, int(self.y * self.f)))
            # https://forum.qt.io/topic/75233/fit-image-into-qlabel @md2012 with modifications
            self.lbl.setPixmap(scale(self.pix, iw, ih).copy(x, y, lw, lh))
        elif self.pages.mode == 'PDF':  # ASSUMPTION: no other trimming is applied/required!
            iw = self.pix.width()
            ih = self.pix.height()
            if self.pages.trim:
                small = scale(self.pix, iw//4, ih//4)
                params = self.__getBoundingRectRatio(small, vmargin=20, hmargin=10)
                if params:
                    params = tuple(int(e*iw) for e in params)
                    p = scale(self.pix.copy(*params), lw, lh)
            try: p
            except:
                p = scale(self.pix, lw, lh)
            if self.pages.invert and self.pages.opacity < 255:
                (img, clr, w, h) = self.__getImageCornerColor(p)
                if clr is not None:  # the corner pixels all are the same color
                    p.setMask(p.createHeuristicMask())
            self.lbl.setPixmap(p)

    def lessOpaque(self): self.pages.lessOpaque(); self.draw(); self.updateStyle()
    def moreOpaque(self): self.pages.moreOpaque(); self.draw(); self.updateStyle()

    def event(self, ev):
        if ev.type() == QEvent.Resize:
            self.pix = self.pages.getPage(self.longdim())
            self.__redraw()
        #
        elif ev.type() == QEvent.Gesture:
            pinch = ev.gesture(Qt.PinchGesture)
            swipe = ev.gesture(Qt.SwipeGesture)
            if pinch and self.pages.mode == 'Images' and not swipe:
                if pinch.state() == Qt.GestureStarted:
                    self.b = pinch.centerPoint()
                if pinch.state() == Qt.GestureUpdated:
                    (lw, lh) = (self.lbl.width(), self.lbl.height())
                    # zoom
                    scaleFactor = pinch.scaleFactor()
                    roundedScaleFactor = round(scaleFactor, 1)
                    self.f *= roundedScaleFactor
                    point = pinch.centerPoint()
                    oldpt = pinch.lastCenterPoint()
                    offset = point - pinch.lastCenterPoint()
                    pt = self.lbl.mapFromGlobal(QPoint(int(point.x()), int(point.y())))
                    ol = self.lbl.mapFromGlobal(QPoint(int(oldpt.x()), int(oldpt.y())))
                    self.x -= 0.5 * (pt.x() - ol.x())
                    self.y -= 0.5 * (pt.y() - ol.y())
                    self.__redraw()
            elif swipe and swipe.state() == Qt.GestureFinished:
                if   swipe.horizontalDirection() == QSwipeGesture.Right: self.prev()
                elif swipe.horizontalDirection() == QSwipeGesture.Left:  self.next()
        #
        elif ev.type() == QEvent.TouchEnd and self.pages.mode == 'PDF':
            point = ev.touchPoints()[0]
            d = point.startNormalizedPos().x() - point.normalizedPos().x()
            if d >  0.1: self.next()
            if d < -0.1: self.prev()
        return True


class Window(QMainWindow):

    def __init__(self, pages, toggleCursor):
        super().__init__()
        self.toggleCursor = toggleCursor
        setTitle = lambda t: self.setWindowTitle((t + ' - ' if t else '') + 'CuteView')
        self.b = TouchViewer(Pages(*pages), setTitle=setTitle)
        self.setCentralWidget(self.b)
        #
        # self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowState(Qt.WindowMaximized)
        # if maximized, must be AFTER setting the translucent background attributes!
        #
        self.show()

    def closeEvent(self, ev):
        self.b.writeHist()

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key_Q:
            if ev.modifiers() == Qt.ShiftModifier:
                self.closeEvent = lambda ev: None
            self.close()
        elif ev.key() == Qt.Key_Left:        self.b.prev()
        elif ev.key() == Qt.Key_Right:       self.b.next()
        elif ev.key() == Qt.Key_Asterisk:    self.b.lessOpaque()
        elif ev.key() == Qt.Key_Slash:       self.b.moreOpaque()
        # moreOpaque should be easier than lessOpaque; especially for desperate keyboard-mashing
        elif ev.key() == Qt.Key_AsciiCircum: self.toggleCursor()
        elif ev.key() == Qt.Key_I:           self.b.toggleInvert()
        elif ev.key() == Qt.Key_T:           self.b.toggleTrim()


app = QApplication(sys.argv)
pages = sys.argv[1:]

if not pages:
    imgexts = ' *.'+(' *.'.join(['png', 'jpg', 'gif', 'bmp', 'webp', 'svg', 'svgz']))
    pages = QFileDialog.getOpenFileNames(None, "Open Images or PDF files", "",
             ";;".join([
                 "All Supported Files (*.pdf " + imgexts + ")",
                 "Image Files (" + imgexts + ")",
                 "PDF Files (*.pdf)",
                 "All Files (*.*)",
             ])
         )[0]
    if not pages:  # cancelled
        sys.exit(0)

imgs = list(filter(lambda f: not f.lower().endswith('.pdf'), pages))
pdfs = list(filter(lambda f:     f.lower().endswith('.pdf'), pages))

if pdfs and not poppler:
    QMessageBox().critical(None, "poppler-tools not found",
           "The package 'poppler-tools' is required for viewing PDF files, but it is not found.")
    pdfs = []
    if not imgs:
        sys.exit(1)


# based with mods on answer by shungo on
# https://forum.qt.io/topic/28703/how-to-hide-the-cursor-in-qt5
def hideCursor():
    QApplication.setOverrideCursor(Qt.BlankCursor)
    QApplication.changeOverrideCursor(Qt.BlankCursor)
def showCursor():
    QApplication.setOverrideCursor(QCursor())
    QApplication.changeOverrideCursor(QCursor())

__cursorHidden = False
def toggleCursor():
    global __cursorHidden
    showCursor() if __cursorHidden else hideCursor()
    __cursorHidden = not __cursorHidden

toggleCursor()  # TODO: make it only hide after a timeout of inactivity


w = []

if imgs:
    w.append(Window(imgs, toggleCursor))

for pdf in pdfs:
    w.append(Window([pdf], toggleCursor))

app.exit(app.exec())
