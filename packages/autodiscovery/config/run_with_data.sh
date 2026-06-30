#!/bin/bash
# One-shot: upload a dataset and run the autodiscovery Cloud Run job on it.
#
# Usage:
#   ./config/run_with_data.sh <job-tag> <metadata.json> <data.csv> [n_experiments]
#
# Example:
#   ./config/run_with_data.sh exp-2026-07-01 ./my_meta.json ./my_data.csv 4
#
# Uploads <metadata.json> + <data.csv> to gs://${BUCKET}/jobs/<job-tag>/ and
# executes the Cloud Run job, writing results to .../jobs/<job-tag>/output/.
# See config/cloud-run-runbook.md for the full reference.

set -euo pipefail

# ---- config (matches cloud-run-runbook.md) ----
PROJECT="autodiscovery-research"
REGION="us-central1"
JOB_NAME="test-adv"
BUCKET="sijia-adv-exp"
MODEL="gpt-5.4-mini"

# ---- args ----
if [ "$#" -lt 3 ]; then
  echo "Usage: $0 <job-tag> <metadata.json> <data.csv> [n_experiments]"
  exit 1
fi
JOB_TAG="$1"
META_PATH="$2"
DATA_PATH="$3"
N_EXPERIMENTS="${4:-4}"

[ -f "$META_PATH" ] || { echo "ERROR: metadata not found: $META_PATH"; exit 1; }
[ -f "$DATA_PATH" ] || { echo "ERROR: data not found: $DATA_PATH"; exit 1; }

# The metadata's datasets[].name must equal the uploaded data filename.
DATA_NAME="$(basename "$DATA_PATH")"
if ! grep -q "\"$DATA_NAME\"" "$META_PATH"; then
  echo "WARNING: '$DATA_NAME' not referenced in $META_PATH (datasets[].name must match the data filename)."
fi

GCS_DIR="gs://${BUCKET}/jobs/${JOB_TAG}"
MNT_DIR="/mnt/gcs/jobs/${JOB_TAG}"

echo "=== Uploading data to ${GCS_DIR}/ ==="
gcloud storage cp "$META_PATH" "$DATA_PATH" "${GCS_DIR}/" --project="$PROJECT"

echo "=== Executing job ${JOB_NAME} (tag=${JOB_TAG}, n_experiments=${N_EXPERIMENTS}) ==="
gcloud run jobs execute "$JOB_NAME" \
  --region="$REGION" --project="$PROJECT" --async \
  --args="--dataset_metadata=${MNT_DIR}/$(basename "$META_PATH"),\
--out_dir=${MNT_DIR}/output,\
--work_dir=work,\
--n_experiments=${N_EXPERIMENTS},\
--model=${MODEL},--belief_model=${MODEL},--vision_model=${MODEL},\
--no-timestamp_dir"

echo ""
echo "Started. Results will appear under ${GCS_DIR}/output/"
echo "Watch status:"
echo "  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --project=${PROJECT} --limit=1"
echo "Download results when done:"
echo "  gcloud storage cp -r \"${GCS_DIR}/output/*\" ./local_out/ --project=${PROJECT}"
