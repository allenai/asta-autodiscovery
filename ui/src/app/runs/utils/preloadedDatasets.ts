export interface PreloadedDataset {
    /** Unique identifier for this dataset */
    id: string;
    /** Display name shown in the UI */
    label: string;
    /** Filename as it will appear in the run */
    filename: string;
    /** Pre-filled dataset schema description */
    description: string;
    /** S3 URL where the dataset is hosted */
    url: string;
}
const datasetDescription =
    '## Data Structure (h5ad Format)\n' +
    '\n' +
    'All files use the AnnData format (`.h5ad`), compatible with [scanpy](https://scanpy.readthedocs.io/) and other single-cell analysis tools.\n' +
    '\n' +
    '### Observation (Cell) Metadata (51 columns)\n' +
    '\n' +
    'Key columns include:\n' +
    '- **Cell Identity:** `cell_type`, `cell_type_ontology_term_id`, `compartment`, `broad_cell_class`\n' +
    '- **Donor Information:** `donor_id`, `sex`, `sex_ontology_term_id`, `development_stage`, `self_reported_ethnicity`\n' +
    '- **Sample Information:** `sample_id`, `tissue`, `tissue_in_publication`, `anatomical_position`\n' +
    '- **Technical:** `assay`, `assay_ontology_term_id`, `method`, `10X_run`\n' +
    '- **QC Metrics:** `n_genes_by_counts`, `total_counts`, `pct_counts_mt`, `pct_counts_ercc`\n' +
    '- **Analysis:** `_scvi_batch`, `_scvi_labels`, `scvi_leiden_donorassay_full`\n' +
    '\n' +
    '### Variable (Gene) Metadata (16 columns)\n' +
    '\n' +
    '- **Gene IDs:** `ensembl_id`, `feature_name`\n' +
    '- **Gene Info:** `feature_biotype`, `feature_length`, `genome`\n' +
    '- **QC Stats:** `n_cells_by_counts`, `mean_counts`, `total_counts`, `pct_dropout_by_counts`\n' +
    '- **Technical:** `mt` (mitochondrial), `ercc` (spike-in), `feature_is_filtered`\n' +
    '\n' +
    '### Embeddings & Dimensionality Reductions (`obsm`)\n' +
    '\n' +
    '- `X_pca` - Principal Component Analysis\n' +
    '- `X_scvi` - scVI latent representation (batch-corrected)\n' +
    '- `X_umap` - UMAP embedding (primary)\n' +
    '- `X_umap_scvi_full_donorassay` - UMAP on scVI latent space\n' +
    '- `X_umap_tissue_scvi_donorassay` - Tissue-specific scVI UMAP\n' +
    '- `X_tissue_uncorrected_umap` - Uncorrected UMAP\n' +
    '- `X_uncorrected_umap` - Uncorrected UMAP (alternate)\n' +
    '\n' +
    '### Layers\n' +
    '\n' +
    '- **`decontXcounts`** - Ambient RNA-corrected counts (decontX)\n' +
    '- **`scale_data`** - Scaled/normalized expression';

export const PRELOADED_DATASETS: PreloadedDataset[] = [
    {
        id: 'tabula-sapiens-heart',
        label: 'Tabula Sapiens - Heart',
        filename: 'heart.h5ad',
        description: datasetDescription,
        url: 'gs://ai2-autodiscovery-public/CELLxGENE/heart.h5ad',
    },
    {
        id: 'tabula-sapiens-kidney',
        label: 'Tabula Sapiens - Kidney',
        filename: 'kidney.h5ad',
        description: datasetDescription,
        url: 'gs://ai2-autodiscovery-public/CELLxGENE/kidney.h5ad',
    },
    {
        id: 'tabula-sapiens-lung',
        label: 'Tabula Sapiens - Lung',
        filename: 'lung.h5ad',
        description: datasetDescription,
        url: 'gs://ai2-autodiscovery-public/CELLxGENE/lung.h5ad',
    },
];
