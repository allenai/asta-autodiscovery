/**
 * Dataset Upload Module
 *
 * Uploads a file with a single PUT and progress tracking via XMLHttpRequest.
 *
 * The destination comes from the API's generate-upload-url call and is either a
 * presigned cloud-storage URL (the upload bypasses our API entirely) or, for
 * storage backends without presigning, a same-origin API path. Only the latter
 * gets an Authorization header: sending our bearer token to a third-party storage
 * host would leak it, and presigned URLs carry their own authorization.
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
    /** Bearer token to attach; only set for same-origin (our own API) uploads. */
    authToken?: string | null;
    onProgress?: (event: UploadProgressEvent) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
    abortSignal?: AbortSignal;
}

/**
 * Upload a file with a single PUT to the URL the API handed back
 *
 * @param options - Upload configuration options
 * @returns Promise that resolves when upload completes or rejects on error
 */
export function uploadToGCS(options: UploadOptions): Promise<void> {
    const {
        file,
        uploadUrl,
        uploadStartTime,
        authToken,
        onProgress,
        onComplete,
        onError,
        abortSignal,
    } = options;

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
        if (authToken) {
            xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        }
        xhr.send(file);
    });
}
