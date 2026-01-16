'use server';

/**
 * Server actions for runs API communication.
 *
 * These actions handle all communication between the Next.js frontend
 * and the Flask backend API for run management.
 */

const API_ORIGIN = process.env.API_ORIGIN ?? 'http://api:8000';

export interface ViewerCredits {
  credits_granted: number;
  credits_used: number;
  credits_remaining: number;
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

  return response.json() as Promise<ViewerCredits>;
}
