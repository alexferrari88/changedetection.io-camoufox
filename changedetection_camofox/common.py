from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"", "0", "false", "no", "off"}


def env_headless(name: str = "CAMOUFOX_HEADLESS") -> bool | str:
    raw = os.getenv(name, "true").strip().lower()
    if raw == "virtual":
        return "virtual"
    return raw not in {"", "0", "false", "no", "off"}


def env_number_or_bool(name: str, default: bool | float = False) -> bool | float:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    try:
        return float(value)
    except ValueError:
        return True


def proxy_url_to_dict(url: str | None) -> dict[str, str] | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return {"server": url}
    port = f":{parsed.port}" if parsed.port else ""
    proxy: dict[str, str] = {"server": f"{parsed.scheme}://{parsed.hostname}{port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


def merge_proxy(base: dict[str, str] | None, override_url: str | None) -> dict[str, str] | None:
    if override_url:
        return proxy_url_to_dict(override_url)
    if base:
        return dict(base)
    env_server = os.getenv("playwright_proxy_server")
    if not env_server:
        return None
    proxy = proxy_url_to_dict(env_server) or {"server": env_server}
    if os.getenv("playwright_proxy_username"):
        proxy["username"] = os.getenv("playwright_proxy_username", "")
    if os.getenv("playwright_proxy_password"):
        proxy["password"] = os.getenv("playwright_proxy_password", "")
    return proxy


def camoufox_launch_kwargs(proxy: dict[str, str] | None = None) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "headless": env_headless(),
        "humanize": env_number_or_bool("CAMOUFOX_HUMANIZE", False),
    }
    if proxy:
        kwargs["proxy"] = proxy
    if env_bool("CAMOUFOX_GEOIP", False):
        kwargs["geoip"] = True
    if env_bool("CAMOUFOX_BLOCK_IMAGES", False):
        kwargs["block_images"] = True
    if os.getenv("CAMOUFOX_OS"):
        values = [v.strip() for v in os.getenv("CAMOUFOX_OS", "").split(",") if v.strip()]
        kwargs["os"] = values[0] if len(values) == 1 else values
    executable = os.getenv("CAMOUFOX_EXECUTABLE") or os.getenv("CAMOUFOX_EXECUTABLE_PATH")
    if executable:
        kwargs["executable_path"] = executable
    return kwargs
