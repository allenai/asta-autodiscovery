'use server';

/**
 * Server actions for runs API communication.
 *
 * These actions handle all communication between the Next.js frontend
 * and the Flask backend API for run management.
 */

const API_ORIGIN = process.env.API_ORIGIN ?? 'http://api:8000';

export interface GetViewerCreditsResponse {
    credits: ViewerCredits;
}
export interface ViewerCredits {
    granted: number; // Total credits granted to the user
    used: number; // Credits used on completed jobs
    pending: number; // Credits in started jobs which have yet to complete
    available: number; // Credits available for new jobs, assuming pending jobs are cancelled
    remaining: number; // Credits available for new jobs, assuming pending jobs are completed
}

/**
 * Fetches the viewer credits for the authenticated user.
 *
 * @param token - Auth0 access token
 * @returns Viewer credits for the authenticated user
 * @throws Error if request fails
 */
export async function getViewerCredits(token: string): Promise<ViewerCredits> {
    const response = await fetch(`${API_ORIGIN}/me/credits`, {
        method: 'GET',
        headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
    });

    if (!response.ok) {
        throw new Error(`Failed to fetch viewer credits: ${response.statusText}`);
    }

    const result: GetViewerCreditsResponse = await response.json();
    return result.credits;
}
