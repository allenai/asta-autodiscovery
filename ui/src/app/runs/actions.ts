'use server';

/**
 * Server actions for runs API communication.
 *
 * These actions handle all communication between the Next.js frontend
 * and the Flask backend API for run management.
 */

const API_ORIGIN = process.env.API_ORIGIN ?? 'http://api:8000';

export interface RunDetails {
    execution_id: string | null;
    created_at: string;
    status: string;
    status_checked_at: string | null;
}

export interface Run {
    runid: string;
    title?: string;
    path?: string;
    run_details?: RunDetails;
}

export interface UploadDatasetResponse {
    path: string;
    filename: string;
    message: string;
}

export interface SubmitRunResponse {
    execution_id: string;
    message: string;
}

export interface ApiError {
    error: string;
}

/**
 * Delete a run and all its contents.
 *
 * @param runid - Run identifier
 * @param token - Auth0 access token
 * @returns Success message
 * @throws Error if request fails
 */
export async function deleteRun(runid: string, token: string): Promise<{ message: string }> {
    const response = await fetch(`${API_ORIGIN}/api/runs/${runid}`, {
        method: 'DELETE',
        headers: {
            Authorization: `Bearer ${token}`,
        },
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.error || 'Failed to delete run');
    }

    return await response.json();
}

/**
 * Upload a dataset file for a run.
 *
 * @param formData - FormData containing file and runid
 * @param token - Auth0 access token
 * @returns Upload confirmation
 * @throws Error if request fails
 */
export async function uploadDataset(
    formData: FormData,
    token: string
): Promise<UploadDatasetResponse> {
    const response = await fetch(`${API_ORIGIN}/api/runs/upload-dataset`, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
        },
        body: formData,
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.error || 'Failed to upload dataset');
    }

    return await response.json();
}

/**
 * Save or update metadata for a run.
 *
 * @param runid - Run identifier
 * @param metadata - Metadata object
 * @param token - Auth0 access token
 * @returns Save confirmation
 * @throws Error if request fails
 */
export async function saveMetadata(
    runid: string,
    metadata: Record<string, unknown>,
    token: string
): Promise<{ path: string; message: string }> {
    const response = await fetch(`${API_ORIGIN}/api/runs/metadata`, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ runid, metadata }),
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.error || 'Failed to save metadata');
    }

    return await response.json();
}

/**
 * Submit a run for execution.
 *
 * @param runid - Run identifier
 * @param params - Run parameters
 * @param token - Auth0 access token
 * @returns Execution ID
 * @throws Error if request fails
 */
export async function submitRun(
    runid: string,
    params: {
        n_experiments?: number;
        model?: string;
        belief_model?: string;
        [key: string]: unknown;
    },
    token: string
): Promise<SubmitRunResponse> {
    const response = await fetch(`${API_ORIGIN}/api/runs/submit`, {
        method: 'POST',
        headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ runid, ...params }),
    });

    if (!response.ok) {
        const error: ApiError = await response.json();
        throw new Error(error.error || 'Failed to submit run');
    }

    return await response.json();
}
