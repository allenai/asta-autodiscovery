import { test, expect } from '@playwright/test';

import {
    TEST_ID_LOGIN_ERROR,
    TEST_ID_LOGIN_PASSWORD,
    TEST_ID_LOGIN_SUBMIT,
    TEST_ID_LOGIN_USERNAME,
    TEST_ID_SIGN_IN_BUTTON,
} from '../src/app/testIds';

/**
 * Auth-backend UX tests. These require NO third-party credentials — they run
 * against a stack started with a specific AUTH_PROVIDER, so they are safe to run
 * in the public repo and are tagged `@public` (see `yarn test:e2e:public`).
 *
 * Select the backend under test with E2E_AUTH_PROVIDER (matching how the stack
 * was started). The non-matching describe blocks skip.
 */
const PROVIDER = process.env.E2E_AUTH_PROVIDER || 'auth0';

// A seeded user for the happy-path login (create it with api/scripts/auth_admin.py
// before running; these are ephemeral test creds, not secrets).
const TEST_USER = process.env.E2E_TEST_USER || 'e2e';
const TEST_PASSWORD = process.env.E2E_TEST_PASSWORD || '';

const signInButton = (page: import('@playwright/test').Page) =>
    page.locator(`[data-test-id="${TEST_ID_SIGN_IN_BUTTON}"]`);

test.describe('Auth: password_file provider', { tag: '@public' }, () => {
    test.skip(PROVIDER !== 'password_file', 'requires E2E_AUTH_PROVIDER=password_file');

    test.beforeEach(async ({ page }) => {
        await page.goto('/runs');
        await page.waitForLoadState('domcontentloaded');
    });

    test('sign-in opens the username/password form', async ({ page }) => {
        await signInButton(page).click();
        const dialog = page.getByRole('dialog');
        await expect(dialog).toBeVisible();
        await expect(dialog.locator(`[data-test-id="${TEST_ID_LOGIN_USERNAME}"]`)).toBeVisible();
        await expect(dialog.locator(`[data-test-id="${TEST_ID_LOGIN_PASSWORD}"]`)).toBeVisible();
    });

    test('wrong password shows an inline error and no stuck global dialog', async ({ page }) => {
        await signInButton(page).click();
        const dialog = page.getByRole('dialog');
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_USERNAME}"]`).fill('nobody');
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_PASSWORD}"]`).fill('wrong-password');
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_SUBMIT}"]`).click();

        // Error is shown inside the login dialog...
        await expect(dialog.locator(`[data-test-id="${TEST_ID_LOGIN_ERROR}"]`)).toBeVisible();
        // ...the login dialog stays open (dismissable)...
        await expect(dialog).toBeVisible();
        // ...and the global "Access Denied" dialog is NOT triggered (regression guard).
        await expect(page.getByRole('heading', { name: 'Access Denied' })).toHaveCount(0);
    });

    test('valid credentials sign in, then sign out', async ({ page }) => {
        test.skip(!TEST_PASSWORD, 'requires E2E_TEST_USER/E2E_TEST_PASSWORD for a seeded user');

        await signInButton(page).click();
        const dialog = page.getByRole('dialog');
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_USERNAME}"]`).fill(TEST_USER);
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_PASSWORD}"]`).fill(TEST_PASSWORD);
        await dialog.locator(`[data-test-id="${TEST_ID_LOGIN_SUBMIT}"]`).click();

        // Dialog closes and the header now offers sign-out.
        await expect(dialog).toBeHidden();
        await expect(signInButton(page)).toHaveText(/Sign out/);

        // Sign out returns to the signed-out state.
        await signInButton(page).click();
        await expect(signInButton(page)).toHaveText(/Sign in/);
    });
});

test.describe('Auth: none provider (desktop mode)', { tag: '@public' }, () => {
    test.skip(PROVIDER !== 'none', 'requires E2E_AUTH_PROVIDER=none');

    test('no sign-in affordance; already authenticated', async ({ page }) => {
        await page.goto('/runs');
        await page.waitForLoadState('domcontentloaded');

        // The header sign-in/out button is hidden entirely in desktop mode.
        await expect(signInButton(page)).toHaveCount(0);
        // And the logged-out intro CTA is not shown.
        await expect(page.getByRole('button', { name: /Sign in to get started/i })).toHaveCount(0);
    });
});
