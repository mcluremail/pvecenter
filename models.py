from dataclasses import dataclass
from typing import List, Optional

@dataclass
class NodeData:
    name: str
    status: str
    cpu: float = 0.0
    mem: int = 0
    uptime: int = 0
    host_name: str = ""

@dataclass
class VmData:
    vmid: int
    name: str
    type: str  # "qemu" или "lxc"
    status: str
    cpu: float = 0.0
    maxmem: int = 0
    maxdisk: int = 0
    uptime: int = 0
    node: str = ""
    host_name: str = ""

@dataclass
class GroupInfo:
    name: str
    hosts: List[str]
    vm_count: int = 0
