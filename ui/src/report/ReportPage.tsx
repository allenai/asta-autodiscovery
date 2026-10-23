import { useEffect, useMemo, useState } from 'react';
import { Alert, Box, styled } from '@mui/material';

import { ExperimentFromApi, RunFromApi } from '@/api/RunsApi';
import {
    DEFAULT_REFRESH_INTERVAL_MS,
    StaticRunExperimentsProvider,
} from '@/contexts/RunExperimentsContext';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { RunViewContent } from '@/runs/components/RunView';
import { Run, getExperimentFromApi, getRunFromApi } from '@/types/Run';
import { scrollbarStyles } from '@/utils/scrollbar';

/**
 * The run data autodiscovery.report writes to data.js beside the report: the
 * same shapes the API serves for a run and for each experiment's details.
 */
export interface ReportData {
    run: RunFromApi;
    experiments: ExperimentFromApi[];
}

declare global {
    interface Window {
        AUTODISCOVERY_REPORT?: ReportData;
    }
}

const noop = () => {};

/**
 * Load data.js again. A script tag, not fetch(): a page opened from file:// may
 * load scripts beside it but not fetch them. The query string keeps a browser
 * from reusing the copy it already has.
 */
const reloadReportData = () =>
    new Promise<ReportData | undefined>((resolve) => {
        const script = document.createElement('script');
        script.src = `data.js?t=${Date.now()}`;
        script.onload = script.onerror = () => {
            script.remove();
            resolve(window.AUTODISCOVERY_REPORT);
        };
        document.head.appendChild(script);
    });

/** A run's view, read-only and served from the data.js beside the page. */
export default function ReportPage() {
    const [data, setData] = useState(window.AUTODISCOVERY_REPORT);
    const isRunning = data?.run.run_details?.status === 'RUNNING';

    // While the run goes on, report.py rewrites data.js as each experiment
    // finishes; follow it at the web UI's polling interval. Only a new
    // experiment or status changes what the page shows, so nothing else
    // re-renders it.
    useEffect(() => {
        if (!isRunning) return;
        const interval = setInterval(async () => {
            const next = await reloadReportData();
            setData((prev) =>
                next &&
                (next.experiments.length !== prev?.experiments.length ||
                    next.run.run_details?.status !== prev?.run.run_details?.status)
                    ? next
                    : prev
            );
        }, DEFAULT_REFRESH_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [isRunning]);

    const run = useMemo(() => (data ? getRunFromApi(data.run) : null), [data]);
    const experiments = useMemo(
        () => (data ? data.experiments.map(getExperimentFromApi) : []),
        [data]
    );

    if (!run?.details) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">
                    No run data found. This page reads data.js from its own directory.
                </Alert>
            </Box>
        );
    }

    return (
        <Wrapper>
            <ScrollContent>
                <URLSearchParamsProvider>
                    <StaticRunExperimentsProvider
                        runid={run.id}
                        experiments={experiments}
                        hasJobCompleted={!isRunning}>
                        <RunViewContent
                            run={run as Run & { details: NonNullable<Run['details']> }}
                            error={null}
                            canStop={false}
                            cancelling={false}
                            handleStop={noop}
                            experimentsLabel={
                                run.stats?.requestedExperiments === 1 ? 'experiment' : 'experiments'
                            }
                        />
                    </StaticRunExperimentsProvider>
                </URLSearchParamsProvider>
            </ScrollContent>
        </Wrapper>
    );
}

// The runs layout's backdrop, without its sidebar and header.
const Wrapper = styled('div')`
    background: radial-gradient(
            141.38% 60.74% at 50% 113.89%,
            #245555 0%,
            rgba(36, 85, 85, 0.2) 50%,
            rgba(36, 85, 85, 0) 100%
        ),
        ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    position: absolute;
    inset: 0;
`;

const ScrollContent = styled('div')`
    height: 100%;
    overflow: auto;
    ${({ theme }) => scrollbarStyles(theme)}
`;
