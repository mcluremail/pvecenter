"""Access control workers: users, tokens, groups, roles, ACLs."""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from ..plugins import create_provider
from ..ui.i18n import tr
from .core import _safe_emit, _sanitize_error

logger = logging.getLogger(__name__)

class AccessUsersSignals(QObject):
    users_ready = Signal(list)
    users_error = Signal(str)
    finished = Signal()
class AccessUsersWorker(QRunnable):
    """Fetch all users with token info (full=1)."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessUsersSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.list_users()
            _safe_emit(self.signals.users_ready, data)
        except Exception as e:
            logger.debug("access users error: %s", e)
            _safe_emit(self.signals.users_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessUserCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessUserCreateWorker(QRunnable):
    """Create a new PVE user."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessUserCreateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.create_user(**self.params)
            _safe_emit(self.signals.result, tr("User created"))
        except Exception as e:
            logger.debug("user create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessUserUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessUserUpdateWorker(QRunnable):
    """Update an existing PVE user."""

    def __init__(self, host_cfg, userid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.params = params
        self.signals = AccessUserUpdateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.update_user(self.userid, **self.params)
            _safe_emit(self.signals.result, tr("User updated"))
        except Exception as e:
            logger.debug("user update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessUserDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessUserDeleteWorker(QRunnable):
    """Delete a PVE user."""

    def __init__(self, host_cfg, userid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.signals = AccessUserDeleteSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.delete_user(self.userid)
            _safe_emit(self.signals.result, tr("User deleted"))
        except Exception as e:
            logger.debug("user delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Access Management — API Tokens
# ----------------------------------------------------------------------
class AccessTokensSignals(QObject):
    tokens_ready = Signal(list)
    tokens_error = Signal(str)
    finished = Signal()
class AccessTokensWorker(QRunnable):
    """Fetch API tokens for a user."""

    def __init__(self, host_cfg, userid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.signals = AccessTokensSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.list_tokens(self.userid)
            _safe_emit(self.signals.tokens_ready, data)
        except Exception as e:
            logger.debug("access tokens error: %s", e)
            _safe_emit(self.signals.tokens_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessTokenCreateSignals(QObject):
    result = Signal(str, str, str)
    error = Signal(str)
    finished = Signal()
class AccessTokenCreateWorker(QRunnable):
    """Create an API token. Returns (msg, full_tokenid, value)."""

    def __init__(self, host_cfg, userid, tokenid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.params = params
        self.signals = AccessTokenCreateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.create_token(self.userid, self.tokenid, **self.params)
            full = data.get("full-tokenid", "")
            value = data.get("value", "")
            _safe_emit(self.signals.result, tr("Token created"), full, value)
        except Exception as e:
            logger.debug("token create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessTokenUpdateSignals(QObject):
    result = Signal(str, str, str)
    error = Signal(str)
    finished = Signal()
class AccessTokenUpdateWorker(QRunnable):
    """Update an API token. If regenerate=1, returns (msg, full_tokenid, value)."""

    def __init__(self, host_cfg, userid, tokenid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.params = params
        self.signals = AccessTokenUpdateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.update_token(self.userid, self.tokenid, **self.params)
            full = (data or {}).get("full-tokenid", "")
            value = (data or {}).get("value", "")
            _safe_emit(self.signals.result, tr("Token updated"), full, value)
        except Exception as e:
            logger.debug("token update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessTokenDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessTokenDeleteWorker(QRunnable):
    """Delete an API token."""

    def __init__(self, host_cfg, userid, tokenid):
        super().__init__()
        self.host_cfg = host_cfg
        self.userid = userid
        self.tokenid = tokenid
        self.signals = AccessTokenDeleteSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.delete_token(self.userid, self.tokenid)
            _safe_emit(self.signals.result, tr("Token deleted"))
        except Exception as e:
            logger.debug("token delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Access Management — Groups
# ----------------------------------------------------------------------
class AccessGroupsSignals(QObject):
    groups_ready = Signal(list)
    groups_error = Signal(str)
    finished = Signal()
class AccessGroupsWorker(QRunnable):
    """Fetch all user groups."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessGroupsSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.list_groups()
            _safe_emit(self.signals.groups_ready, data)
        except Exception as e:
            logger.debug("access groups error: %s", e)
            _safe_emit(self.signals.groups_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessGroupCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessGroupCreateWorker(QRunnable):
    """Create a new user group."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessGroupCreateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.create_group(**self.params)
            _safe_emit(self.signals.result, tr("Group created"))
        except Exception as e:
            logger.debug("group create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessGroupUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessGroupUpdateWorker(QRunnable):
    """Update a user group."""

    def __init__(self, host_cfg, groupid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.groupid = groupid
        self.params = params
        self.signals = AccessGroupUpdateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.update_group(self.groupid, **self.params)
            _safe_emit(self.signals.result, tr("Group updated"))
        except Exception as e:
            logger.debug("group update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessGroupDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessGroupDeleteWorker(QRunnable):
    """Delete a user group."""

    def __init__(self, host_cfg, groupid):
        super().__init__()
        self.host_cfg = host_cfg
        self.groupid = groupid
        self.signals = AccessGroupDeleteSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.delete_group(self.groupid)
            _safe_emit(self.signals.result, tr("Group deleted"))
        except Exception as e:
            logger.debug("group delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Access Management — Roles
# ----------------------------------------------------------------------
class AccessRolesSignals(QObject):
    roles_ready = Signal(list)
    roles_error = Signal(str)
    finished = Signal()
class AccessRolesWorker(QRunnable):
    """Fetch all roles."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessRolesSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.list_roles()
            _safe_emit(self.signals.roles_ready, data)
        except Exception as e:
            logger.debug("access roles error: %s", e)
            _safe_emit(self.signals.roles_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessRoleCreateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessRoleCreateWorker(QRunnable):
    """Create a new role."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessRoleCreateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.create_role(**self.params)
            _safe_emit(self.signals.result, tr("Role created"))
        except Exception as e:
            logger.debug("role create error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessRoleUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessRoleUpdateWorker(QRunnable):
    """Update a role's privileges."""

    def __init__(self, host_cfg, roleid, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.roleid = roleid
        self.params = params
        self.signals = AccessRoleUpdateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.update_role(self.roleid, **self.params)
            _safe_emit(self.signals.result, tr("Role updated"))
        except Exception as e:
            logger.debug("role update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessRoleDeleteSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessRoleDeleteWorker(QRunnable):
    """Delete a role."""

    def __init__(self, host_cfg, roleid):
        super().__init__()
        self.host_cfg = host_cfg
        self.roleid = roleid
        self.signals = AccessRoleDeleteSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.delete_role(self.roleid)
            _safe_emit(self.signals.result, tr("Role deleted"))
        except Exception as e:
            logger.debug("role delete error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# Access Management — ACL / Permissions
# ----------------------------------------------------------------------
class AccessAclSignals(QObject):
    acl_ready = Signal(list)
    acl_error = Signal(str)
    finished = Signal()
class AccessAclWorker(QRunnable):
    """Fetch ACL entries."""

    def __init__(self, host_cfg):
        super().__init__()
        self.host_cfg = host_cfg
        self.signals = AccessAclSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            data = access_api.list_acl()
            _safe_emit(self.signals.acl_ready, data)
        except Exception as e:
            logger.debug("access acl error: %s", e)
            _safe_emit(self.signals.acl_error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)
class AccessAclUpdateSignals(QObject):
    result = Signal(str)
    error = Signal(str)
    finished = Signal()
class AccessAclUpdateWorker(QRunnable):
    """Add or remove ACL permissions."""

    def __init__(self, host_cfg, params):
        super().__init__()
        self.host_cfg = host_cfg
        self.params = params
        self.signals = AccessAclUpdateSignals()

    def run(self):
        provider = None
        try:
            provider = create_provider(self.host_cfg, timeout=15)
            access_api = provider.access
            access_api.update_acl(**self.params)
            is_delete = int(self.params.get("delete", 0) or 0)
            msg = tr("Permissions removed") if is_delete else tr("Permissions added")
            _safe_emit(self.signals.result, msg)
        except Exception as e:
            logger.debug("acl update error: %s", e)
            _safe_emit(self.signals.error, _sanitize_error(e))
        finally:
            if provider:
                provider.close()
            _safe_emit(self.signals.finished)

# ----------------------------------------------------------------------
# VersionCheckWorker — check GitHub releases for newer versions
# ----------------------------------------------------------------------
