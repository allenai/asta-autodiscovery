#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${ROOT_DIR}"

# Configuration
PROJECT_ID=$(gcloud config get-value project)
REGION="us-west1"
VERTEX_LOCATION="${VERTEX_LOCATION:-$REGION}"
ENV_TAG="${ENV_TAG:-dev}"  # Default to dev, override with ENV_TAG=prod
SKIP_BUILD="${SKIP_BUILD:-false}"  # Set SKIP_BUILD=true to skip image build
IMAGE="us-west1-docker.pkg.dev/${PROJECT_ID}/autodiscovery/autodiscovery:${ENV_TAG}"
JOB_NAME="autodiscovery-job-${ENV_TAG}"
BUCKET="example-gcp-project"
OPENAI_SECRET_NAME="openai-api-key-secret"
MODAL_TOKEN_ID_SECRET_NAME="modal-token-id-secret"
MODAL_TOKEN_SECRET_SECRET_NAME="modal-token-secret"
MODAL_ENVIRONMENT_SECRET_NAME="modal-environment-secret"
MODAL_IMAGE_BUILDER_SECRET_NAME="modal-image-builder-secret"

echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Environment: ${ENV_TAG}"
echo "Image: ${IMAGE}"
echo "Job: ${JOB_NAME}"
echo ""

# Verify required secrets exist
echo "Verifying required secrets..."
missing_secrets=()
for secret in \
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

# Step 1: Build and push image using Cloud Build (optional)
if [ "$SKIP_BUILD" = "false" ]; then
    echo "========================================="
    echo "Step 1: Building and pushing Docker image"
    echo "========================================="
    echo "Note: Building with tag ${ENV_TAG} using Cloud Build"
    echo "      To skip build and use existing image, set SKIP_BUILD=true"
    echo ""

    gcloud builds submit \
        --config="${ROOT_DIR}/packages/autodiscovery/cloudbuild.yaml" \
        --substitutions="_IMAGE_TAG=${ENV_TAG}" \
        "${ROOT_DIR}"
else
    echo "========================================="
    echo "Step 1: Skipping image build (SKIP_BUILD=true)"
    echo "========================================="
    echo "Using existing image: ${IMAGE}"
    echo ""
fi

echo ""
echo "========================================="
echo "Step 2: Updating Cloud Run Job"
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
echo "  ./scripts/setup_job.sh exampleuser job1 ./discoverybench/nls_ses/ ./metadata.json"
echo "  ./scripts/run_job.sh exampleuser job1"
