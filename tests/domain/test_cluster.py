"""Tests for ClusterInfo and ClusterNode domain models."""

from __future__ import annotations

from pve_center.domain import ClusterInfo, ClusterNode, ClusterStatus, QuorumState

CLUSTER_ENTRY = {
    "type": "cluster",
    "quorate": 1,
    "votes": 3,
    "expected_votes": 3,
}

CLUSTER_ENTRY_LOST = {
    "type": "cluster",
    "quorate": 0,
    "votes": 1,
    "expected_votes": 3,
}

NODE_STATUS_ENTRY = {
    "type": "node",
    "name": "pve01",
    "online": 1,
    "quorum_votes": 1,
    "ip": "10.0.0.1",
}

COROSYNC_ENTRY = {
    "name": "pve01",
    "ring0_addr": "10.0.0.1",
    "ring1_addr": "10.0.0.2",
    "quorum_votes": 1,
    "nodeid": 1,
}


class TestClusterInfoFromPve:
    def test_quorate(self):
        ci = ClusterInfo.from_pve(CLUSTER_ENTRY)
        assert ci.quorum_state is QuorumState.OK
        assert ci.votes == 3
        assert ci.expected_votes == 3

    def test_not_quorate(self):
        ci = ClusterInfo.from_pve(CLUSTER_ENTRY_LOST)
        assert ci.quorum_state is QuorumState.LOST
        assert ci.votes == 1

    def test_missing_quorate(self):
        ci = ClusterInfo.from_pve({"votes": 2, "expected_votes": 3})
        assert ci.quorum_state is QuorumState.UNKNOWN

    def test_empty(self):
        ci = ClusterInfo.from_pve({})
        assert ci.quorum_state is QuorumState.UNKNOWN
        assert ci.votes == 0


class TestClusterNodeFromPve:
    def test_with_corosync(self):
        cn = ClusterNode.from_pve(NODE_STATUS_ENTRY, COROSYNC_ENTRY)
        assert cn.name == "pve01"
        assert cn.online is True
        assert cn.quorum_votes == 1
        assert cn.ip == "10.0.0.1"
        assert cn.ring0_addr == "10.0.0.1"
        assert cn.ring1_addr == "10.0.0.2"
        assert cn.nodeid == 1

    def test_without_corosync(self):
        cn = ClusterNode.from_pve(NODE_STATUS_ENTRY, None)
        assert cn.ring0_addr == ""
        assert cn.ring1_addr == ""
        assert cn.nodeid == ""

    def test_ring0_display_fallback(self):
        cn = ClusterNode.from_pve(NODE_STATUS_ENTRY, None)
        assert cn.ring0_display == "10.0.0.1"

    def test_ring0_display_from_corosync(self):
        cn = ClusterNode.from_pve(NODE_STATUS_ENTRY, {"ring0_addr": "192.168.1.1"})
        assert cn.ring0_display == "192.168.1.1"

    def test_votes_display(self):
        cn = ClusterNode.from_pve(NODE_STATUS_ENTRY, None)
        assert cn.votes_display == "1"

    def test_votes_display_zero(self):
        cn = ClusterNode.from_pve({"name": "x", "quorum_votes": 0}, None)
        assert cn.votes_display == ""

    def test_offline_node(self):
        cn = ClusterNode.from_pve({"name": "pve03", "online": 0}, None)
        assert cn.online is False


class TestClusterStatusFromPve:
    """ClusterStatus container merges /cluster/status + corosync nodes."""

    def test_full_merge(self):
        status_list = [CLUSTER_ENTRY, NODE_STATUS_ENTRY]
        cs = ClusterStatus.from_pve(status_list, [COROSYNC_ENTRY])
        assert cs.info.quorum_state == QuorumState.OK
        assert cs.info.votes == 3
        assert cs.info.expected_votes == 3
        assert len(cs.nodes) == 1
        node = cs.nodes[0]
        assert node.name == "pve01"
        assert node.online is True
        assert node.ring0_display == "10.0.0.1"
        assert node.ring1_addr == "10.0.0.2"
        assert node.nodeid == 1

    def test_no_cluster_entry(self):
        cs = ClusterStatus.from_pve([], [])
        assert cs.info.quorum_state == QuorumState.UNKNOWN
        assert cs.nodes == ()

    def test_node_without_corosync_entry(self):
        cs = ClusterStatus.from_pve([NODE_STATUS_ENTRY], [])
        node = cs.nodes[0]
        assert node.ring0_display == NODE_STATUS_ENTRY["ip"]  # IP fallback
        assert node.ring1_addr == ""

    def test_quorum_lost(self):
        cs = ClusterStatus.from_pve([CLUSTER_ENTRY_LOST], [])
        assert cs.info.quorum_state == QuorumState.LOST
