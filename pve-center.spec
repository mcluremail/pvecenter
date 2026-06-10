%global pypi_name pvecenter

Name:          pve-center
Version:       1.0.0
Release:       1%{?dist}
Summary:       Desktop client for Proxmox VE clusters

License:       GPLv3
URL:           https://github.com/mcluremail/pvecenter
Source0:       %{pypi_source}

BuildArch:     noarch
BuildRequires: python3-devel
BuildRequires: python3-setuptools

Requires:      python3

Requires:      python3
Requires:      python3-pyside6
Requires:      python3-requests
Requires:      python3-pyqtgraph
Requires:      python3-cryptography

Recommends:    virt-viewer

%description
PVE Center — десктопный инструмент для мониторинга и управления
кластерами Proxmox VE. Работает через официальный API PVE.

Возможности:
  * Мониторинг: статус нод, ВМ/контейнеров, ЦП, память, диски, сеть
  * Управление: power actions, SPICE консоль
  * Аудит: лента задач с читаемыми описаниями
  * Безопасность: user-bound API-токены, шифрование конфига

%prep
%autosetup -n %{pypi_name}-%{version}

%build
%py3_build

%install
# manual install (setup.py install is deprecated in modern setuptools)
install -d %{buildroot}%{python3_sitelib}/pve_center/
cp -a pve_center/ %{buildroot}%{python3_sitelib}/
install -d %{buildroot}%{python3_sitelib}/pvecenter-%{version}.dist-info/
cat > %{buildroot}%{python3_sitelib}/pvecenter-%{version}.dist-info/METADATA << EOF
Name: pvecenter
Version: %{version}
Summary: Desktop client for Proxmox VE clusters
EOF
# entry point
install -d %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/pvecenter << 'SCRIPT'
#!/usr/bin/env python3
from pve_center.main import main
main()
SCRIPT
chmod 755 %{buildroot}%{_bindir}/pvecenter
# desktop entry
mkdir -p %{buildroot}%{_datadir}/applications/
install -m 644 debian/pve-center.desktop \
  %{buildroot}%{_datadir}/applications/pve-center.desktop

%files
%{python3_sitelib}/pve_center/
%{python3_sitelib}/pve_center-*.egg-info/
%{_bindir}/pvecenter
%{_datadir}/applications/pve-center.desktop

%changelog
* Sun Jun 07 2026 Taurus McLure <taurus@mclure.ru> - 0.1.2-1
- Clean release without diagnostic logging.

* Sun Jun 07 2026 Taurus McLure <taurus@mclure.ru> - 0.1.1-1
- Первый публичный релиз.
