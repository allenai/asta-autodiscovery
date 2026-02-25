import { test, expect } from '@playwright/test';
import { expectExternalLink } from './helpers';
import {
    TEST_ID_SIGN_IN_BUTTON,
    TEST_ID_FEEDBACK_BUTTON,
    TEST_ID_ABOUT_BUTTON,
    TEST_ID_CREDITS_CHIP,
    TEST_ID_AI2_LOGO_LINK,
    TEST_ID_ASTA_LABS_LOGO_LINK,
    TEST_ID_EXAMPLE_SESSION_ITEM,
    TEST_ID_DISCLAIMER_BUTTON,
    TEST_ID_ATTRIBUTION_BUTTON,
    TEST_ID_DISCLAIMER_DIALOG,
    TEST_ID_ATTRIBUTION_DIALOG,
    TEST_ID_DIALOG_CLOSE_BUTTON,
    TEST_ID_PRIVACY_POLICY_LINK,
    TEST_ID_TERMS_OF_USE_LINK,
    TEST_ID_RESPONSIBLE_USE_LINK,
} from '../src/app/testIds';

test.describe('Homepage (/runs)', () => {
    test.beforeEach(async ({ page }) => {
        await page.goto('/runs');
        // Wait for the page to finish loading (auth check completes)
        await page.waitForLoadState('networkidle');
    });

    test('page loads without error', async ({ page }) => {
        await expect(page).not.toHaveURL(/error/);
        await expect(page.locator('body')).toBeVisible();
        // No visible error toasts (MuiAlert-filledError = filled Alert with severity="error")
        await expect(page.locator('.MuiAlert-filledError')).toHaveCount(0);
    });

    test('sign in button links to auth.example.com domain', async ({ page }) => {
        const signInBtn = page.locator(`[data-test-id="${TEST_ID_SIGN_IN_BUTTON}"]`);
        await expect(signInBtn).toBeVisible();

        // Intercept navigation to auth0 before it completes
        const requestPromise = page.waitForRequest(
            (req) => req.url().includes('auth.example.com'),
            { timeout: 10000 }
        );
        await signInBtn.click();
        const request = await requestPromise;
        expect(request.url()).toContain('auth.example.com');
    });

    test('feedback button links to a page that does not error out', async ({ page, context }) => {
        const feedbackLink = page.locator(`[data-test-id="${TEST_ID_FEEDBACK_BUTTON}"]`);
        await expect(feedbackLink).toBeVisible();
        await expectExternalLink(context, feedbackLink, 'google.com');
    });

    test('About button links to allenai.org domain', async ({ page, context }) => {
        const aboutLink = page.locator(`[data-test-id="${TEST_ID_ABOUT_BUTTON}"]`);
        await expect(aboutLink).toBeVisible();
        await expectExternalLink(context, aboutLink, 'allenai.org');
    });

    test('header does not show credits chip', async ({ page }) => {
        await expect(page.locator(`[data-test-id="${TEST_ID_CREDITS_CHIP}"]`)).toHaveCount(0);
    });

    test('Ai2 logo link leads to allenai.org', async ({ page, context }) => {
        const ai2Link = page.locator(`[data-test-id="${TEST_ID_AI2_LOGO_LINK}"]`);
        await expect(ai2Link).toBeVisible();
        await expectExternalLink(context, ai2Link, 'allenai.org');
    });

    test('ASTA Labs logo link leads to allen.ai', async ({ page, context }) => {
        const astaLink = page.locator(`[data-test-id="${TEST_ID_ASTA_LABS_LOGO_LINK}"]`);
        await expect(astaLink).toBeVisible();
        await expectExternalLink(context, astaLink, 'allen.ai');
    });

    test('first example session link loads successfully', async ({ page }) => {
        const firstItem = page.locator(`[data-test-id="${TEST_ID_EXAMPLE_SESSION_ITEM}"]`).first();
        await expect(firstItem).toBeVisible();

        // Click the link inside it and wait for navigation to a run page
        const link = firstItem.locator('a').first();
        await Promise.all([
            page.waitForLoadState('networkidle'),
            link.click(),
        ]);
        await expect(page).not.toHaveURL('/runs');
        await expect(page.locator('body')).toBeVisible();
    });

    test('Disclaimer button opens dialog which can be closed', async ({ page }) => {
        const disclaimerBtn = page.locator(`[data-test-id="${TEST_ID_DISCLAIMER_BUTTON}"]`);
        await expect(disclaimerBtn).toBeVisible();
        await disclaimerBtn.click();

        const dialog = page.locator(`[data-test-id="${TEST_ID_DISCLAIMER_DIALOG}"]`);
        await expect(dialog).toBeVisible();

        const closeBtn = page.locator(`[data-test-id="${TEST_ID_DIALOG_CLOSE_BUTTON}"]`);
        await closeBtn.click();
        await expect(dialog).not.toBeVisible();
    });

    test('Attribution button opens dialog which can be closed', async ({ page }) => {
        const attributionBtn = page.locator(`[data-test-id="${TEST_ID_ATTRIBUTION_BUTTON}"]`);
        await expect(attributionBtn).toBeVisible();
        await attributionBtn.click();

        const dialog = page.locator(`[data-test-id="${TEST_ID_ATTRIBUTION_DIALOG}"]`);
        await expect(dialog).toBeVisible();

        const closeBtn = page.locator(`[data-test-id="${TEST_ID_DIALOG_CLOSE_BUTTON}"]`);
        await closeBtn.click();
        await expect(dialog).not.toBeVisible();
    });

    test('Privacy Policy link opens without error', async ({ page, context }) => {
        const link = page.locator(`[data-test-id="${TEST_ID_PRIVACY_POLICY_LINK}"]`);
        await expect(link).toBeVisible();
        await expectExternalLink(context, link, 'allenai.org');
    });

    test('Terms of Use link opens without error', async ({ page, context }) => {
        const link = page.locator(`[data-test-id="${TEST_ID_TERMS_OF_USE_LINK}"]`);
        await expect(link).toBeVisible();
        await expectExternalLink(context, link, 'allenai.org');
    });

    test('Responsible Use link opens without error', async ({ page, context }) => {
        const link = page.locator(`[data-test-id="${TEST_ID_RESPONSIBLE_USE_LINK}"]`);
        await expect(link).toBeVisible();
        await expectExternalLink(context, link, 'allenai.org');
    });
});
