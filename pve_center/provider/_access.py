"""AccessAPI — access management PVE endpoints.

Covers: /access/users, /access/users/{userid}/token,
/access/groups, /access/roles, /access/acl.
"""

from __future__ import annotations

from ._session import ProxmoxSession, _q


class AccessAPI:
    """Access management PVE API methods."""

    def __init__(self, session: ProxmoxSession) -> None:
        self._s = session

    # -- users --

    def list_users(self, full: bool = True) -> list[dict]:
        """GET /access/users."""
        params = {"full": 1} if full else {}
        return self._s.call(self._s.proxmox.access.users.get, **params)

    def create_user(self, **params) -> object:
        """POST /access/users."""
        return self._s.call(self._s.proxmox.access.users.post, **params)

    def update_user(self, userid: str, **params) -> object:
        """PUT /access/users/{userid}."""
        return self._s.call(self._s.proxmox.access.users(_q(userid)).put, **params)

    def delete_user(self, userid: str) -> object:
        """DELETE /access/users/{userid}."""
        return self._s.call(self._s.proxmox.access.users(_q(userid)).delete)

    # -- tokens --

    def list_tokens(self, userid: str) -> list[dict]:
        """GET /access/users/{userid}/token."""
        return self._s.call(self._s.proxmox.access.users(_q(userid)).token.get)

    def create_token(self, userid: str, tokenid: str, **params) -> dict:
        """POST /access/users/{userid}/token/{tokenid}."""
        return self._s.call(
            self._s.proxmox.access.users(_q(userid)).token(_q(tokenid)).post, **params
        )

    def update_token(self, userid: str, tokenid: str, **params) -> dict:
        """PUT /access/users/{userid}/token/{tokenid}."""
        return self._s.call(
            self._s.proxmox.access.users(_q(userid)).token(_q(tokenid)).put, **params
        )

    def delete_token(self, userid: str, tokenid: str) -> object:
        """DELETE /access/users/{userid}/token/{tokenid}."""
        return self._s.call(
            self._s.proxmox.access.users(_q(userid)).token(_q(tokenid)).delete
        )

    # -- groups --

    def list_groups(self) -> list[dict]:
        """GET /access/groups."""
        return self._s.call(self._s.proxmox.access.groups.get)

    def create_group(self, **params) -> object:
        """POST /access/groups."""
        return self._s.call(self._s.proxmox.access.groups.post, **params)

    def update_group(self, groupid: str, **params) -> object:
        """PUT /access/groups/{groupid}."""
        return self._s.call(self._s.proxmox.access.groups(_q(groupid)).put, **params)

    def delete_group(self, groupid: str) -> object:
        """DELETE /access/groups/{groupid}."""
        return self._s.call(self._s.proxmox.access.groups(_q(groupid)).delete)

    # -- roles --

    def list_roles(self) -> list[dict]:
        """GET /access/roles."""
        return self._s.call(self._s.proxmox.access.roles.get)

    def create_role(self, **params) -> object:
        """POST /access/roles."""
        return self._s.call(self._s.proxmox.access.roles.post, **params)

    def update_role(self, roleid: str, **params) -> object:
        """PUT /access/roles/{roleid}."""
        return self._s.call(self._s.proxmox.access.roles(_q(roleid)).put, **params)

    def delete_role(self, roleid: str) -> object:
        """DELETE /access/roles/{roleid}."""
        return self._s.call(self._s.proxmox.access.roles(_q(roleid)).delete)

    # -- ACL --

    def list_acl(self) -> list[dict]:
        """GET /access/acl."""
        return self._s.call(self._s.proxmox.access.acl.get)

    def update_acl(self, **params) -> object:
        """PUT /access/acl — add or remove permissions."""
        return self._s.call(self._s.proxmox.access.acl.put, **params)
