from __future__ import annotations

import asyncio
import gc
import json
import os

from loguru import logger
from changedetectionio.pluggy_interface import hookimpl

from .common import camoufox_launch_kwargs, merge_proxy


@hookimpl
def register_content_fetcher():
    from changedetectionio.content_fetchers import (
        FAVICON_FETCHER_JS,
        INSTOCK_DATA_JS,
        SCREENSHOT_MAX_HEIGHT_DEFAULT,
        XPATH_ELEMENT_JS,
        visualselector_xpath_selectors,
    )
    from changedetectionio.content_fetchers.base import Fetcher, manage_user_agent
    from changedetectionio.content_fetchers.exceptions import (
        BrowserStepsStepException,
        EmptyReply,
        Non200ErrorCodeReceived,
        PageUnloadable,
        ScreenshotUnavailable,
    )
    from changedetectionio.content_fetchers.playwright import capture_full_page_async

    class fetcher(Fetcher):
        fetcher_description = "Camoufox - stealth Firefox (plugin)"
        supports_browser_steps = True
        supports_screenshots = True
        supports_xpath_element_data = True

        proxy = None

        def __init__(self, proxy_override=None, custom_browser_connection_url=None, **kwargs):
            super().__init__(**kwargs)
            if custom_browser_connection_url:
                logger.warning(
                    "Camoufox fetcher ignores custom_browser_connection_url; it launches Camoufox directly."
                )
            self.proxy = merge_proxy(None, proxy_override)
            self._playwright = None
            self._browser = None
            self._context = None

        @classmethod
        def get_status_icon_data(cls):
            return {
                "group": "plugin",
                "filename": "favicon.ico",
                "alt": "Using Camoufox",
                "title": "Camoufox — stealth Firefox",
            }

        async def _launch_browser(self):
            from camoufox.async_api import AsyncNewBrowser
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await AsyncNewBrowser(
                self._playwright,
                **camoufox_launch_kwargs(proxy=self.proxy),
            )
            return self._browser

        async def screenshot_step(self, step_n=""):
            super().screenshot_step(step_n=step_n)
            watch_uuid = getattr(self, "watch_uuid", None)
            screenshot = await capture_full_page_async(
                page=self.page,
                screenshot_format=self.screenshot_format,
                watch_uuid=watch_uuid,
                lock_viewport_elements=self.lock_viewport_elements,
            )
            if self.browser_steps_screenshot_path is not None:
                destination = os.path.join(
                    self.browser_steps_screenshot_path, f"step_{step_n}.jpeg"
                )
                logger.debug(f"Saving step screenshot to {destination}")
                with open(destination, "wb") as f:
                    f.write(screenshot)
            del screenshot
            gc.collect()

        async def save_step_html(self, step_n):
            super().save_step_html(step_n=step_n)
            content = await self.page.content()
            destination = os.path.join(self.browser_steps_screenshot_path, f"step_{step_n}.html")
            logger.debug(f"Saving step HTML to {destination}")
            with open(destination, "w", encoding="utf-8") as f:
                f.write(content)
            del content
            gc.collect()

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
            import time
            from changedetectionio.browser_steps.browser_steps import steppable_browser_interface

            self.delete_browser_steps_screenshots()
            self.watch_uuid = watch_uuid
            request_headers = request_headers or {}
            response = None

            try:
                browser = await self._launch_browser()
                self._context = await browser.new_context(
                    accept_downloads=False,
                    bypass_csp=True,
                    extra_http_headers=request_headers,
                    ignore_https_errors=True,
                    service_workers=os.getenv("PLAYWRIGHT_SERVICE_WORKERS", "allow"),
                    user_agent=manage_user_agent(headers=request_headers),
                )
                self.page = await self._context.new_page()
                self.page.on(
                    "console",
                    lambda msg: logger.debug(
                        f"Camoufox console: {url} {msg.type}: {msg.text} {msg.args}"
                    ),
                )

                browsersteps_interface = steppable_browser_interface(start_url=url)
                browsersteps_interface.page = self.page
                response = await browsersteps_interface.action_goto_url(value=url)
                if response is None:
                    raise EmptyReply(url=url, status_code=None)

                try:
                    self.headers = await response.all_headers()
                except TypeError:
                    self.headers = response.all_headers()

                try:
                    if self.webdriver_js_execute_code and len(self.webdriver_js_execute_code):
                        await browsersteps_interface.action_execute_js(
                            value=self.webdriver_js_execute_code, selector=None
                        )
                except Exception as e:
                    logger.debug(f"Camoufox > Error executing custom JS: {e}")
                    raise PageUnloadable(url=url, status_code=None, message=str(e))

                extra_wait = int(os.getenv("WEBDRIVER_DELAY_BEFORE_CONTENT_READY", 5)) + int(
                    self.render_extract_delay
                )
                await self.page.wait_for_timeout(extra_wait * 1000)

                try:
                    self.status_code = response.status
                except Exception as e:
                    raise PageUnloadable(url=url, status_code=None, message=str(e))

                if fetch_favicon:
                    try:
                        self.favicon_blob = await self.page.evaluate(FAVICON_FETCHER_JS)
                    except Exception as e:
                        logger.debug(f"Camoufox > Error fetching favicon: {e}; continuing")

                if self.status_code != 200 and not ignore_status_codes:
                    screenshot = await capture_full_page_async(
                        self.page,
                        screenshot_format=self.screenshot_format,
                        watch_uuid=watch_uuid,
                        lock_viewport_elements=self.lock_viewport_elements,
                    )
                    raise Non200ErrorCodeReceived(
                        url=url, status_code=self.status_code, screenshot=screenshot
                    )

                if not empty_pages_are_a_change and len((await self.page.content()).strip()) == 0:
                    raise EmptyReply(url=url, status_code=response.status)

                try:
                    if self.browser_steps:
                        try:
                            await self.iterate_browser_steps(start_url=url)
                        except BrowserStepsStepException:
                            raise
                        await self.page.wait_for_timeout(extra_wait * 1000)

                    now = time.time()
                    max_total_height = int(
                        os.getenv("SCREENSHOT_MAX_HEIGHT", SCREENSHOT_MAX_HEIGHT_DEFAULT)
                    )
                    await self.page.evaluate(
                        f"var include_filters={json.dumps(current_include_filters or '')}"
                    )
                    self.xpath_data = await self.page.evaluate(
                        XPATH_ELEMENT_JS,
                        {
                            "visualselector_xpath_selectors": visualselector_xpath_selectors,
                            "max_height": max_total_height,
                        },
                    )
                    self.instock_data = await self.page.evaluate(INSTOCK_DATA_JS)
                    self.content = await self.page.content()
                    logger.debug(f"Camoufox > Scraped data in {time.time() - now:.2f}s")
                    self.screenshot = await capture_full_page_async(
                        page=self.page,
                        screenshot_format=self.screenshot_format,
                        watch_uuid=watch_uuid,
                        lock_viewport_elements=self.lock_viewport_elements,
                    )
                    gc.collect()
                except ScreenshotUnavailable:
                    raise ScreenshotUnavailable(url=url, status_code=self.status_code)
            finally:
                await self.quit()

        async def quit(self, watch=None):
            for attr, label in (("page", "page"), ("_context", "context"), ("_browser", "browser")):
                obj = getattr(self, attr, None)
                if obj:
                    try:
                        await asyncio.wait_for(obj.close(), timeout=5.0)
                    except Exception as e:
                        logger.warning(f"Camoufox > Error closing {label}: {e}")
                    finally:
                        setattr(self, attr, None)
            if self._playwright:
                try:
                    await asyncio.wait_for(self._playwright.stop(), timeout=5.0)
                except Exception as e:
                    logger.warning(f"Camoufox > Error stopping Playwright: {e}")
                finally:
                    self._playwright = None
            gc.collect()

        def get_error(self):
            return self.error

        def get_last_status_code(self):
            return self.status_code

        def is_ready(self):
            try:
                import camoufox  # noqa: F401
                import playwright  # noqa: F401
                return True
            except ImportError as e:
                logger.error(f"Camoufox fetcher is not ready: {e}")
                return False

    # Prefix with extra_browser_ so changedetection.io's OpenAPI/API validators accept it
    # without patching changedetection.io source.
    return ("extra_browser_camoufox", fetcher)
