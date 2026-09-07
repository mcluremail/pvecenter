"""Tests for pve_center.pbs.client — ticket auth, endpoints, error paths."""
from __future__ import annotations

import pytest

from pve_center.pbs.client import PBS_PORT, PbsClient, PbsError

_CFG = {
    "name": "pbs1", "type": "pbs", "host": "pbs.local",
    "port": 8007, "user": "root@pam", "token_value": "secret",
}


class FakeResponse:
    def __init__(self, status_code=200, data=None, errors=None, raw=None):
        self.status_code = status_code
        self._data = data
        self._errors = errors
        self._raw = raw

    def json(self):
        if self._raw is not None:
            raise ValueError("no json")
        body = {}
        if self._data is not None:
            body["data"] = self._data
        if self._errors is not None:
            body["errors"] = self._errors
        return body


class FakeSession:
    """Scripted requests.Session replacement."""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.verify = True
        self.calls = []  # (method, url, kwargs)

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


def make_client(session, cfg=None):
    c = PbsClient(cfg or _CFG)
    c._http = session
    return c


def ticket_response():
    return FakeResponse(200, data={
        "ticket": "TICKET", "CSRFPreventionToken": "CSRF",
    })


class TestAuth:
    def test_login_success(self):
        s = FakeSession([ticket_response()])
        c = make_client(s)
        c.login()
        method, url, kwargs = s.calls[0]
        assert url == f"https://pbs.local:{PBS_PORT}/api2/json/access/ticket"
        assert kwargs["data"] == {"username": "root@pam", "password": "secret"}
        assert c._ticket == "TICKET"
        assert c._csrf == "CSRF"

    def test_login_bad_credentials(self):
        s = FakeSession([FakeResponse(401)])
        c = make_client(s)
        with pytest.raises(PbsError, match="auth failed"):
            c.login()
        assert c._ticket == ""

    def test_request_login_on_demand(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=[1])])
        c = make_client(s)
        assert c.get("/version") == [1]
        assert len(s.calls) == 2
        # second request reuses the ticket — no extra login
        s.responses.append(FakeResponse(200, data={"a": 1}))
        assert c.get("/version") == {"a": 1}
        assert len(s.calls) == 3

    def test_relogin_once_on_401(self):
        s = FakeSession([
            ticket_response(),
            FakeResponse(401),
            ticket_response(),
            FakeResponse(200, data="ok"),
        ])
        c = make_client(s)
        assert c.get("/version") == "ok"

    def test_401_twice_raises(self):
        s = FakeSession([
            ticket_response(),
            FakeResponse(401),
            ticket_response(),
            FakeResponse(401),
        ])
        c = make_client(s)
        with pytest.raises(PbsError, match="401"):
            c.get("/version")

    def test_headers_and_cookies(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data={})])
        c = make_client(s)
        c.post("/admin/sync/j1/run")
        method, url, kwargs = s.calls[1]
        assert method == "POST"
        assert kwargs["headers"] == {"CSRFPreventionToken": "CSRF"}
        assert kwargs["cookies"] == {"PBSAuthCookie": "TICKET"}

    def test_trust_ssl_disables_verify(self):
        c = PbsClient({**_CFG, "trust_ssl": True})
        assert c._http.verify is False


class TestEndpoints:
    def test_datastores(self):
        s = FakeSession([
            ticket_response(),
            FakeResponse(200, data=[{"store": "main", "path": "/d"}]),
        ])
        c = make_client(s)
        assert c.datastores() == [{"store": "main", "path": "/d"}]
        assert s.calls[1][1].endswith("/config/datastore")

    def test_datastore_status_encodes_name(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data={})])
        c = make_client(s)
        c.datastore_status("my store")
        assert "/admin/datastore/my%20store/status" in s.calls[1][1]

    def test_snapshots_with_ns(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=[])])
        c = make_client(s)
        c.snapshots("main", ns="t1")
        assert s.calls[1][2]["params"] == {"ns": "t1"}

    def test_snapshots_without_ns(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=[])])
        c = make_client(s)
        c.snapshots("main")
        assert s.calls[1][2]["params"] is None

    def test_namespaces_parent_param(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=[])])
        c = make_client(s)
        c.namespaces("main", parent="base")
        assert s.calls[1][2]["params"] == {"parent": "base"}

    def test_jobs_kind_validation(self):
        c = PbsClient(_CFG)
        with pytest.raises(ValueError):
            c.jobs("bogus")

    def test_jobs_endpoint(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=[])])
        c = make_client(s)
        c.jobs("sync")
        assert s.calls[1][1].endswith("/admin/sync")

    def test_run_job_returns_upid(self):
        s = FakeSession([ticket_response(),
                         FakeResponse(200, data="UPID:abc")])
        c = make_client(s)
        assert c.run_job("verify", "v1") == "UPID:abc"
        assert s.calls[1][1].endswith("/admin/verify/v1/run")

    def test_verify_datastore(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data="UPID:v")])
        c = make_client(s)
        assert c.verify_datastore("main") == "UPID:v"
        assert s.calls[1][1].endswith("/admin/datastore/main/verify")

    def test_forget_snapshot_params(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=None)])
        c = make_client(s)
        c.forget_snapshot("main", "vm", "100", 1700000000, ns="t1")
        method, url, kwargs = s.calls[1]
        assert method == "DELETE"
        assert kwargs["params"] == {
            "backup-type": "vm", "backup-id": "100",
            "backup-time": "1700000000", "ns": "t1",
        }

    def test_forget_snapshot_no_ns(self):
        s = FakeSession([ticket_response(), FakeResponse(200, data=None)])
        c = make_client(s)
        c.forget_snapshot("main", "vm", "100", 1700000000)
        assert "ns" not in s.calls[1][2]["params"]

    def test_error_response_raises(self):
        s = FakeSession([
            ticket_response(),
            FakeResponse(400, errors={"param": "bad"}),
        ])
        c = make_client(s)
        with pytest.raises(PbsError, match="HTTP 400"):
            c.get("/config/datastore")


class TestConnectionErrors:
    def test_timeout(self, monkeypatch):
        import requests as real_requests

        class TimeoutSession(FakeSession):
            def post(self, url, **kwargs):
                raise real_requests.exceptions.Timeout("too slow")

        c = make_client(TimeoutSession())
        with pytest.raises(PbsError, match="timeout"):
            c.login()

    def test_connection_error(self, monkeypatch):
        import requests as real_requests

        class DeadSession(FakeSession):
            def post(self, url, **kwargs):
                raise real_requests.exceptions.ConnectionError("refused")

        c = make_client(DeadSession())
        with pytest.raises(PbsError, match="connection failed"):
            c.login()

    def test_non_json_response(self):
        s = FakeSession([ticket_response(), FakeResponse(200, raw="<html>")])
        c = make_client(s)
        assert c.get("/version") is None
