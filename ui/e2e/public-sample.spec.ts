import { test, expect } from '@playwright/test';

/**
 * E2E test for public shared sample run.
 *
 * This test verifies that the public shared sample at /shared/samples/nls_bmi
 * loads correctly without requiring authentication.
 */
test.describe('Public shared sample', () => {
    test('loads nls_bmi sample run', async ({ page }) => {
        // Navigate to the public shared sample
        await page.goto('/shared/samples/nls_bmi');

        // Wait for the page to load
        await page.waitForLoadState('networkidle');

        // Verify the page title/header contains run information
        // Look for the actual run title or status
        await expect(page.locator('body')).toContainText(/National Longitudinal Survey|Spending behavior/i);

        // Verify no authentication error
        await expect(page.locator('body')).not.toContainText(/Please log in/i);

        // Verify experiments table or content loads
        // Check for either the experiments table or loading state
        const hasTable = await page.locator('[role="grid"]').count() > 0;
        const hasLoading = await page.locator('text=/loading/i').count() > 0;

        expect(hasTable || hasLoading).toBeTruthy();

        // Verify no JavaScript errors occurred
        const errors: string[] = [];
        page.on('pageerror', (error) => errors.push(error.message));

        await page.waitForTimeout(2000);
        expect(errors).toHaveLength(0);
    });
});
