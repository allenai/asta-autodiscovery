import { Paper, styled } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useEffect, useRef, useState } from 'react';

import { Experiment, getExperimentFromApi } from '@/types/Run';
import { getRunsApi } from '@/api/RunsApi';

type RunExperimentsProps = {
    runId: string;
    onSelectExperiment: (experiment: Experiment) => void;
};

const DEFAULT_UPDATE_INTERVAL_MS = 15000;

const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 130 },
    { field: 'isSurprising', headerName: 'Surprising', width: 100 },
    { field: 'status', headerName: 'Status', width: 120 },
    { field: 'creationIdx', headerName: 'Creation Index', width: 130 },
    { field: 'runtimeMs', headerName: 'Runtime (ms)', width: 130 },
    { field: 'hypothesis', headerName: 'Hypothesis', width: 200, flex: 1 },
];

export function RunExperiments({ runId, onSelectExperiment }: RunExperimentsProps) {
    const api = getRunsApi();
    const [experiments, setExperiments] = useState<Record<string, Experiment>>({});
    const [rows, setRows] = useState<any[]>([]);
    const [isLoading, setIsloading] = useState(false);

    // Keep track of details needed for polling that shouldn't trigger re-renders
    const pollingStateRef = useRef({
        lastKnownExperimentId: null as string | null,
        hasRunCompleted: false,
        isFetching: false,
    });

    const fetchLatestRunExperiments = async (runId: string) => {
        // Prevent concurrent fetches
        if (pollingStateRef.current.isFetching || pollingStateRef.current.hasRunCompleted) {
            return;
        }

        pollingStateRef.current.isFetching = true;

        try {
            // Get the list of experiments since the last one we know about
            const { data } = await api.getRunExperiments({
                runid: runId,
                afterExperimentId: pollingStateRef.current.lastKnownExperimentId ?? undefined,
            });
            const newExperiments = data.experiments.map((experimentFromApi) =>
                getExperimentFromApi(experimentFromApi)
            );
            setExperiments((prevExperiments) => ({
                ...prevExperiments,
                ...newExperiments.reduce(
                    (acc, experiment) => {
                        acc[experiment.experimentId] = experiment;
                        return acc;
                    },
                    {} as Record<string, Experiment>
                ),
            }));

            // Convert to rows for DataGrid
            const newRows = newExperiments.map((experiment) => ({
                id: experiment.experimentId,
                hypothesis: experiment.hypothesis ?? 'N/A',
                isSurprising: experiment.isSurprising ? 'Yes' : 'No',
                status: experiment.status,
                creationIdx: experiment.creationIdx,
                runtimeMs: experiment.runtimeMs ?? 'N/A',
            }));
            setRows((prevRows) => [...prevRows, ...newRows]);

            // Update the last known experiment ID for the next poll
            const lastExperimentId = newExperiments.at(-1)?.experimentId;
            if (lastExperimentId) {
                pollingStateRef.current.lastKnownExperimentId = lastExperimentId;
            }
            if (data.has_job_completed) {
                pollingStateRef.current.hasRunCompleted = true;
            }
        } catch (error) {
            console.error('Error fetching experiments:', error);
        } finally {
            pollingStateRef.current.isFetching = false;
        }
    };

    useEffect(() => {
        if (!runId) {
            return;
        }
        if (!pollingStateRef.current.lastKnownExperimentId) {
            // First time running since mounting
            setIsloading(true);
            fetchLatestRunExperiments(runId).finally(() => setIsloading(false));
        }
        const intervalId = setInterval(() => {
            console.log('setInterval()', { runId, ...pollingStateRef.current });
            fetchLatestRunExperiments(runId);
        }, DEFAULT_UPDATE_INTERVAL_MS);
        return () => {
            clearInterval(intervalId);
        };
    }, [runId]);

    const paginationModel = { page: 0, pageSize: 5 };

    const handleRowClick = (params: any) => {
        onSelectExperiment(experiments[params.id]);
    };

    return (
        <Paper sx={{ height: '100%', width: '100%' }}>
            <StyledDataGrid
                rows={rows}
                columns={columns}
                loading={isLoading}
                initialState={{ pagination: { paginationModel } }}
                pageSizeOptions={[5, 10, 25]}
                sx={{ border: 0 }}
                onRowClick={handleRowClick}
            />
        </Paper>
    );
}

const StyledDataGrid = styled(DataGrid)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    backgroundColor: theme.color['dark-teal-100'].hex,
    margin: theme.spacing(0.5, 0, 1, 0),
    '.MuiDataGrid-cell, .MuiDataGrid-columnHeaders, .MuiDataGrid-row, .MuiDataGrid-columnSeparator':
        {
            borderColor: theme.color['cream-4'].rgba.toString(),
        },
}));
