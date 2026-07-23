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
# When GCSFUSE_ONLY_DIR is also set, the mount is scoped to just that prefix
# (this run's users/<uid>/jobs/<jid>) for least-privilege tenant isolation: the
# container then cannot see or modify other users' data through the filesystem.
# The scoped subtree is mounted at its full path (/mnt/gcs/$GCSFUSE_ONLY_DIR) so
# the job's existing absolute --dataset_metadata / --out_dir args still resolve.
set -e

if [ -n "${GCSFUSE_BUCKET}" ]; then
    if [ -n "${GCSFUSE_ONLY_DIR}" ]; then
        # Quote GCSFUSE_ONLY_DIR everywhere: user ids can contain a '|' char,
        # which is a valid path character but shell-special when unquoted.
        echo "Mounting gs://${GCSFUSE_BUCKET}/${GCSFUSE_ONLY_DIR} at /mnt/gcs/${GCSFUSE_ONLY_DIR} via gcsfuse..."
        mkdir -p "/mnt/gcs/${GCSFUSE_ONLY_DIR}"
        gcsfuse --implicit-dirs --only-dir "${GCSFUSE_ONLY_DIR}" "${GCSFUSE_BUCKET}" "/mnt/gcs/${GCSFUSE_ONLY_DIR}"
    else
        echo "Mounting gs://${GCSFUSE_BUCKET} at /mnt/gcs via gcsfuse..."
        mkdir -p /mnt/gcs
        gcsfuse --implicit-dirs "${GCSFUSE_BUCKET}" /mnt/gcs
    fi
fi

exec /root/.local/bin/uv run python -m autodiscovery.run "$@"
