/**
 * GCS Upload Module
 *
 * Handles direct uploads to Google Cloud Storage using presigned URLs
 * with progress tracking via XMLHttpRequest.
 */

export interface UploadProgressEvent {
    progress: number; // 0-100
    uploadedBytes: number;
    totalBytes: number;
    secondsRemaining: number | null; // seconds, null while calculating
}

export interface UploadOptions {
    file: File;
    uploadUrl: string;
    uploadStartTime: number;
    onProgress?: (event: UploadProgressEvent) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
    abortSignal?: AbortSignal;
}

/**
 * Upload a file directly to GCS using a presigned URL
 *
 * @param options - Upload configuration options
 * @returns Promise that resolves when upload completes or rejects on error
 */
export function uploadToGCS(options: UploadOptions): Promise<void> {
    const { file, uploadUrl, uploadStartTime, onProgress, onComplete, onError, abortSignal } =
        options;

    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();

        // Track upload progress
        xhr.upload.addEventListener('progress', (event) => {
            if (event.lengthComputable && onProgress) {
                const progress = (event.loaded / event.total) * 100;
                const uploadedBytes = event.loaded;

                // Calculate time remaining
                const elapsedTime = (Date.now() - uploadStartTime) / 1000; // seconds
                const uploadSpeed = uploadedBytes / elapsedTime; // bytes per second
                const remainingBytes = event.total - uploadedBytes;
                const secondsRemaining = uploadSpeed > 0 ? remainingBytes / uploadSpeed : null;

                onProgress({
                    progress,
                    uploadedBytes,
                    totalBytes: event.total,
                    secondsRemaining,
                });
            }
        });

        // Handle successful completion
        xhr.addEventListener('load', () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                onComplete?.();
                resolve();
            } else {
                const error = new Error(`Upload failed with status ${xhr.status}`);
                onError?.(error);
                reject(error);
            }
        });

        // Handle errors
        xhr.addEventListener('error', () => {
            const error = new Error('Network error during upload');
            onError?.(error);
            reject(error);
        });

        // Handle abort
        xhr.addEventListener('abort', () => {
            const error = new Error('Upload cancelled');
            onError?.(error);
            reject(error);
        });

        // Setup abort signal if provided
        if (abortSignal) {
            abortSignal.addEventListener('abort', () => {
                xhr.abort();
            });
        }

        // Open connection and send
        xhr.open('PUT', uploadUrl, true);
        xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
        xhr.send(file);
    });
}
