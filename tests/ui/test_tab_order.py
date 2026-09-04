"""Tab order invariant: TabIndex values must match the real addTab order.

v2.11.2 inserted TabIndex.STORAGE_MONITORING = 10 and shifted every
later tab by +1. If the addTab sequence in DetailPanel._build_tabs ever
drifts from the enum, the UI shows the wrong widget under each label.
"""
import pytest

from pve_center.ui.detail_panel import DetailPanel
from pve_center.ui.detail_panel._constants import TabIndex

EXPECTED_LABELS = {
    TabIndex.MONITOR: "Monitoring",
    TabIndex.HARDWARE: "Hardware",
    TabIndex.OPTIONS: "Options",
    TabIndex.HISTORY: "History",
    TabIndex.SUMMARY: "Summary",
    TabIndex.HOST_VMS: "Virtual Machines",
    TabIndex.POOL_VMS: "Pool VMs",
    TabIndex.STORAGES: "Storage",
    TabIndex.HOST_STORAGE: "Storage",
    TabIndex.STORAGE_DETAIL: "Storage Detail",
    TabIndex.STORAGE_MONITORING: "Monitoring",
    TabIndex.BACKUPS: "Backups",
    TabIndex.DISKS_VM: "VM Disks",
    TabIndex.ISO: "ISO",
    TabIndex.TEMPLATES: "Templates",
    TabIndex.NETWORK: "Network",
    TabIndex.SERVICES: "Services",
    TabIndex.HOST_DISKS: "Disks",
    TabIndex.SNAPSHOTS: "Snapshots",
    TabIndex.HEALTH: "Health",
    TabIndex.VM_SNAPSHOTS: "Snapshots",
    TabIndex.VM_BACKUP: "Backup",
    TabIndex.BACKUP_JOBS: "Backup Jobs",
    TabIndex.ACCESS: "Access",
    TabIndex.HA: "HA",
}


@pytest.fixture
def panel(qtbot):
    p = DetailPanel([])
    qtbot.addWidget(p)
    return p


class TestTabIndexMatchesTabs:
    def test_tab_count(self, panel):
        assert panel.tabs.count() == len(EXPECTED_LABELS)

    @pytest.mark.parametrize(
        "tab_index,label",
        sorted(EXPECTED_LABELS.items(), key=lambda kv: int(kv[0])),
        ids=lambda v: v if isinstance(v, str) else int(v),
    )
    def test_label_at_index(self, panel, tab_index, label):
        assert panel.tabs.tabText(int(tab_index)) == label
