FROM ghcr.io/dgtlmoon/changedetection.io:0.55.3

# Build with the local source checked out next to this Dockerfile context:
#   docker build -f examples/Dockerfile -t changedetection-camoufox .
COPY . /tmp/changedetection.io-camoufox
RUN pip install --no-cache-dir /tmp/changedetection.io-camoufox[geoip] \
    && camoufox fetch \
    && rm -rf /tmp/changedetection.io-camoufox

ENV CAMOUFOX_HEADLESS=true \
    CAMOUFOX_HUMANIZE=false \
    CAMOUFOX_GEOIP=false \
    PLAYWRIGHT_SERVICE_WORKERS=block
