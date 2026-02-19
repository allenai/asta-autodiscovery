import { test, expect } from '@playwright/test';

/**
 * E2E test for public shared sample run.
 *
 * This test verifies that the public shared sample at /shared/samples/nls_bmi
 * loads correctly without requiring authentication.
 */
test.describe('Public shared sample', () => {
    test('loads nls_bmi sample run', async ({ page }) => {
        await page.goto('/shared/samples/nls_bmi');

        // Wait for experiment rows to appear - confirms page fully rendered and API data loaded
        await page.waitForSelector('[data-track-name="run_details__experiment-row"]', {
            timeout: 20000,
        });

        // Verify run status loaded
        await expect(page.locator('text=Succeeded')).toBeVisible();

        // Verify Top Surprisals section rendered
        await expect(page.locator('text=Top Surprisals')).toBeVisible();

        // Click first experiment row and verify Belief Shift chart appears
        await page.locator('[data-track-name="run_details__experiment-row"]').first().click();
        await expect(page.locator('text=Belief Shift')).toBeVisible({ timeout: 10000 });
        await expect(page.locator('.js-plotly-plot')).toBeVisible();
    });
});
