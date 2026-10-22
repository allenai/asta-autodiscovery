import { test, expect, type Page } from '@playwright/test';

import { cpSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';

import { DEFAULT_REFRESH_INTERVAL_MS } from '../src/app/contexts/RunExperimentsContext';

import {
    TEST_ID_EXPERIMENT_DETAILS_PANEL,
    TEST_ID_EXPERIMENT_GRAPH,
    TEST_ID_EXPERIMENTS_TABLE,
    TEST_ID_SESSION_CONFIG_BUTTON,
    TEST_ID_SESSION_CONFIG_MODAL,
    TEST_ID_TOP_SURPRISALS_LIST,
} from '../src/app/testIds';

/**
 * Smoke test of the standalone HTML report: the built run view, opened from disk
 * the way people open it, rendering a run written by autodiscovery.report (see
 * make_report.py). The run view's own behavior is the web UI's and is tested
 * there; this covers what only the report has: one self-contained page that
 * must work from file:// without the network, and the data contract between
 * report.py and the page.
 *
 * `make test-report-viewer` builds the viewer, writes the run and sets REPORT_DIR.
 */
const REPORT_DIR = process.env.REPORT_DIR;

const byTestId = (id: string) => `[data-test-id="${id}"]`;

/** Console errors, page errors and network requests, none of which a report should make. */
function watchForProblems(page: Page): string[] {
    const problems: string[] = [];
    page.on('console', (msg) => {
        if (msg.type() === 'error') problems.push(`console: ${msg.text()}`);
    });
    page.on('pageerror', (err) => problems.push(`page error: ${err.message}`));
    page.on('request', (req) => {
        if (!/^(file|data):/.test(req.url())) problems.push(`network request: ${req.url()}`);
    });
    return problems;
}

const DATA_JS_PREFIX = 'window.AUTODISCOVERY_REPORT = ';

test.beforeEach(() => {
    if (!REPORT_DIR) throw new Error('REPORT_DIR is unset; run `make test-report-viewer`');
});

test('renders a finished run from disk, offline', async ({ page }) => {
    const problems = watchForProblems(page);

    await page.goto(pathToFileURL(join(REPORT_DIR!, 'index.html')).href);

    // The run, from data.js.
    await expect(page.getByRole('heading', { name: 'Synthetic soil study' })).toBeVisible();
    await expect(page.locator(byTestId(TEST_ID_TOP_SURPRISALS_LIST))).toContainText(
        'Nitrogen raises yield only in acidic soil.'
    );
    const table = page.locator(byTestId(TEST_ID_EXPERIMENTS_TABLE));
    for (const hypothesis of [
        'Nitrogen raises yield only in acidic soil.',
        'Rainfall predicts yield.',
        'Clay content explains the acidity effect.',
    ]) {
        await expect(table).toContainText(hypothesis);
    }
    // The tree draws every experiment, under the placeholder root it draws for the
    // data-loading node, which the report leaves out as the API does.
    await expect(page.locator(`${byTestId(TEST_ID_EXPERIMENT_GRAPH)} circle.node`)).toHaveCount(4);

    // An experiment's details, with its figures read from figures/ beside the page.
    await table.getByText('Nitrogen raises yield only in acidic soil.').click();
    const details = page.locator(byTestId(TEST_ID_EXPERIMENT_DETAILS_PANEL));
    await expect(details).toContainText('The data support it.');
    await expect(details).toContainText('yield ~ nitrogen * pH');
    const figure = details.getByAltText('Figure 1');
    await expect(figure).toHaveJSProperty('complete', true);
    expect(await figure.evaluate((img: HTMLImageElement) => img.naturalWidth)).toBeGreaterThan(0);
    // Selection lives in the hash, the part of a file:// URL that can change.
    await expect(page).toHaveURL(/#\/\?exp=1$/);

    // Run parameters, from args.json and the dataset metadata.
    await page.locator(byTestId(TEST_ID_SESSION_CONFIG_BUTTON)).click();
    const config = page.locator(byTestId(TEST_ID_SESSION_CONFIG_MODAL));
    await expect(config).toContainText('soil.csv');
    await expect(config).toContainText('3 experiments');

    expect(problems).toEqual([]);
});

test('follows a running run as data.js is rewritten', async ({ page }) => {
    const problems = watchForProblems(page);

    // A copy of the report, rewound to a run with one experiment done.
    const dir = mkdtempSync(join(tmpdir(), 'report-'));
    cpSync(REPORT_DIR!, dir, { recursive: true });
    const dataJs = join(dir, 'data.js');
    const finished = JSON.parse(
        readFileSync(dataJs, 'utf-8').slice(DATA_JS_PREFIX.length).trim().replace(/;$/, '')
    );
    const write = (data: unknown) =>
        writeFileSync(dataJs, `${DATA_JS_PREFIX}${JSON.stringify(data)};`);
    const running = (experiments: number) => ({
        run: {
            ...finished.run,
            status: 'RUNNING',
            run_details: { ...finished.run.run_details, status: 'RUNNING', finished_at: null },
        },
        experiments: finished.experiments.slice(0, experiments),
    });
    write(running(1));

    await page.clock.install();
    await page.goto(pathToFileURL(join(dir, 'index.html')).href);
    const table = page.locator(byTestId(TEST_ID_EXPERIMENTS_TABLE));
    await expect(table).toContainText('Nitrogen raises yield only in acidic soil.');
    await expect(table).not.toContainText('Rainfall predicts yield.');

    // A reader opens the finished experiment while the run goes on.
    await table.getByText('Nitrogen raises yield only in acidic soil.').click();
    const details = page.locator(byTestId(TEST_ID_EXPERIMENT_DETAILS_PANEL));
    await expect(details).toContainText('The data support it.');

    // report.py rewrites data.js as the next experiment finishes.
    write(running(2));
    await page.clock.runFor(DEFAULT_REFRESH_INTERVAL_MS);
    await expect(table).toContainText('Rainfall predicts yield.');
    // The reader's place survives the reload.
    await expect(details).toContainText('The data support it.');
    await expect(page).toHaveURL(/#\/\?exp=1$/);

    // And the run finishes.
    write(finished);
    await page.clock.runFor(DEFAULT_REFRESH_INTERVAL_MS);
    await expect(table).toContainText('Clay content explains the acidity effect.');
    await expect(page.locator(byTestId(TEST_ID_TOP_SURPRISALS_LIST))).toBeVisible();

    expect(problems).toEqual([]);
});
