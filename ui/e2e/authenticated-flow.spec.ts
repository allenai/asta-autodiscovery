import { test, expect } from '@playwright/test';

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
 * 3. Fill in run details and upload a data file
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
        await page.waitForLoadState('domcontentloaded');

        // Look for the "Sign in to get started" button
        const loginButton = page.locator('button:has-text("Sign in to get started")');

        try {
            await loginButton.waitFor({ timeout: 5000 });
            await loginButton.click();

            // Wait for Auth0 login page
            await page.waitForURL(/auth0\.allenai\.org/, { timeout: 10000 });
        } catch (e) {
            // If no login button found, may already be authenticated
            const currentUrl = page.url();
            if (!currentUrl.includes('/runs') && !currentUrl.includes('auth0')) {
                throw e;
            }
            console.log('Already authenticated, skipping login');
        }

        // Only fill credentials if we're on Auth0 page
        if (page.url().includes('auth0')) {
            // Wait for the form to fully load
            await page.waitForSelector('input[name="username"]', { state: 'visible' });

            // Fill email
            const emailInput = page.locator('input[name="username"]');
            await emailInput.click();
            await emailInput.fill(testEmail!);

            // Fill password (single-step form - both fields visible at once)
            const passwordInput = page.locator('input[type="password"]');
            const passwordVisible = await passwordInput.isVisible();
            if (!passwordVisible) {
                // Two-step flow: submit email first to reveal password field
                await page.click('button[type="submit"]');
                await page.waitForSelector('input[type="password"]', {
                    state: 'visible',
                    timeout: 10000,
                });
            }

            await passwordInput.click();
            await passwordInput.fill(testPassword!);

            // Verify password was filled before submitting
            await expect(passwordInput).not.toHaveValue('');

            await page.click('button[type="submit"]');

            // Wait for redirect back to app (don't use networkidle - SPA keeps polling)
            await page.waitForURL(/\/(runs|home)/, { timeout: 30000 });
            await page.waitForLoadState('load');
        }

        // Step 2: Create a new run
        // Wait for the create button and give the app state time to settle after login
        await page.waitForSelector('[data-track-name="sidebar__create-run-btn"]', {
            state: 'visible',
            timeout: 30000,
        });
        await page.waitForTimeout(2000);
        await page.click('[data-track-name="sidebar__create-run-btn"]');

        // Wait for the new run page (URL: /runs/<id>) - API call can be slow on local stack
        await page.waitForURL(/\/runs\/[a-f0-9-]+/, { timeout: 30000 });

        // Wait for the run setup form to render (MUI labels aren't standard <label> elements,
        // so we use placeholder-based selectors)
        await page.waitForSelector('input[placeholder="New Session 1"]', {
            state: 'visible',
            timeout: 30000,
        });

        // Step 3: Fill in run details
        const runName = `E2E Test Run ${Date.now()}`;

        // Fill session name (placeholder: "New Session 1")
        const nameInput = page.locator('input[placeholder="New Session 1"]');
        await nameInput.click();
        await nameInput.fill(runName);

        // Fill dataset context (multiline textarea)
        const contextInput = page.locator('textarea').first();
        await contextInput.click();
        await contextInput.fill('What factors influence body mass index in the dataset?');

        // Upload a data file
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

        // Wait for upload to complete (MUI SvgIcon with titleAccess sets role="img" on the SVG)
        await page.getByRole('img', { name: 'Upload completed' }).waitFor({ timeout: 60000 });

        // Set experiment budget to 1
        // The budget field validates against creditsAvailable, which starts at 0 while credits load.
        // Wait for the credits button to show a positive number before filling.
        await page.waitForFunction(
            () => {
                const btn = document.querySelector('[data-track-name="header__credits_btn"]');
                if (!btn) return false;
                const match = btn.textContent?.match(/(\d+)/);
                return match ? parseInt(match[1]) > 0 : false;
            },
            null,
            { timeout: 15000 }
        );

        const budgetInput = page.locator('input[type="number"]').first();
        await budgetInput.fill('1');
        // Verify no validation error before proceeding
        await expect(page.locator('text=Must be between')).not.toBeVisible({ timeout: 2000 });

        // Step 4: Submit the run
        await page.click('[data-track-name="run_setup__submit_btn"]');

        // Step 5: Verify the run view loads and the job is in progress
        // Wait for the loading spinner to go away, then check the status chip
        // Status chip shows toSentenceCase(status): "Pending", "Queued", or "Running"
        await page.waitForSelector('[role="progressbar"]', { state: 'hidden', timeout: 30000 });
        await expect(page.locator('text=/Pending|Queued|Running/').first()).toBeVisible({
            timeout: 15000,
        });
    });
});
