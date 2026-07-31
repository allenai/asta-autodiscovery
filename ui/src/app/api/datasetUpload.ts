/**
 * Dataset Upload Module
 *
 * Uploads a dataset file with progress tracking. Uses XMLHttpRequest rather than
 * fetch because only XHR reports upload progress, which the run-setup UI displays.
 *
 * There are two destinations, decided by whether generate-upload-url gave us a
 * presigned URL:
 *
 * - `uploadUrl` set — PUT the bytes straight to cloud storage, bypassing our API.
 *   No Authorization header: the presigned URL carries its own, and sending our
 *   bearer token to a third-party host would leak it.
 * - `uploadUrl` null — the backend has no presigning, so POST the file as
 *   multipart to our own authenticated upload endpoint.
 *
 * Both live here so callers just forward `upload_url` and never decide where it is
 * safe to send credentials.
 */

import { authBridge } from '@/auth/authBridge';

/** Endpoint that receives uploads when the storage backend cannot presign. */
const API_UPLOAD_PATH = '/api/runs/upload-dataset';

export interface UploadProgressEvent {
    progress: number; // 0-100
    uploadedBytes: number;
    totalBytes: number;
    secondsRemaining: number | null; // seconds, null while calculating
}

export interface UploadOptions {
    file: File;
    /** Presigned URL from generate-upload-url, or null to upload via our API. */
    uploadUrl: string | null;
    /** Run the file belongs to; needed for the API upload path. */
    runid: string;
    uploadStartTime: number;
    onProgress?: (event: UploadProgressEvent) => void;
    onComplete?: () => void;
    onError?: (error: Error) => void;
    abortSignal?: AbortSignal;
}

/**
 * Upload a dataset file, direct to storage when possible and through our API otherwise
 *
 * @param options - Upload configuration options
 * @returns Promise that resolves when upload completes or rejects on error
 */
export async function uploadDatasetFile(options: UploadOptions): Promise<void> {
    const {
        file,
        uploadUrl,
        runid,
        uploadStartTime,
        onProgress,
        onComplete,
        onError,
        abortSignal,
    } = options;

    // Only fetched for the API path; a presigned URL must not receive our token.
    const authToken = uploadUrl ? null : await authBridge.getToken().catch(() => null);

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
        if (uploadUrl) {
            xhr.open('PUT', uploadUrl, true);
            xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
            xhr.send(file);
        } else {
            const form = new FormData();
            form.append('file', file);
            form.append('runid', runid);
            xhr.open('POST', API_UPLOAD_PATH, true);
            if (authToken) {
                xhr.setRequestHeader('Authorization', `Bearer ${authToken}`);
            }
            // Content-Type is deliberately unset: the browser adds the multipart
            // boundary, which we cannot compute here.
            xhr.send(form);
        }
    });
}
