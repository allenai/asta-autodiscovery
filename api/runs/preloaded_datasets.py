"""The preloaded datasets this API publishes, and the only ones submit copies in.

A run names a preloaded dataset in its metadata by ``preloaded_id``. Submit
copies it into the run with this service's own storage credentials, so the
source and the filename it lands under always come from this registry, never
from the metadata. Runs saved before ids existed name one by its ``gs://`` URL,
which is looked up here the same way.

The UI's picker (``ui/src/app/runs/utils/preloadedDatasets.ts``) lists the same
ids.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreloadedDataset:
    id: str
    #: The name the file lands under in the run, which the agent reads.
    filename: str
    #: Where submit copies it from.
    source: str


class UnknownPreloadedDatasetError(ValueError):
    """A dataset entry names a preloaded dataset this API doesn't publish."""


_CELLXGENE = "gs://ai2-autodiscovery/public/CELLxGENE"

PRELOADED_DATASETS: dict[str, PreloadedDataset] = {
    d.id: d
    for d in (
        PreloadedDataset("tabula-sapiens-heart", "heart.h5ad", f"{_CELLXGENE}/heart.h5ad"),
        PreloadedDataset("tabula-sapiens-kidney", "kidney.h5ad", f"{_CELLXGENE}/kidney.h5ad"),
        PreloadedDataset("tabula-sapiens-lung", "lung.h5ad", f"{_CELLXGENE}/lung.h5ad"),
    )
}

_BY_SOURCE = {d.source: d for d in PRELOADED_DATASETS.values()}


def resolve(dataset: dict) -> PreloadedDataset | None:
    """The preloaded dataset a metadata entry names, or None for an upload.

    An entry names one by ``preloaded_id``, or (saved before ids) by a ``gs://``
    ``url``. Raises UnknownPreloadedDatasetError when it names one this API
    doesn't publish.
    """
    preloaded_id = dataset.get("preloaded_id")
    if preloaded_id:
        if preloaded_id not in PRELOADED_DATASETS:
            raise UnknownPreloadedDatasetError(f"No preloaded dataset '{preloaded_id}'")
        return PRELOADED_DATASETS[preloaded_id]

    url = dataset.get("url") or ""
    if url.startswith("gs://"):
        if url not in _BY_SOURCE:
            raise UnknownPreloadedDatasetError(f"{url} is not a preloaded dataset")
        return _BY_SOURCE[url]
    return None


def normalize(dataset: dict) -> dict:
    """A metadata entry with any preloaded dataset it names spelled out in full."""
    preloaded = resolve(dataset)
    if preloaded is None:
        return dataset
    return {
        **dataset,
        "preloaded_id": preloaded.id,
        "name": preloaded.filename,
        "url": preloaded.source,
    }
