# Devtools

Developer Tools for AutoDiscovery

## ADK Web

Run from the repo root:

```bash
just adk-web
```

Or directly:

```bash
uv run adk web packages/devtools/adk --port 8000
```

## CLI

### Running Code with IPython Session

You can run Python code in an IPython session using the following command:

```sh
uv run --project packages/devtools ipython-session --code "print('Hello World!')"
```

You can also run code that uses external libraries, such as matplotlib:

```sh
uv run --project packages/devtools ipython-session --code "import matplotlib.pyplot as plt; plt.plot([1,2,3], [4,5,6]); plt.show()"
```