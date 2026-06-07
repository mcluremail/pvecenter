%global pypi_name pvecenter

Name:          pve-center
Version:       0.1.1
Release:       1%{?dist}
Summary:       Десктопная панель управления Proxmox VE

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
%py3_install
# desktop entry
mkdir -p %{buildroot}%{_datadir}/applications/
install -m 644 %{_builddir}/%{pypi_name}-%{version}/debian/pve-center.desktop \
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
