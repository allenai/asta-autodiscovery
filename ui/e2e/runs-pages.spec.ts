import { test, expect } from '@playwright/test';
import { expectExternalLink, waitForExperimentsLoaded } from './helpers';
import {
    TEST_ID_SIGN_IN_BUTTON,
    TEST_ID_FEEDBACK_BUTTON,
    TEST_ID_ABOUT_BUTTON,
    TEST_ID_CREDITS_CHIP,
    TEST_ID_BACK_BUTTON,
    TEST_ID_TOP_SURPRISALS_LIST,
    TEST_ID_TOP_SURPRISALS_ITEM,
    TEST_ID_VIEW_ALL_SURPRISALS_BUTTON,
    TEST_ID_SESSION_CONFIG_BUTTON,
    TEST_ID_SESSION_CONFIG_MODAL,
    TEST_ID_EXPERIMENTS_TABLE,
    TEST_ID_EXPERIMENT_GRAPH,
    TEST_ID_EXPERIMENT_GRAPH_ZOOM_IN,
    TEST_ID_EXPERIMENT_GRAPH_ZOOM_OUT,
    TEST_ID_EXPERIMENT_GRAPH_RESET,
    TEST_ID_EXPERIMENT_DETAILS_PANEL,
} from '../src/app/testIds';

const RUN_URLS = [
    '/shared/samples/nls_bmi',
    '/runs/shared/353800d1-9e6e-40c1-a241-2169ed1a9b7d',
];

for (const url of RUN_URLS) {
    test.describe(`Runs page: ${url}`, () => {
        test.beforeEach(async ({ page }) => {
            await page.goto(url);
            await waitForExperimentsLoaded(page);
        });

        test('page loads without error, correct initial state', async ({ page }) => {
            // No visible error toasts
            await expect(page.locator('.MuiAlert-filledError')).toHaveCount(0);

            // More than one surprisal in list — wait for job to complete (TopSurprisalsList
            // only renders after hasJobCompleted === true)
            const surprisalItems = page.locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"]`);
            await expect(surprisalItems).toHaveCount(2, { timeout: 30000 }); // collapsed to 2 by default

            // More than one experiment in table
            const tableRows = page.locator('.MuiDataGrid-row:not([data-id^="skeleton"])');
            expect(await tableRows.count()).toBeGreaterThan(1);

            // More than one node in tree (circles in the SVG)
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            await expect(graphContainer).toBeVisible();
            const treeNodes = graphContainer.locator('circle.node');
            await expect(treeNodes.first()).toBeVisible({ timeout: 15000 });
            expect(await treeNodes.count()).toBeGreaterThan(1);

            // No surprisals highlighted (no data-selected="true")
            const selectedSurprisal = page.locator(
                `[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"][data-selected="true"]`
            );
            await expect(selectedSurprisal).toHaveCount(0);

            // No table rows highlighted
            await expect(page.locator('.MuiDataGrid-row.Mui-selected')).toHaveCount(0);

            // Details panel not open
            await expect(
                page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_PANEL}"]`)
            ).toHaveCount(0);
        });

        test('back button navigates to home page', async ({ page }) => {
            const backBtn = page.locator(`[data-test-id="${TEST_ID_BACK_BUTTON}"]`);
            await expect(backBtn).toBeVisible();
            await Promise.all([page.waitForURL('**/runs'), backBtn.click()]);
            await expect(page).toHaveURL(/\/runs$/);
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

        test('view all surprisals expands and collapses list', async ({ page }) => {
            // TopSurprisalsList only renders after hasJobCompleted; wait for it
            const surprisalsList = page.locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_LIST}"]`);
            await expect(surprisalsList).toBeVisible({ timeout: 30000 });

            const expandBtn = page.locator(
                `[data-test-id="${TEST_ID_VIEW_ALL_SURPRISALS_BUTTON}"]`
            );
            await expect(expandBtn).toBeVisible();

            const collapsedCount = await page
                .locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"]`)
                .count();

            // Expand
            await expandBtn.click();
            const expandedCount = await page
                .locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"]`)
                .count();
            expect(expandedCount).toBeGreaterThan(collapsedCount);

            // Collapse
            await expandBtn.click();
            const reCollapsedCount = await page
                .locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_ITEM}"]`)
                .count();
            expect(reCollapsedCount).toBe(collapsedCount);
        });

        test('session configuration button opens modal which can be closed', async ({ page }) => {
            const configBtn = page.locator(`[data-test-id="${TEST_ID_SESSION_CONFIG_BUTTON}"]`);
            await expect(configBtn).toBeVisible();
            await configBtn.click();

            const modal = page.locator(`[data-test-id="${TEST_ID_SESSION_CONFIG_MODAL}"]`);
            await expect(modal).toBeVisible();

            // Close via the X button inside the modal
            await page.locator('[aria-label="close"]').click();
            await expect(modal).not.toBeVisible();
        });

        test('hypothesis column can be hidden and shown', async ({ page }) => {
            const table = page.locator(`[data-test-id="${TEST_ID_EXPERIMENTS_TABLE}"]`);
            await expect(table).toBeVisible();

            // Open column manager
            const columnsBtn = table.getByRole('button', { name: /columns/i });
            await columnsBtn.click();

            // Toggle Experiment Hypothesis column off — MUI DataGrid v8 uses text items in a panel
            const hypothesisToggle = page.getByText('Experiment Hypothesis').last();
            await hypothesisToggle.click();

            // Column header should be gone
            await expect(
                table.locator('.MuiDataGrid-columnHeader[data-field="hypothesis"]')
            ).toHaveCount(0);

            // Toggle back on
            await hypothesisToggle.click();
            await expect(
                table.locator('.MuiDataGrid-columnHeader[data-field="hypothesis"]')
            ).toBeVisible();

            // Close panel
            await page.keyboard.press('Escape');
        });

        test('table can sort by surprisal ascending then descending', async ({ page }) => {
            const table = page.locator(`[data-test-id="${TEST_ID_EXPERIMENTS_TABLE}"]`);

            // Default sort is surprisal descending after job completes; click to change to ascending
            const surprisalHeader = table.locator(
                '.MuiDataGrid-columnHeader[data-field="surprisal"]'
            );
            await surprisalHeader.click();
            await page.waitForTimeout(300);
            await expect(surprisalHeader).toHaveAttribute('aria-sort', 'ascending');

            // Click again for descending
            await surprisalHeader.click();
            await page.waitForTimeout(300);
            await expect(surprisalHeader).toHaveAttribute('aria-sort', 'descending');

            // Verify rows still exist after sorting
            const rows = page.locator('.MuiDataGrid-row:not([data-id^="skeleton"])');
            expect(await rows.count()).toBeGreaterThan(0);
        });

        test('table CSV download can be triggered', async ({ page }) => {
            const table = page.locator(`[data-test-id="${TEST_ID_EXPERIMENTS_TABLE}"]`);

            // Open export menu
            const exportBtn = table.getByRole('button', { name: /export/i });
            await exportBtn.click();

            // Click CSV download option
            const downloadPromise = page.waitForEvent('download');
            await page.getByRole('menuitem', { name: /download as csv/i }).click();
            const download = await downloadPromise;
            expect(download.suggestedFilename()).toMatch(/\.csv$/);
        });

        test('table search for "significant" returns between 1 and total rows', async ({ page }) => {
            const table = page.locator(`[data-test-id="${TEST_ID_EXPERIMENTS_TABLE}"]`);

            // Use quick filter search
            const searchInput = table.locator('.MuiDataGrid-toolbar input');
            await searchInput.fill('significant');

            // Wait for filtering to apply
            await page.waitForTimeout(500);

            const filteredRows = page.locator('.MuiDataGrid-row:not([data-id^="skeleton"])');
            const filteredCount = await filteredRows.count();
            expect(filteredCount).toBeGreaterThan(0);

            // Clear search and verify more rows come back
            await searchInput.clear();
            await page.waitForTimeout(500);
            const clearedCount = await page
                .locator('.MuiDataGrid-row:not([data-id^="skeleton"])')
                .count();
            expect(clearedCount).toBeGreaterThan(filteredCount);
        });

        test('table sorts by ID ascending then descending', async ({ page }) => {
            const table = page.locator(`[data-test-id="${TEST_ID_EXPERIMENTS_TABLE}"]`);
            const idHeader = table.locator('.MuiDataGrid-columnHeader[data-field="id"]');
            const surprisalHeader = table.locator(
                '.MuiDataGrid-columnHeader[data-field="surprisal"]'
            );

            // Wait for the default surprisal-descending sort to be applied — this is the visual
            // evidence that the hasJobCompleted useEffect in ExperimentsTable has already fired.
            // Clicking ID before that fires would have its sort overridden by the effect.
            await expect(surprisalHeader).toHaveAttribute('aria-sort', 'descending', {
                timeout: 30000,
            });

            // Click the column header title span specifically — the ID column is only 45px wide
            // and Playwright's viewport-level click may miss the sort trigger on narrow columns.
            // Using evaluate() dispatches the click directly in the JS context.
            const idHeaderTitle = table.locator(
                '.MuiDataGrid-columnHeader[data-field="id"] .MuiDataGrid-columnHeaderTitle'
            );
            await idHeaderTitle.evaluate((el) => {
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            });
            await expect(idHeader).toHaveAttribute('aria-sort', 'ascending', { timeout: 5000 });

            // Click again for descending
            await idHeaderTitle.evaluate((el) => {
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            });
            await expect(idHeader).toHaveAttribute('aria-sort', 'descending', { timeout: 5000 });
        });

        test('clicking table row highlights row, tree node, and opens details panel', async ({
            page,
        }) => {
            // Wait for job to complete so experiments are fully loaded in context
            await expect(
                page.locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_LIST}"]`)
            ).toBeVisible({ timeout: 30000 });

            // Click the hypothesis cell of the first non-skeleton row (force to bypass overlap)
            const firstHypothesisCell = page
                .locator(
                    '.MuiDataGrid-row:not([data-id^="skeleton"]) .MuiDataGrid-cell[data-field="hypothesis"]'
                )
                .first();
            await firstHypothesisCell.click({ force: true });

            // Row is highlighted
            await expect(page.locator('.MuiDataGrid-row.Mui-selected')).toBeVisible({
                timeout: 10000,
            });

            // Details panel is open
            await expect(
                page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_PANEL}"]`)
            ).toBeVisible({ timeout: 10000 });

            // Tree node is highlighted (stroke changes to green)
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            const selectedNode = graphContainer.locator('circle.node[stroke="#0FCB8C"]');
            expect(await selectedNode.count()).toBeGreaterThan(0);
        });

        test('tree can be dragged to pan', async ({ page }) => {
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            await expect(graphContainer).toBeVisible();

            // Target only the main tree SVG (not icon SVGs inside buttons)
            const svg = graphContainer.locator('svg:not([data-testid])');
            const box = await svg.boundingBox();
            if (!box) throw new Error('SVG bounding box not found');

            const treeGroup = graphContainer.locator('.tree-group');
            const transformBefore = await treeGroup.getAttribute('transform');

            // Drag in the right portion of the SVG — the RunPanel occupies the left ~700px
            // so we start at 80% of the width to be in the tree-visible area
            const startX = box.x + box.width * 0.8;
            const startY = box.y + box.height / 2;
            await page.mouse.move(startX, startY);
            await page.mouse.down();
            await page.mouse.move(startX + 80, startY + 80, { steps: 5 });
            await page.mouse.up();

            const transformAfter = await treeGroup.getAttribute('transform');
            expect(transformAfter).not.toEqual(transformBefore);
        });

        test('tree zoom in, zoom out, and reset work', async ({ page }) => {
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            await expect(graphContainer).toBeVisible();

            const treeGroup = graphContainer.locator('.tree-group');
            const initialTransform = await treeGroup.getAttribute('transform');

            // Zoom in
            const zoomIn = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH_ZOOM_IN}"]`);
            await zoomIn.click();
            await page.waitForTimeout(300);
            const zoomedInTransform = await treeGroup.getAttribute('transform');
            expect(zoomedInTransform).not.toEqual(initialTransform);

            // Zoom out
            const zoomOut = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH_ZOOM_OUT}"]`);
            await zoomOut.click();
            await page.waitForTimeout(300);

            // Reset should appear after interaction
            const resetBtn = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH_RESET}"]`);
            await expect(resetBtn).toBeVisible();
            await resetBtn.click();
            await page.waitForTimeout(400);

            // After reset, transform should be back to centered (not same as zoomed-in)
            const resetTransform = await treeGroup.getAttribute('transform');
            expect(resetTransform).not.toEqual(zoomedInTransform);
        });

        test('clicking a tree node highlights node, table row, and opens details panel', async ({
            page,
        }) => {
            const graphContainer = page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_GRAPH}"]`);
            await expect(graphContainer).toBeVisible();

            // Wait for job to complete so experiments are fully loaded in context
            await expect(
                page.locator(`[data-test-id="${TEST_ID_TOP_SURPRISALS_LIST}"]`)
            ).toBeVisible({ timeout: 30000 });

            // Wait for nodes to be rendered, then dispatch click directly on the element.
            // We use evaluate() instead of .click({ force: true }) because the tree SVG sits
            // at z-index 1 behind the RunPanel (z-index 2); a force-click still moves the mouse
            // to the viewport position and the RunPanel intercepts it.
            const nodes = graphContainer.locator('circle.node[style*="pointer"]');
            await expect(nodes.first()).toBeVisible({ timeout: 15000 });
            await nodes.first().evaluate((el) => {
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
            });

            // Details panel opens
            await expect(
                page.locator(`[data-test-id="${TEST_ID_EXPERIMENT_DETAILS_PANEL}"]`)
            ).toBeVisible({ timeout: 10000 });

            // A table row is highlighted
            expect(await page.locator('.MuiDataGrid-row.Mui-selected').count()).toBeGreaterThan(0);

            // The clicked node has a green stroke
            const selectedNode = graphContainer.locator('circle.node[stroke="#0FCB8C"]');
            expect(await selectedNode.count()).toBeGreaterThan(0);
        });
    });
}
