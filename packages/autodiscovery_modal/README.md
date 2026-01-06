# AutoDiscovery Modal

Package for using AutoDiscovery on Modal

## Setup

The following environment variables must be set to use Modal

```sh
export MODAL_TOKEN_ID=
export MODAL_TOKEN_SECRET=
export MODAL_IMAGE_BUILDER_VERSION= # Only required for ephemeral runs or deployments
```

## Code Execution

To test remotely (ephemeral run):

```sh
# Displaying Output
uv run modal run -m autodiscovery_modal.ipython_session::main_print --code-str "print('hi')"

# Without Displaying Output
uv run modal run -m autodiscovery_modal.ipython_session --code-str "print('hi')"
```

Note: `run_ipython_cell` returns a dictionary of outputs but does not print them.
Use `main_print` to emit stdout/stderr and rich outputs in the CLI.

To deploy, run the following from the root project:
```sh
just modal-deploy
```
