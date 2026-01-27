#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${ROOT_DIR}"

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-west1"
VERTEX_LOCATION="${VERTEX_LOCATION:-$REGION}"
IMAGE="us-west1-docker.pkg.dev/${PROJECT_ID}/autodiscovery/autodiscovery:latest"
JOB_NAME="autodiscovery-job"
BUCKET="ai2-autodiscovery"
OPENAI_SECRET_NAME="autodiscovery-openai-key"
GITHUB_SECRET_NAME="autodiscovery-github-token"
MODAL_TOKEN_ID_SECRET_NAME="autodiscovery-modal-token-id"
MODAL_TOKEN_SECRET_SECRET_NAME="autodiscovery-modal-token-secret"
MODAL_ENVIRONMENT_SECRET_NAME="autodiscovery-modal-environment"
MODAL_IMAGE_BUILDER_SECRET_NAME="autodiscovery-modal-image-builder"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE}"
echo "Job: ${JOB_NAME}"
echo ""

# Verify required secrets exist
echo "Verifying required secrets..."
missing_secrets=()
for secret in \
    "${GITHUB_SECRET_NAME}" \
    "${OPENAI_SECRET_NAME}" \
    "${MODAL_TOKEN_ID_SECRET_NAME}" \
    "${MODAL_TOKEN_SECRET_SECRET_NAME}" \
    "${MODAL_ENVIRONMENT_SECRET_NAME}" \
    "${MODAL_IMAGE_BUILDER_SECRET_NAME}"; do
    if ! gcloud secrets describe "${secret}" >/dev/null 2>&1; then
        missing_secrets+=("${secret}")
    fi
done

if [ "${#missing_secrets[@]}" -gt 0 ]; then
    echo "ERROR: Missing required secrets:"
    for secret in "${missing_secrets[@]}"; do
        echo "  - ${secret}"
    done
    echo ""
    echo "Create the missing secrets before deploying. See packages/autodiscovery/CLOUD_RUN_DEPLOYMENT.md"
    exit 1
fi

echo "All required secrets are present."
echo ""

# Step 1: Build and push image using Cloud Build
echo "========================================="
echo "Step 1: Building and pushing Docker image"
echo "========================================="
gcloud builds submit --config="${ROOT_DIR}/packages/autodiscovery/cloudbuild.yaml" "${ROOT_DIR}"

echo ""
echo "========================================="
echo "Step 2: Updating Cloud Run Job with GCS mount"
echo "========================================="
UPDATE_SECRETS=(
    "OPENAI_API_KEY=${OPENAI_SECRET_NAME}:latest"
    "MODAL_TOKEN_ID=${MODAL_TOKEN_ID_SECRET_NAME}:latest"
    "MODAL_TOKEN_SECRET=${MODAL_TOKEN_SECRET_SECRET_NAME}:latest"
    "MODAL_ENVIRONMENT=${MODAL_ENVIRONMENT_SECRET_NAME}:latest"
    "MODAL_IMAGE_BUILDER_VERSION=${MODAL_IMAGE_BUILDER_SECRET_NAME}:latest"
)

UPDATE_SECRETS_ARG=$(IFS=,; echo "${UPDATE_SECRETS[*]}")
gcloud run jobs update ${JOB_NAME} \
    --region ${REGION} \
    --image ${IMAGE} \
    --update-secrets "${UPDATE_SECRETS_ARG}" \
    --update-env-vars "VERTEX_PROJECT_ID=${PROJECT_ID},VERTEX_LOCATION=${VERTEX_LOCATION}" \
    --add-volume name=job-storage,type=cloud-storage,bucket=${BUCKET} \
    --add-volume-mount volume=job-storage,mount-path=/mnt/gcs

echo ""
echo "Note: GCS bucket '${BUCKET}' is now mounted at /mnt/gcs/"

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Setup a new job:    ./scripts/setup_job.sh <userid> <jobid> <local_data_dir> [metadata_file]"
echo "2. Run the job:        ./scripts/run_job.sh <userid> <jobid>"
echo ""
echo "Example:"
echo "  ./scripts/setup_job.sh reecea job1 ./discoverybench/nls_ses/ ./metadata.json"
echo "  ./scripts/run_job.sh reecea job1"
