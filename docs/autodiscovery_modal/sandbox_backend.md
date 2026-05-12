# Modal Sandbox Backend

`autodiscovery_modal` provides helpers for running isolated code in Modal
ephemeral sandboxes. Each call creates a fresh sandbox, executes the code, and
terminates the sandbox. No state persists between calls.

The main types re-exported from `asta_sandbox`:

- `ModalEphemeralExecutor`: Async executor that creates a fresh Modal sandbox per `run_code()` call.
- `CloudShare`: Mounts a cloud storage bucket prefix into the sandbox filesystem.
- `build_sandbox_image` / `build_modal_ephemeral_image`: Build Modal images with IPython and optional extra packages.

## Usage Examples

### Basic execution

```python
import asyncio
from autodiscovery_modal import ModalEphemeralExecutor, build_sandbox_image

image = build_sandbox_image(extra_packages=["numpy", "pandas", "matplotlib", "matplotlib-inline"])

executor = ModalEphemeralExecutor(app_name="my-app", image=image)

async def main():
    await executor.start()
    result = await executor.run_code("print('hello')\n1 + 1")
    print(result.stdout)
    print(result.success)
    await executor.shutdown()

asyncio.run(main())
```

### Execution with a GCS bucket mount

```python
import asyncio
import modal
from autodiscovery_modal import ModalEphemeralExecutor, CloudShare, build_sandbox_image

image = build_sandbox_image(extra_packages=["pandas"])

cloud_share = CloudShare(
    dest="/data",
    bucket="my-bucket",
    key_prefix="datasets/my-dataset/",
    read_only=True,
    bucket_endpoint_url="https://storage.googleapis.com",
    modal_secret=modal.Secret.from_name("gcs-my-bucket"),
)

executor = ModalEphemeralExecutor(
    app_name="my-app",
    image=image,
    environment={"DATASET_ROOT": "/data"},
)

async def main():
    await executor.start()
    await executor.add_shares(cloud_share)
    result = await executor.run_code(
        "import os, pathlib; print(list(pathlib.Path(os.environ['DATASET_ROOT']).iterdir()))"
    )
    print(result.stdout)
    await executor.shutdown()

asyncio.run(main())
```

### Capturing matplotlib figures

Figures produced by `plt.show()` are returned as `rich_outputs` on the result:

```python
import asyncio
from autodiscovery_modal import ModalEphemeralExecutor, build_sandbox_image

image = build_sandbox_image(extra_packages=["matplotlib", "matplotlib-inline"])

executor = ModalEphemeralExecutor(app_name="my-app", image=image)

async def main():
    await executor.start()
    result = await executor.run_code(
        "import matplotlib.pyplot as plt\nplt.plot([1,2,3])\nplt.show()"
    )
    for ro in result.rich_outputs:
        if "image/png" in ro.data:
            print("Got PNG figure")
    await executor.shutdown()

asyncio.run(main())
```

## Notes

- Each `run_code()` call creates a new sandbox. No variables, imports, or data
  persist between calls.
- `CloudShare` mounts are scoped per executor instance. Call `add_shares()`
  before `run_code()`.
- Use `build_sandbox_image(extra_packages=[...])` to bake in Python packages.
  Modal caches image layers by content hash, so unchanged images are free to reuse.
- For the full `asta_sandbox` API (including `SandboxBase`, `ExecutionResult`,
  `RichOutput`), see the [asta-sandbox package](https://pypi.org/project/asta-sandbox/).
