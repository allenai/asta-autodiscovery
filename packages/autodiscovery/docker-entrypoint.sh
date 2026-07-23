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
#
# When GCSFUSE_ONLY_DIR is set (e.g. users/<uid>/jobs/<jid>), only that prefix is
# mounted, at the matching deep path under /mnt/gcs, so the job sees only its own
# data even when code executes in-process. This keeps other users' workspaces out
# of the container. Without it, the whole bucket is mounted at /mnt/gcs.
set -e

if [ -n "${GCSFUSE_BUCKET}" ]; then
    if [ -n "${GCSFUSE_ONLY_DIR}" ]; then
        mountpoint="/mnt/gcs/${GCSFUSE_ONLY_DIR}"
        echo "Mounting gs://${GCSFUSE_BUCKET}/${GCSFUSE_ONLY_DIR} at ${mountpoint} via gcsfuse..."
        mkdir -p "${mountpoint}"
        gcsfuse --implicit-dirs --only-dir "${GCSFUSE_ONLY_DIR}" "${GCSFUSE_BUCKET}" "${mountpoint}"
    else
        echo "Mounting gs://${GCSFUSE_BUCKET} at /mnt/gcs via gcsfuse..."
        mkdir -p /mnt/gcs
        gcsfuse --implicit-dirs "${GCSFUSE_BUCKET}" /mnt/gcs
    fi
fi

exec /root/.local/bin/uv run python -m autodiscovery.run "$@"
