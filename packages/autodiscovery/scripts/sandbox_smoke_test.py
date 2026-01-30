import logging
import os

import modal
from autodiscovery_modal import ModalSandboxIPythonBackend, build_sandbox_image
from code_execution import IPythonExecutor

logging.basicConfig(level=logging.INFO, format="%(message)s")
app_name = os.environ.get("MODAL_APP_NAME", "asta-autodiscovery")
bucket = os.environ.get("GCS_BUCKET", "example-gcp-project")
key_prefix = os.environ.get("GCS_PREFIX", "samples/")
read_only = os.environ.get("GCS_READ_ONLY", "true").lower() == "true"
bucket_endpoint_url = os.environ.get("GCS_ENDPOINT_URL", "https://storage.googleapis.com")
mount_path = "/data"

secret_name = os.environ.get("MODAL_BUCKET_SECRET", "example-bucket-secret")
if not secret_name:
    raise ValueError("Set MODAL_BUCKET_SECRET to a Modal Secret with GCS credentials.")

bucket_secret = modal.Secret.from_name(secret_name)
image = build_sandbox_image(extra_packages=["matplotlib", "matplotlib-inline", "scipy"])
backend = ModalSandboxIPythonBackend.for_bucket_prefix(
    app_name=app_name,
    bucket=bucket,
    key_prefix=key_prefix,
    mount_path=mount_path,
    read_only=read_only,
    bucket_endpoint_url=bucket_endpoint_url,
    bucket_secret=bucket_secret,
    image=image,
    env={"SMOKE_TEST": "true"},
)

executor = IPythonExecutor(backend)
code = """
import matplotlib.pyplot as plt

import os

print(os.listdir("/data"))

plt.figure(figsize=(4, 3))
plt.plot([0, 1, 2, 3], [0, 1, 4, 9], marker="o")
plt.title("Sandbox Smoke Test")
plt.xlabel("x")
plt.ylabel("y")
plt.tight_layout()
plt.show()
"""
result = executor.run_cell(code)

print(result["stdout"])
rich_outputs = result.get("rich_outputs")
if rich_outputs:
    print(f"rich_outputs: {rich_outputs}")
else:
    print("rich_outputs: <none>")
