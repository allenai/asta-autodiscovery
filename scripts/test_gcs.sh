#!/bin/bash

# Define constants
BUCKET="autodiscovery"
OTHER_BUCKET="aristo-reeca"
ENDPOINT="https://storage.googleapis.com"

echo "--- Starting GCS Access Key Validation ---"

# --- STEP 1: Test without reassignment ---
echo "Step 1: Testing access WITHOUT reassigned variables..."
# Unset any current AWS keys to ensure a clean slate
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY

if aws s3 ls "s3://$BUCKET" --endpoint-url "$ENDPOINT" 2>/dev/null; then
    echo "❌ Unexpected Success: Access should have been denied."
else
    echo "✅ Success: Access denied as expected (No credentials)."
fi

echo "------------------------------------------"

# --- STEP 2: Test with reassignment ---
echo "Step 2: Testing access WITH reassigned variables..."
export AWS_ACCESS_KEY_ID="$GOOGLE_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$GOOGLE_ACCESS_KEY_SECRET"

if aws s3 ls "s3://$BUCKET" --endpoint-url "$ENDPOINT"; then
    echo "✅ Success: Access granted to $BUCKET."
else
    echo "❌ Failure: Access denied to $BUCKET (Check keys/permissions)."
fi

echo "------------------------------------------"

# --- STEP 3: Test access to unrelated bucket ---
echo "Step 3: Testing access to unrelated bucket ($OTHER_BUCKET)..."
if aws s3 ls "s3://$OTHER_BUCKET" --endpoint-url "$ENDPOINT" 2>/dev/null; then
    echo "❌ Unexpected Success: You have access to $OTHER_BUCKET."
else
    echo "✅ Success: Access denied to $OTHER_BUCKET as expected."
fi

echo "--- Validation Complete ---"
