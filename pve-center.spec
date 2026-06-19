%global pypi_name pvecenter

Name:          pve-center
Version:       1.1.0
Release:       1%{?dist}
Summary:       Desktop client for Proxmox VE clusters

License:       GPLv3
URL:           https://github.com/mcluremail/pvecenter
Source0:       %{pypi_source}

BuildArch:     noarch
BuildRequires: python3-devel
BuildRequires: python3-setuptools

Requires:      python3
Requires:      python3-pyside6
Requires:      python3-requests
Requires:      python3-pyqtgraph
Requires:      python3-cryptography

Recommends:    virt-viewer

%description
PVE Center — desktop client for Proxmox VE cluster monitoring and management.

%prep
%autosetup -n %{pypi_name}-%{version}

%build
%py3_build

%install
%py3_install
install -m 644 -D debian/pve-center.desktop \
  %{buildroot}%{_datadir}/applications/pve-center.desktop

%files
%{python3_sitelib}/pve_center/
%{python3_sitelib}/pvecenter-*.egg-info/
%{_bindir}/pvecenter
%{_datadir}/applications/pve-center.desktop

%changelog
* Fri Jun 19 2026 Taurus McLure <taurus@mclure.ru> - 1.1.0-1
- S3: decompose detail_panel.py (2509 lines) into detail_panel/ package with 7 modules.
- Tab construction and populate logic extracted into _host_tabs.py, _storage_tabs.py, _vm_tabs.py.
- Static helpers extracted into _table_utils.py, worker management into _worker_manager.py.
- Constants and TabIndex enum in _constants.py. DetailPanel is now a thin coordinator (~300 lines).

* Fri Jun 19 2026 Taurus McLure <taurus@mclure.ru> - 1.0.4-1
- Race condition fixes (R1/R2/R3): copy lists before iteration, atomic generation guard in soft_refresh.
- M7: remove duplicate setStyleSheet/setDefaultAlignment calls on datacenter_summary.
- Add missing 'Force stop' translations to ru.json.
- seed_translations: forced re-seed when i18n version changes.

* Fri Jun 19 2026 Taurus McLure <taurus@mclure.ru> - 1.0.3-1
- Move i18n translations from inline Python dicts to external JSON files.

* Sun Jun 07 2026 Taurus McLure <taurus@mclure.ru> - 0.1.2-1
- Clean release without diagnostic logging.

* Sun Jun 07 2026 Taurus McLure <taurus@mclure.ru> - 0.1.1-1
- First public release.