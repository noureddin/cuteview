# CuteView

Touch-friendly, distraction-free, PDF reader and image viewer for desktop.

- Both PDF Reader and Image Viewer.
- Both Touch-friendly and Keyboard-driven.
- Distraction-free and minimal UI.
- Dark mode (invert color and grayscale).
- Auto-reloading on file changes.
- Automatic margin trimming (auto-crop).
- Transparency.
- Remembers the last opened page and other preferences (dark mode, auto-crop, transparency) per PDF file.

Written in Python 3 using Qt 5 (PyQt5).

It can read practically any image format, thanks to Qt.

It uses `mutool` (from `mupdf-tools`) or `pdftoppm` (from `poppler-utils`) to render the PDF.

The system package `poppler-utils` is the only hard dependency (after Python&nbsp;3 and `PyQt5`).  
It's recommended to have `mupdf-tools` too.

To read a PDF file, launch it with exactly one file,
where that file has the extension 'pdf' (case-insensitively).

To view images, launch it with one or more image files.

You can launch it from the GUI or CLI.


## Installation

1. Install the dependencies; they are: `python3`, `poppler-utils`, `PyQt5` (from PyPI),
    and optionally but recommended `mupdf-tools`.

    On a Debian or Ubuntu system, they are installed with:

    ```
    sudo apt install python3-pip poppler-utils mupdf-tools
    ```

    Then

    ```
    python3 -m pip install --user --upgrade pip
    python3 -m pip install --user --upgrade PyQt5
    ```

2. Install CuteView:

    If you want to install to the user only (no root needed):

    ```
    mkdir -p ~/.local/bin
    wget -O ~/.local/bin/cuteview https://raw.githubusercontent.com/noureddin/cuteview/main/cuteview.py
    chmod u+x ~/.local/bin/cuteview
    ```

3. Install the menu entry and GUI launcher:

    ```
    mkdir -p ~/.local/share/applications
    wget -O ~/.local/share/applications/cuteview.desktop https://raw.githubusercontent.com/noureddin/cuteview/main/cuteview.desktop
    chmod u+x ~/.local/share/applications/cuteview.desktop
    ```


## Touch Interface

Both (PDF and Images) modes:

- Three-finger swipe from right to left: next page.
- Three-finger swipe from left to right: previous page.

PDF mode only:

- Single-finger swipe from right to left: next page.
- Single-finger swipe from left to right: previous page.

Images mode only:

- Two-finger Pinch Gesture to zoom and pan.


## Keyboard Interface

- `q`: exit
- Shift+`Q`: exit without saving the position and preferences for the current PDF file.
- `i`: toggle dark mode (grayscale + invert)
- `t`: toggle automatic margin trimming (auto-crop)
- `*`: increase transparency (make the window and page less opaque)
- `/`: decrease transparency (make the window and page more opaque)
- `^`: toggle showing/hiding of the cursor (by default it's hidden)
- Right Arrow: next page or image
- Left Arrow: previous page or image


## Roadmap

### Currently work-in-progress

- Make the two-finger panning/zooming gesture behave naturally, more like Gwenview.
- Show an open dialog if launched without arguments.

### To-do in the near future

- Simplify the installation procedure. Maybe introduce an installation script instead?
- Show a "floating toolbar" (like context menu but grid) on double-tapping, to adjust transparency, dark mode, auto-cropping, etc.
- Switch to PyMuPDF, instead of using system-installed tools.
- Launch a window for every PDF given in the arguments, and remove them from the argument list;
  e.g., if launched with four PDF files and a number of images, fives windows would be launched: one for each PDF, and one for the images.

### Maybe do

- Move to previous/next image with the (two-finger) panning gesture, if it goes far enough outside the image to the left/right.
- Switch to PySimpleGUI.
- When exactly one file is given as argument, and that file is an image, load all the image files in the same directory (without looking into sub-directories).

## License

Apache License, Version 2.

Copyright 2021 Noureddin.
