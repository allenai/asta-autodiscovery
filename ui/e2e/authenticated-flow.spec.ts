import { test, expect } from '@playwright/test';
import { Stagehand } from '@browserbasehq/stagehand';
import * as path from 'path';

/**
 * E2E test for authenticated user flow.
 *
 * This test requires the following environment variables:
 * - E2E_TEST_USER: Test user email
 * - E2E_TEST_PASSWORD: Test user password
 * - E2E_TEST_DATAFILE: Path to a test data file (optional, will use a minimal example if not provided)
 *
 * The test performs a complete workflow:
 * 1. Login with test credentials
 * 2. Create a new run
 * 3. Upload a data file
 * 4. Submit the run
 * 5. Wait for completion (with timeout)
 * 6. Verify results view
 */
test.describe('Authenticated user flow', () => {
    test.setTimeout(600000); // 10 minutes - runs can take a while

    test('complete run workflow', async ({ page }) => {
        // Verify required env vars
        const testEmail = process.env.E2E_TEST_USER;
        const testPassword = process.env.E2E_TEST_PASSWORD;

        if (!testEmail || !testPassword) {
            test.skip(
                !testEmail || !testPassword,
                'E2E_TEST_USER and E2E_TEST_PASSWORD must be set'
            );
        }

        // Step 1: Navigate to home and initiate login
        await page.goto('/');

        // Home page redirects to /runs, wait for it to load
        await page.waitForLoadState('networkidle');

        // Look for the "Sign in to get started" button
        const loginButton = page.locator('button:has-text("Sign in to get started")');

        // Wait for either the login button (not authenticated) or the page to load (authenticated)
        try {
            await loginButton.waitFor({ timeout: 5000 });
            await loginButton.click();

            // Wait for Auth0 login page
            await page.waitForURL(/auth0\.allenai\.org/, { timeout: 10000 });
        } catch (e) {
            // If no login button found, we might already be authenticated
            // Check if we're already on the runs page
            const currentUrl = page.url();
            if (!currentUrl.includes('/runs') || currentUrl.includes('auth0')) {
                throw e;
            }
            // Already authenticated, skip login
            console.log('Already authenticated, skipping login');
        }

        // Only fill credentials if we're on Auth0 page
        if (page.url().includes('auth0')) {
            // Use Stagehand to handle Auth0 login with natural language
            const stagehand = new Stagehand({
                env: 'LOCAL',
                apiKey: process.env.ANTHROPIC_API_KEY,
                enableCaching: false,
                headless: false,
            });

            // Initialize Stagehand with the existing page
            await stagehand.init({ cdpUrl: page.context().browser()?.wsEndpoint() });

            // Use natural language to log in
            await stagehand.act({
                action: `Log in with email "${testEmail}" and password "${testPassword}"`,
            });

            // Wait for redirect back to app
            await page.waitForURL(/\/(runs|home)/, { timeout: 20000 });
            await page.waitForLoadState('networkidle');

            // Clean up Stagehand
            await stagehand.close();
        }

        // Step 2: Create a new run
        // Click "New Run" or similar button
        await page.click('button:has-text("New Run"), a:has-text("New Run")');

        // Wait for the new run form
        await expect(page).toHaveURL(/\/runs\/[a-f0-9-]+/);

        // Fill in run details
        const runName = `E2E Test Run ${Date.now()}`;
        await page.fill('input[name="name"]', runName);

        // Fill in research question
        await page.fill(
            'textarea[name="research_question"]',
            'What factors influence body mass index in the dataset?'
        );

        // Step 3: Upload a test data file
        // Create a minimal test CSV if no file provided
        const testDataFile = process.env.E2E_TEST_DATAFILE;
        const fileInput = page.locator('input[type="file"]');

        if (testDataFile) {
            await fileInput.setInputFiles(testDataFile);
        } else {
            // Create a minimal CSV for testing
            const minimalCsv = Buffer.from(
                'id,age,height,weight,bmi\n' +
                    '1,25,170,70,24.2\n' +
                    '2,30,165,65,23.9\n' +
                    '3,35,180,85,26.2\n' +
                    '4,40,175,75,24.5\n' +
                    '5,45,160,60,23.4\n'
            );
            await fileInput.setInputFiles({
                name: 'test-data.csv',
                mimeType: 'text/csv',
                buffer: minimalCsv,
            });
        }

        // Wait for file upload to complete
        await expect(page.locator('text=/uploaded|ready/i')).toBeVisible({ timeout: 30000 });

        // Step 4: Submit the run
        await page.click('button:has-text("Submit"), button:has-text("Start Run")');

        // Wait for submission confirmation
        await page.waitForURL(/\/runs/);

        // Step 5: Navigate to the run details and wait for completion
        // The URL should now be at the run details page
        await expect(page.locator('text=/running|pending|queued/i')).toBeVisible({
            timeout: 10000,
        });

        // Poll for completion (check every 30 seconds, timeout after 8 minutes)
        let completed = false;
        const maxWaitTime = 8 * 60 * 1000; // 8 minutes
        const pollInterval = 30000; // 30 seconds
        const startTime = Date.now();

        while (!completed && Date.now() - startTime < maxWaitTime) {
            await page.reload();
            await page.waitForLoadState('networkidle');

            // Check if run is completed (look for success or failure status)
            const statusText = await page.textContent('body');
            if (
                statusText?.match(/succeeded|completed|failed/i) &&
                !statusText?.match(/running|pending|queued/i)
            ) {
                completed = true;
            } else {
                await page.waitForTimeout(pollInterval);
            }
        }

        expect(completed).toBeTruthy();

        // Step 6: Verify results view
        // Check that we see experiments
        await expect(page.locator('text=/experiment/i')).toBeVisible();

        // Verify experiments table is present
        await expect(page.locator('[role="grid"]')).toBeVisible({ timeout: 10000 });

        // Verify we can see experiment data (hypothesis, surprisal, etc.)
        const hasData =
            (await page.locator('text=/hypothesis/i').count()) > 0 ||
            (await page.locator('text=/surprisal/i').count()) > 0;

        expect(hasData).toBeTruthy();

        // Verify no JavaScript errors
        const errors: string[] = [];
        page.on('pageerror', (error) => errors.push(error.message));

        await page.waitForTimeout(2000);
        expect(errors).toHaveLength(0);
    });
});
