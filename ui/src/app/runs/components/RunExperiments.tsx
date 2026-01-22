import { Paper } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useEffect, useRef, useState } from 'react';

import { Experiment, getExperimentFromApi } from '@/types/Run';
import { getRunsApi } from '@/api/RunsApi';

type RunExperimentsProps = {
    runId: string;
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

export default function RunExperiments({ runId }: RunExperimentsProps) {
    const api = getRunsApi();
    const [experiments, setExperiments] = useState<Experiment[]>([]); // eslint-disable-line @typescript-eslint/no-unused-vars
    const [rows, setRows] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    // Keep track of details needed for polling that shouldn't trigger re-renders
    const pollingStateRef = useRef({
        lastKnownExperimentId: null as string | null,
        hasRunCompleted: false,
    });

    const fetchLatestRunExperiments = async (runId: string) => {
        if (pollingStateRef.current.hasRunCompleted) {
            return;
        }
        try {
            // Get the list of experiments since the last one we know about
            const { data } = await api.getRunExperiments({
                runid: runId,
                afterExperimentId: pollingStateRef.current.lastKnownExperimentId ?? undefined,
            });
            const newExperiments = data.experiments.map((experimentFromApi) =>
                getExperimentFromApi(experimentFromApi)
            );
            setExperiments((prevExperiments) => [...prevExperiments, ...newExperiments]);

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
            pollingStateRef.current.lastKnownExperimentId =
                newExperiments.at(-1)?.experimentId ?? null;
            if (data.has_job_completed) {
                pollingStateRef.current.hasRunCompleted = true;
            }
        } catch (error) {
            console.error('Error fetching experiments:', error);
        }
    };

    useEffect(() => {
        if (!runId) {
            return;
        }
        if (!pollingStateRef.current.lastKnownExperimentId) {
            // First time running since mounting
            setLoading(true);
            fetchLatestRunExperiments(runId).finally(() => setLoading(false));
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

    return (
        <Paper sx={{ height: 400, width: '100%' }}>
            <DataGrid
                rows={rows}
                columns={columns}
                loading={loading}
                initialState={{ pagination: { paginationModel } }}
                pageSizeOptions={[5, 10]}
                sx={{ border: 0 }}
            />
        </Paper>
    );
}
