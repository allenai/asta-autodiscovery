"""The preloaded datasets a run may copy in from ``gs://``.

A run's metadata names a preloaded dataset by its ``gs://`` URL, and submit
copies it with AutoDiscovery's own service account. Only these URLs are
copied, whoever asks. Keep in step with the UI's picker
(``ui/src/app/runs/utils/preloadedDatasets.ts``).
"""

PRELOADED_DATASET_URLS: frozenset[str] = frozenset(
    {
        "gs://ai2-autodiscovery/public/CELLxGENE/heart.h5ad",
        "gs://ai2-autodiscovery/public/CELLxGENE/kidney.h5ad",
        "gs://ai2-autodiscovery/public/CELLxGENE/lung.h5ad",
    }
)
