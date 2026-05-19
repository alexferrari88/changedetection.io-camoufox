# Architecture notes

## Candidate integrations evaluated

1. **Set `PLAYWRIGHT_DRIVER_URL` to Camoufox/Camoufox server** — rejected for stock changedetection.io 0.55.3. changedetection.io's built-in Playwright fetcher connects to Chromium/CDP-style endpoints; Camoufox exposes Firefox Playwright connections (`p.firefox.connect(...)`). That mismatch requires a changedetection.io code patch or a fetcher plugin.

2. **Use `jo-inc/camofox-browser` REST API directly** — viable as a plugin adapter for simple checks. It can create a tab, evaluate `document.documentElement.outerHTML`, and collect screenshots. It is not a full Playwright `Page`, so changedetection.io browser steps and visual selector internals need reimplementation or a native fetcher.

3. **Native changedetection.io plugin using `camoufox` Python package** — recommended. It registers through changedetection.io's pluggy entry point and returns a normal Playwright Firefox page object. This keeps changedetection.io unchanged and preserves browser steps/custom JS/screenshot behavior.

## Why `extra_browser_camoufox`, not `html_camoufox`?

changedetection.io's plugin hook documentation says content fetchers should start with `html_`, but the 0.55.3 OpenAPI schema for watch create/update only accepts:

```text
^(system|html_requests|html_webdriver|extra_browser_.+)$
```

A plugin named `html_camoufox` can show in the UI but API writes can be rejected before the application code sees the installed fetcher list. Registering the fetcher as `extra_browser_camoufox` avoids a source patch and still resolves to the plugin class because changedetection.io checks `hasattr(changedetectionio.content_fetchers, prefer_fetch_backend)` after its `extra_browser_` custom-browser lookup.

## Operational risks

- Camoufox is Firefox-based. Sites that specifically expect Chromium may behave differently from changedetection.io's default `html_webdriver` stack.
- Camoufox binary fetch should happen at image build time for deterministic production deploys.
- `CAMOUFOX_GEOIP=true` may perform an external IP lookup; keep it off unless proxy geolocation alignment matters.
- Anti-bot bypass is not guaranteed. IP quality, cookies, rate limits, TLS/network fingerprinting, and site-specific challenges still matter.
- The REST adapter currently does not implement changedetection.io browser steps; use native Camoufox for product-watch normalization flows.

## Open-source shape

This repository is designed to be published independently:

- no changedetection.io source patches
- pluggy entry points only
- Docker examples instead of instance-specific config
- `extra_browser_*` names for API compatibility
- no embedded secrets or proxy credentials
