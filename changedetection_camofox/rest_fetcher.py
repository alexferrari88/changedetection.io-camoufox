from __future__ import annotations

import base64
import os
import time
from urllib.parse import quote

import httpx
from loguru import logger
from changedetectionio.pluggy_interface import hookimpl


@hookimpl
def register_content_fetcher():
    from changedetectionio.content_fetchers.base import Fetcher
    from changedetectionio.content_fetchers.exceptions import EmptyReply, Non200ErrorCodeReceived

    class fetcher(Fetcher):
        fetcher_description = "camofox-browser REST server (experimental)"
        supports_browser_steps = False
        supports_screenshots = True
        supports_xpath_element_data = False

        def __init__(self, proxy_override=None, custom_browser_connection_url=None, **kwargs):
            super().__init__(**kwargs)
            self.base_url = (
                custom_browser_connection_url
                or os.getenv("CAMOFOX_BROWSER_URL")
                or os.getenv("CAMOUFOX_BROWSER_URL")
                or "http://127.0.0.1:9377"
            ).rstrip("/")
            self.user_id = os.getenv("CAMOFOX_CHANGED_USER_ID", "changedetection")
            self.api_key = os.getenv("CAMOFOX_API_KEY")
            self.tab_id = None
            if proxy_override:
                logger.warning(
                    "camofox-browser REST fetcher received a per-watch proxy override, but "
                    "the REST server owns proxy configuration. Configure camofox-browser instead."
                )

        def _headers(self):
            headers = {"content-type": "application/json"}
            if self.api_key:
                headers["authorization"] = f"Bearer {self.api_key}"
            return headers

        async def _post(self, path, payload, timeout):
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                response = await client.post(f"{self.base_url}{path}", json=payload)
                response.raise_for_status()
                return response.json()

        async def _get(self, path, timeout):
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                response = await client.get(f"{self.base_url}{path}")
                response.raise_for_status()
                return response.json()

        async def _delete(self, path, timeout):
            async with httpx.AsyncClient(timeout=timeout, headers=self._headers()) as client:
                response = await client.delete(f"{self.base_url}{path}")
                if response.status_code not in (200, 204, 404):
                    response.raise_for_status()

        async def _evaluate(self, expression, timeout):
            data = await self._post(
                f"/tabs/{quote(self.tab_id)}/evaluate",
                {"userId": self.user_id, "expression": expression},
                timeout,
            )
            return data.get("result")

        async def run(
            self,
            fetch_favicon=True,
            current_include_filters=None,
            empty_pages_are_a_change=False,
            ignore_status_codes=False,
            is_binary=False,
            request_body=None,
            request_headers=None,
            request_method=None,
            screenshot_format=None,
            timeout=None,
            url=None,
            watch_uuid=None,
        ):
            timeout = timeout or int(os.getenv("CAMOFOX_REST_TIMEOUT", "60"))
            session_key = f"changedetection-{watch_uuid or int(time.time())}"
            try:
                created = await self._post(
                    "/tabs",
                    {"userId": self.user_id, "sessionKey": session_key, "url": url},
                    timeout,
                )
                self.tab_id = created.get("tabId") or created.get("id")
                wait_s = int(os.getenv("WEBDRIVER_DELAY_BEFORE_CONTENT_READY", "5")) + int(
                    self.render_extract_delay
                )
                if wait_s > 0:
                    time.sleep(wait_s)

                if self.webdriver_js_execute_code:
                    await self._evaluate(self.webdriver_js_execute_code, timeout)

                status = await self._evaluate("document.readyState", timeout)
                self.status_code = 200 if status else None
                self.headers = {}
                self.content = await self._evaluate("document.documentElement.outerHTML", timeout)

                if not self.content and not empty_pages_are_a_change:
                    raise EmptyReply(url=url, status_code=self.status_code)
                if self.status_code != 200 and not ignore_status_codes:
                    raise Non200ErrorCodeReceived(url=url, status_code=self.status_code)

                try:
                    shot = await self._get(
                        f"/tabs/{quote(self.tab_id)}/screenshot?userId={quote(self.user_id)}",
                        timeout,
                    )
                    screenshot = shot.get("screenshot", {})
                    data = screenshot.get("data")
                    if data:
                        self.screenshot = base64.b64decode(data)
                except Exception as e:
                    logger.debug(f"camofox-browser REST screenshot unavailable: {e}")
            finally:
                await self.quit()

        async def quit(self, watch=None):
            if self.tab_id:
                await self._delete(
                    f"/tabs/{quote(self.tab_id)}?userId={quote(self.user_id)}",
                    int(os.getenv("CAMOFOX_REST_TIMEOUT", "60")),
                )
                self.tab_id = None

        def get_error(self):
            return self.error

        def get_last_status_code(self):
            return self.status_code

        def screenshot_step(self, step_n):
            return None

        def is_ready(self):
            try:
                with httpx.Client(timeout=5, headers=self._headers()) as client:
                    response = client.get(f"{self.base_url}/health")
                    return response.status_code == 200
            except Exception as e:
                logger.error(f"camofox-browser REST fetcher is not ready: {e}")
                return False

    return ("extra_browser_camofox_rest", fetcher)
