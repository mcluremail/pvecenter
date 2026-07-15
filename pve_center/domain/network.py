"""Domain model: NetworkInterface (PVE host network interface)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NetworkInterface:
    """A PVE host network interface (eth, bridge, vlan, bond, ...)."""

    iface: str
    """Interface name, e.g. 'eth0', 'vmbr0'."""

    iface_type: str
    """Interface type: 'eth', 'bridge', 'vlan', 'bond', etc."""

    active: bool
    """Whether the interface is currently up."""

    method: str
    """IP method: 'static', 'dhcp', 'manual'."""

    address: str
    """IP address."""

    netmask: str
    """Netmask."""

    gateway: str
    """Default gateway IP."""

    bridge_ports: str
    """Comma-separated bridge member interfaces."""

    vlan_id: str
    """VLAN ID (raw PVE field name 'vlan_id')."""

    mtu: str
    """MTU value (PVE returns this as int or string)."""

    pending: bool
    """Whether there are unapplied (pending) changes."""

    autostart: bool
    """Whether the interface starts on boot."""

    @property
    def addr_str(self) -> str:
        """Formatted address: 'address/netmask' or 'address' or ''."""
        if self.address and self.netmask:
            return f"{self.address}/{self.netmask}"
        if self.address:
            return self.address
        return ""

    @property
    def bridge_port_list(self) -> list[str]:
        """Bridge ports as a list of stripped strings."""
        if not self.bridge_ports:
            return []
        return [p.strip() for p in self.bridge_ports.split(",") if p.strip()]

    @staticmethod
    def from_pve(d: dict) -> NetworkInterface:
        """Build a NetworkInterface from a raw PVE API dict."""
        return NetworkInterface(
            iface=d.get("iface", "") or "",
            iface_type=d.get("type", "") or "",
            active=bool(d.get("active")),
            method=d.get("method", "") or "",
            address=d.get("address", "") or "",
            netmask=d.get("netmask", "") or "",
            gateway=d.get("gateway", "") or "",
            bridge_ports=d.get("bridge_ports", "") or "",
            vlan_id=str(d.get("vlan_id", "") or ""),
            mtu=str(d.get("mtu", "") or ""),
            pending=bool(d.get("pending")),
            autostart=bool(d.get("autostart")),
        )
