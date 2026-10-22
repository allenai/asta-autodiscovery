import { useMemo } from 'react';
import { Alert, Box, styled } from '@mui/material';

import { ExperimentFromApi, RunFromApi } from '@/api/RunsApi';
import { StaticRunExperimentsProvider } from '@/contexts/RunExperimentsContext';
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

/** A finished run's view, read-only and served from the embedded data. */
export default function ReportPage() {
    const data = window.AUTODISCOVERY_REPORT;
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
                    <StaticRunExperimentsProvider runid={run.id} experiments={experiments}>
                        <RunViewContent
                            run={run as Run & { details: NonNullable<Run['details']> }}
                            error={null}
                            canStop={false}
                            cancelling={false}
                            handleStop={noop}
                            experimentsLabel={
                                run.stats?.requestedExperiments === 1 ? 'experiment' : 'experiments'
                            }
                            canShare={false}
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
