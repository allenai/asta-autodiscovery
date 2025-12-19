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
uv run modal run -m autodiscovery_modal.ipython_session::app.run_ipython_cell --code-str "print('hi')"
```

To deploy, run the following from the root project:
```sh
uv run deploy-modal
```