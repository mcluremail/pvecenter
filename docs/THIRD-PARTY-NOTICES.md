# Third-party software notices

This project is licensed under the GNU General Public License v3.0
(see the `LICENSE` file). It bundles and depends on the third-party
software listed below. Each component remains under its own license.

## Bundled software

### noVNC (vendored)

- Source: https://github.com/novnc/noVNC
- Files: `pve_center/ui/console/novnc/`
- License: Mozilla Public License 2.0 (MPL-2.0) for the core library
  (`novnc/core/**/*.js`); see `pve_center/ui/console/novnc/LICENSE.txt`
  for the full text and per-file exceptions.
- Modifications: none — the vendored files are used as-is.
- Note: MPL-2.0 is compatible with GPL-3.0. The MPL-2.0 files remain
  under MPL-2.0; their sources are provided in this repository.

### pako (vendored inside noVNC)

- Source: https://github.com/nodeca/pako
- Files: `pve_center/ui/console/novnc/vendor/pako/`
- License: MIT.

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
