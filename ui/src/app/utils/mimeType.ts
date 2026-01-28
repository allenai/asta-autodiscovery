const EXT_TO_MIME: Record<string, string> = {
    // Text-based tabular formats
    csv: 'text/csv',
    tsv: 'text/tab-separated-values',
    txt: 'text/plain',

    // JSON formats
    json: 'application/json',
    jsonl: 'application/jsonl',
    ndjson: 'application/x-ndjson',

    // Spreadsheet formats
    xls: 'application/vnd.ms-excel',
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ods: 'application/vnd.oasis.opendocument.spreadsheet',

    // XML formats
    xml: 'application/xml',

    // Columnar & big data formats
    parquet: 'application/vnd.apache.parquet',
    avro: 'application/vnd.apache.avro',
    orc: 'application/octet-stream',

    // Compressed formats
    gz: 'application/gzip',
    gzip: 'application/gzip',
    zip: 'application/zip',
    bz2: 'application/x-bzip2',
    tar: 'application/x-tar',

    // Database formats
    sqlite: 'application/x-sqlite3',
    sqlite3: 'application/vnd.sqlite3',
    db: 'application/x-sqlite3',

    // Scientific data formats
    hdf: 'application/x-hdf',
    h5: 'application/x-hdf',
    nc: 'application/x-netcdf',

    // Other structured formats
    yaml: 'text/yaml',
    yml: 'text/yaml',
    toml: 'application/toml',
};

const MIME_TO_FRIENDLY: Record<string, string> = {
    // Text-based tabular formats
    'text/csv': 'CSV',
    'text/tab-separated-values': 'TSV',
    'text/plain': 'TXT',

    // JSON formats
    'application/json': 'JSON',
    'application/jsonl': 'JSON-L',
    'application/json-l': 'JSON-L',
    'application/x-jsonlines': 'JSON-L',
    'application/x-ndjson': 'NDJSON',

    // Spreadsheet formats
    'application/vnd.ms-excel': 'XLS',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
    'application/vnd.oasis.opendocument.spreadsheet': 'ODS',

    // XML formats
    'application/xml': 'XML',
    'text/xml': 'XML',

    // Columnar & big data formats
    'application/vnd.apache.parquet': 'Parquet',
    'application/x-parquet': 'Parquet',
    'application/vnd.apache.avro': 'Avro',
    'application/octet-stream': 'Binary',

    // Compressed formats
    'application/gzip': 'GZIP',
    'application/x-gzip': 'GZIP',
    'application/zip': 'ZIP',
    'application/x-bzip2': 'BZIP2',
    'application/x-tar': 'TAR',

    // Database formats
    'application/x-sqlite3': 'SQLite',
    'application/vnd.sqlite3': 'SQLite',

    // Scientific data formats
    'application/x-hdf': 'HDF',
    'application/x-netcdf': 'NetCDF',

    // Other structured formats
    'text/yaml': 'YAML',
    'application/x-yaml': 'YAML',
    'application/toml': 'TOML',
};

export function getMimeType(filename: string): string {
    const parts = filename.toLowerCase().split('.');
    if (parts.length < 2) {
        return 'application/octet-stream';
    }

    const ext = parts[parts.length - 1];
    const compressionExts = ['gz', 'gzip', 'zip', 'bz2', 'tar'];

    // Check if the file is compressed and has a content type extension before the compression
    if (parts.length >= 3 && compressionExts.includes(ext)) {
        const contentExt = parts[parts.length - 2];
        const contentMime = EXT_TO_MIME[contentExt];

        // If we recognize the content type, return it (e.g., csv.gz -> text/csv)
        if (contentMime) {
            return contentMime;
        }
    }

    return EXT_TO_MIME[ext] ?? 'application/octet-stream';
}

export function getFriendlyMimeType(mimeType: string): string {
    return MIME_TO_FRIENDLY[mimeType] ?? mimeType.split('/').pop();
}
