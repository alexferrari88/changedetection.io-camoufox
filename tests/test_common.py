from changedetection_camofox.common import env_bool, proxy_url_to_dict


def test_proxy_url_to_dict_splits_auth():
    assert proxy_url_to_dict("http://user:pass@example.com:823") == {
        "server": "http://example.com:823",
        "username": "user",
        "password": "pass",
    }


def test_env_bool(monkeypatch):
    monkeypatch.setenv("X", "false")
    assert env_bool("X", True) is False
    monkeypatch.setenv("X", "yes")
    assert env_bool("X", False) is True
