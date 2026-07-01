#!/bin/sh
# Entrypoint for the AutoDiscovery job image.
#
# On Cloud Run the GCS bucket is provided as a FUSE volume at /mnt/gcs by the
# platform, so GCSFUSE_BUCKET is left unset and this script just runs the job.
#
# For the local Docker job backend there is no platform-provided volume, so the
# container mounts the bucket itself: when GCSFUSE_BUCKET is set, gcsfuse mounts
# gs://$GCSFUSE_BUCKET at /mnt/gcs (authenticating via GOOGLE_APPLICATION_CREDENTIALS)
# before the job starts. gcsfuse requires the /dev/fuse device and CAP_SYS_ADMIN,
# which the Docker backend grants when launching the container.
set -e

if [ -n "${GCSFUSE_BUCKET}" ]; then
    echo "Mounting gs://${GCSFUSE_BUCKET} at /mnt/gcs via gcsfuse..."
    mkdir -p /mnt/gcs
    gcsfuse --implicit-dirs "${GCSFUSE_BUCKET}" /mnt/gcs
fi

exec /root/.local/bin/uv run python -m autodiscovery.run "$@"
