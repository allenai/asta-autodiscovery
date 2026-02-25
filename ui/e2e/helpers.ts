import { Page, BrowserContext, expect } from '@playwright/test';

/**
 * Clicks an element and asserts the outgoing navigation request goes to a URL
 * containing the given domain. Intercepts the request before it completes so
 * the test page is not navigated away from.
 */
export async function expectLinkDomain(
    page: Page,
    locator: ReturnType<Page['locator']>,
    domain: string
) {
    const requestPromise = page.waitForRequest(
        (req) => req.url().includes(domain) && req.isNavigationRequest(),
        { timeout: 10000 }
    );
    await locator.click();
    const request = await requestPromise;
    expect(request.url()).toContain(domain);
}

/**
 * Clicks an element that opens a new tab (target="_blank") and asserts
 * the new page URL contains the given domain and returns a non-error HTTP status.
 */
export async function expectExternalLink(
    context: BrowserContext,
    locator: ReturnType<Page['locator']>,
    domain: string
) {
    const [newPage] = await Promise.all([
        context.waitForEvent('page'),
        locator.click(),
    ]);
    await newPage.waitForLoadState('domcontentloaded');
    expect(newPage.url()).toContain(domain);
    await newPage.close();
}

/**
 * Waits for the runs page to finish loading experiments.
 * Polls until the experiments table has at least one non-skeleton row.
 */
export async function waitForExperimentsLoaded(page: Page) {
    // Wait for the data grid to appear and have rows
    await page.waitForSelector('.MuiDataGrid-row:not([data-id^="skeleton"])', { timeout: 30000 });
}
