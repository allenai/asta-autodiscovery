import { test, expect } from '@playwright/test';
import { expectExternalLink, waitForExperimentsLoaded } from './helpers';
import {
    TEST_ID_SIGN_IN_BUTTON,
    TEST_ID_FEEDBACK_BUTTON,
    TEST_ID_ABOUT_BUTTON,
    TEST_ID_CREDITS_CHIP,
    TEST_ID_TOP_SURPRISALS_ITEM,
    TEST_ID_EXPERIMENT_GRAPH,
    TEST_ID_EXPERIMENT_DETAILS_PANEL,
    TEST_ID_EXPERIMENT_DETAILS_CLOSE,
} from '../src/app/testIds';

const DETAILS_URLS = [
    '/shared/samples/nls_bmi?exp=100',
    '/runs/shared/353800d1-9e6e-40c1-a241-2169ed1a9b7d?exp=2',
];

for (const url of DETAILS_URLS) {
    test.describe(`Details page: ${url}`, () => {
        test.beforeEach(async ({ page }) => {
            await page.goto(url);
            await waitForExperimentsLoaded(page);
        });

        test('page loads with experiment pre-selected', async ({ page }) => {
            // No visible error toasts
            await expect(page.locator('.MuiAlert-filledError')).toHaveCount(0);

            // More than one surprisal in list — wait for job to complete
            const surprisalItems = page.locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"]`);
            await expect(surprisalItems.first()).toBeVisible({ timeout: 30000 });
            expect(await surprisalItems.count()).toBeGreaterThan(0);

            // More than one experiment in table
            const tableRows = page.locator('.MuiDataGrid-row:not([data-id^="skeleton"])');
            expect(await tableRows.count()).toBeGreaterThan(1);

            // More than one node in tree
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            await expect(graphContainer).toBeVisible();
            const treeNodes = graphContainer.locator('circle.node');
            await expect(treeNodes.first()).toBeVisible({ timeout: 15000 });
            expect(await treeNodes.count()).toBeGreaterThan(1);

            // A table row is highlighted
            expect(await page.locator('.MuiDataGrid-row.Mui-selected').count()).toBeGreaterThan(0);

            // A surprisal is highlighted (data-selected="true")
            const selectedSurprisal = page.locator(
                `[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"][data-selected="true"]`
            );
            expect(await selectedSurprisal.count()).toBeGreaterThan(0);

            // A tree node is highlighted (green stroke)
            const selectedNode = graphContainer.locator('circle.node[stroke="#0FCB8C"]');
            expect(await selectedNode.count()).toBeGreaterThan(0);

            // Details panel is open
            await expect(
                page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_PANEL}"]`)
            ).toBeVisible();
        });

        test('sign in button links to auth.example.com', async ({ page }) => {
            const signInBtn = page.locator(`[data-test-id="${TEST_ID_SIGN_IN_BUTTON}"]`);
            await expect(signInBtn).toBeVisible();

            const requestPromise = page.waitForRequest(
                (req) => req.url().includes('auth.example.com'),
                { timeout: 10000 }
            );
            await signInBtn.click();
            const request = await requestPromise;
            expect(request.url()).toContain('auth.example.com');
        });

        test('feedback button opens page without error', async ({ page, context }) => {
            const feedbackLink = page.locator(`[data-test-id="${TEST_ID_FEEDBACK_BUTTON}"]`);
            await expect(feedbackLink).toBeVisible();
            await expectExternalLink(context, feedbackLink, 'google.com');
        });

        test('About button opens page on allenai.org', async ({ page, context }) => {
            const aboutLink = page.locator(`[data-test-id="${TEST_ID_ABOUT_BUTTON}"]`);
            await expect(aboutLink).toBeVisible();
            await expectExternalLink(context, aboutLink, 'allenai.org');
        });

        test('header does not show credits', async ({ page }) => {
            await expect(page.locator(`[data-test-id="${TEST_ID_CREDITS_CHIP}"]`)).toHaveCount(0);
        });

        test('closing details panel clears all selection state', async ({ page }) => {
            // Panel should be open initially
            const detailsPanel = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_PANEL}"]`);
            await expect(detailsPanel).toBeVisible();

            // Close via the X button
            const closeBtn = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_CLOSE}"]`);
            await closeBtn.click();

            // Details panel is gone
            await expect(detailsPanel).toHaveCount(0);

            // No surprisals highlighted
            const selectedSurprisal = page.locator(
                `[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"][data-selected="true"]`
            );
            await expect(selectedSurprisal).toHaveCount(0);

            // No table rows highlighted
            await expect(page.locator('.MuiDataGrid-row.Mui-selected')).toHaveCount(0);

            // No tree nodes highlighted
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            const selectedNode = graphContainer.locator('circle.node[stroke="#0FCB8C"]');
            await expect(selectedNode).toHaveCount(0);
        });
    });
}
