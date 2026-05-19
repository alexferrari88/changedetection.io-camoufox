# changedetection.io-camoufox

`changedetection.io-camoufox` is a changedetection.io plugin that adds Camoufox-backed fetchers without patching changedetection.io source.

It registers two fetch backends:

```text
extra_browser_camoufox       Native Camoufox Python/Playwright fetcher; best compatibility.
extra_browser_camofox_rest   Experimental adapter for a running jo-inc/camofox-browser REST server.
```

## Why the `extra_browser_` prefix?

changedetection.io 0.55.3 validates API `fetch_backend` values with a regex that accepts `system`, `html_requests`, `html_webdriver`, and `extra_browser_*`. A normal plugin name such as `html_camoufox` can appear in the UI but may be rejected by POST/PUT API calls. Using `extra_browser_camoufox` lets the plugin work through both the UI and API while still requiring **zero source changes** to changedetection.io.

## Recommended approach

Use `extra_browser_camoufox`.

It launches Camoufox directly inside the changedetection.io container via the Python `camoufox` package. The returned objects are normal Playwright Firefox `browser/context/page` objects, so changedetection.io browser steps, screenshots, custom JS, visual selectors, and restock processors can reuse changedetection.io's existing Playwright-oriented internals.

Use `extra_browser_camofox_rest` only when you already operate [`jo-inc/camofox-browser`](https://github.com/jo-inc/camofox-browser) and want a low-risk first smoke test. The REST adapter can fetch HTML and screenshots through `/tabs`, `/evaluate`, and `/screenshot`, but it does **not** yet implement changedetection.io browser steps.

## Requirements

- changedetection.io 0.55.3 or newer, already installed/running.
- Linux container/host dependencies required by Playwright Firefox/Camoufox.
- Camoufox binaries fetched with `camoufox fetch` before production use.

The package intentionally does **not** declare `changedetection.io` as a dependency, because it is meant to be installed inside an existing changedetection.io image/runtime and should not cause pip to reinstall the host app.

## Install in Docker Compose

### Option A — `EXTRA_PACKAGES` from GitHub/PyPI

```yaml
services:
  changedetection:
    image: ghcr.io/dgtlmoon/changedetection.io:0.55.3
    environment:
      - EXTRA_PACKAGES=changedetection.io-camoufox[geoip]
      - CAMOUFOX_HEADLESS=true
      - CAMOUFOX_HUMANIZE=false
      - CAMOUFOX_GEOIP=false
      - PLAYWRIGHT_SERVICE_WORKERS=block
```

Then prefetch Camoufox once inside the container/image:

```bash
docker compose exec changedetection camoufox fetch
```

### Option B — custom image

See [`examples/Dockerfile`](examples/Dockerfile). This is better for production because browser binaries are fetched during image build rather than at first check.

## Select per watch

UI: Watch → Edit → Fetch → choose **Camoufox - stealth Firefox (plugin)**.

API:

```bash
curl -X PUT "$CHANGEDETECTION_BASE_URL/api/v1/watch/$WATCH_UUID" \
  -H "x-api-key: $CHANGEDETECTION_API_KEY" \
  -H "content-type: application/json" \
  -d '{"fetch_backend":"extra_browser_camoufox"}'
```

## Runtime environment

```text
CAMOUFOX_HEADLESS=true|false|virtual   default true
CAMOUFOX_HUMANIZE=true|false|1.5       default false
CAMOUFOX_GEOIP=true|false              default false; requires camoufox[geoip]
CAMOUFOX_BLOCK_IMAGES=true|false       default false
CAMOUFOX_OS=windows,macos,linux        optional fingerprint OS pool
CAMOUFOX_EXECUTABLE=/path/to/camoufox  optional externally managed Camoufox bundle
PLAYWRIGHT_SERVICE_WORKERS=block       recommended for deterministic monitoring
WEBDRIVER_DELAY_BEFORE_CONTENT_READY=5 changedetection-compatible wait
```

Proxy support reuses changedetection.io's `proxy_override` and `playwright_proxy_*` environment variables. Because changedetection.io 0.55.x skips passing per-watch proxies to `extra_browser_*` fetchers, the native fetcher also recovers the selected watch proxy from `/datastore/<watch_uuid>/watch.json` + `/datastore/proxies.json`.

For Camoufox IP/timezone/locale consistency, enable `CAMOUFOX_GEOIP=true` when using a residential proxy and the `camoufox[geoip]` extra.

## Current status

Alpha. The native fetcher is the target production path. The REST fetcher is intentionally narrower and exists to prove integration with an already-running `camofox-browser` service.

See [`docs/architecture.md`](docs/architecture.md) for the design trade-offs and known risks.
