# Containerfile
FROM registry.access.redhat.com/ubi9/python-311

# (Optional) install dependencies for requests/dateutil if needed
# Comment these 3 lines out if you already have them in the image.
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir requests python-dateutil

# Prepare writable dirs, group-owned by 0 and group-writable
USER 0
RUN mkdir -p /app /data /site \
 && chgrp -R 0 /app /data /site \
 && chmod -R g+rwX /app /data /site

# Copy app code & config
COPY usgs_multi_alert.py /app/usgs_multi_alert.py
COPY qpf.py             /app/qpf.py
COPY entrypoint.sh      /app/entrypoint.sh
COPY gauges.conf.json   /app/gauges.conf.json

# Ensure executable
RUN chmod 0755 /app/entrypoint.sh /app/usgs_multi_alert.py

# Drop privileges: run as UID 10001, GID 0 (so group perms apply)
USER 10001:0

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --retries=3 CMD test -s /site/gauges.json || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]

