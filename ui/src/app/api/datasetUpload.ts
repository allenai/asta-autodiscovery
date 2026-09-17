/**
 * Dataset Upload Module
 *
 * Performs the upload request that `generate-upload-url` describes, with progress
 * tracking. Uses XMLHttpRequest rather than fetch because only XHR reports upload
 * progress, which the run-setup UI displays.
 *
 * The destination may be cloud storage (a presigned URL, bypassing our API) or our
 * own API, and this module does not need to know which: the response carries the
 * url, method, and any form fields. The one thing decided here is credentials —
 * our bearer token is attached only when the destination is our own origin, since
 * sending it to a third-party storage host would leak it. That rule is deliberately
 * the client's own and not something the server can ask for.
 */

import { authBridge } from '@/auth/authBridge';

export interface UploadProgressEvent {
    progress: number; // 0-100
    uploadedBytes: number;
    totalBytes: number;
    secondsRemaining: number | null; // seconds, null while calculating
}

/** The upload request to perform, as described by generate-upload-url. */
export interface UploadTarget {
    url: string;
    method: string;
    /** When set, send multipart/form-data with these fields plus the file. */
    fields?: Record<string, string> | null;
}

export interface UploadOptions {
    file: File;
    target: UploadTarget;
    uploadStartTime: number;
    onProgress?: (event: UploadProgressEvent) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
    abortSignal?: AbortSignal;
}

/**
 * Perform the described upload request
 *
 * @param options - Upload configuration options
 * @returns Promise that resolves when upload completes or rejects on error
 */
export async function uploadDatasetFile(options: UploadOptions): Promise<void> {
    const { file, target, uploadStartTime, onProgress, onComplete, onError, abortSignal } = options;

    // Resolves relative URLs (our own API) as well as absolute ones (cloud storage).
    const url = new URL(target.url, window.location.origin);
    const authToken =
        url.origin === window.location.origin
            ? await authBridge.getToken().catch(() => null)
            : null;

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
        xhr.open(target.method, url.toString(), true);
        if (authToken) {
            xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
        }

        if (target.fields) {
            const form = new FormData();
            // Fields precede the file: presigned POST policies require that ordering.
            Object.entries(target.fields).forEach(([name, value]) => form.append(name, value));
            form.append('file', file);
            // Content-Type is deliberately unset: the browser adds the multipart
            // boundary, which we cannot compute here.
            xhr.send(form);
        } else {
            xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
            xhr.send(file);
        }
    });
}
