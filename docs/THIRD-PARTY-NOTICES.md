# Third-party software notices

This project is licensed under the GNU General Public License v3.0
(see the `LICENSE` file). It bundles and depends on the third-party
software listed below. Each component remains under its own license.

## Bundled software

### noVNC (vendored)

- Source: https://github.com/novnc/noVNC
- Files: `virtdeck/ui/console/novnc/`
- License: Mozilla Public License 2.0 (MPL-2.0) for the core library
  (`novnc/core/**/*.js`); see `virtdeck/ui/console/novnc/LICENSE.txt`
  for the full text and per-file exceptions.
- Modifications: none — the vendored files are used as-is.
- Note: MPL-2.0 is compatible with GPL-3.0. The MPL-2.0 files remain
  under MPL-2.0; their sources are provided in this repository.

### pako (vendored inside noVNC)

- Source: https://github.com/nodeca/pako
- Files: `virtdeck/ui/console/novnc/vendor/pako/`
- License: MIT.

## Design references

### KDE color schemes (Breeze, Oxygen)

- Sources:
  https://invent.kde.org/plasma/breeze (colors/BreezeLight.colors,
  colors/BreezeDark.colors, LGPL-2.0-or-later) and
  https://invent.kde.org/plasma/oxygen (color-schemes/Oxygen.colors).
- What is used: individual color values (hex constants) as reference
  data for the built-in theme plugins in `virtdeck/plugins/_themes.py`.
  No KDE files are vendored or redistributed with this project.
- The SVG icons shipped with VirtDeck (including the Breeze-style
  24px set) are original works drawn for this project; no icon path
  data from breeze-icons (LGPL-2.1) or any other icon set is copied.

## Trademark notice

VirtDeck is an unofficial third-party client. It is not affiliated
with, endorsed by, or sponsored by Proxmox Server Solutions GmbH
("Proxmox" and "Proxmox VE" are trademarks of Proxmox Server Solutions
GmbH) or KDE e.V. The Proxmox name is used solely to describe
compatibility ("desktop client for Proxmox VE"); no Proxmox or KDE
artwork is used in this project.

## Python runtime dependencies

| Package      | License                    | Homepage                                    | Used for                            |
|--------------|----------------------------|---------------------------------------------|-------------------------------------|
| PySide6      | LGPL-3.0-only              | https://wiki.qt.io/Qt_for_Python            | Qt GUI (widgets, QtWebEngine)       |
| proxmoxer    | MIT                        | https://github.com/proxmoxer/proxmoxer      | Proxmox VE API client               |
| requests     | Apache-2.0                 | https://github.com/psf/requests             | HTTP client                         |
| urllib3      | MIT                        | https://github.com/urllib3/urllib3          | HTTP transport                      |
| pyqtgraph    | MIT                        | https://github.com/pyqtgraph/pyqtgraph      | Charts                              |
| cryptography | Apache-2.0 OR BSD-3-Clause | https://github.com/pyca/cryptography        | TLS/keys, credential storage crypto |
| keyring      | MIT                        | https://github.com/jaraco/keyring           | OS credential storage (tokens)      |
| websockets   | BSD-3-Clause               | https://github.com/python-websockets/websockets | noVNC websocket bridge (optional extra) |
