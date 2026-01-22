import { Paper } from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useEffect, useState } from 'react';

import {
    ExperimentDetailed,
    getExperimentSummaryFromApi,
    getExperimentDetailedFromApi,
} from '@/types/Run';
import { getRunsApi } from '@/api/RunsApi';

type RunExperimentsProps = {
    runId: string;
};

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
    const [_lastExperimentIdFetched, setLastExperimentIdFetched] = useState<string | null>(null);
    const [_experiments, setExperiments] = useState<ExperimentDetailed[]>([]);
    const [rows, setRows] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchRunExperiments = async () => {
        setLoading(true);
        try {
            // First, get the list of experiments
            const { data } = await api.getRunExperiments({ runid: runId });
            const experimentSummaries = data.experiments.map((experimentFromApi) =>
                getExperimentSummaryFromApi(experimentFromApi)
            );

            // Then fetch detailed info for each experiment
            const detailedExperiments = await Promise.all(
                experimentSummaries.map(async (summary) => {
                    try {
                        const { data: detailData } = await api.getRunExperimentDetails({
                            runid: runId,
                            experimentId: summary.experimentId,
                        });
                        return getExperimentDetailedFromApi(detailData.experiment);
                    } catch (error) {
                        console.error(
                            `Error fetching details for experiment ${summary.experimentId}:`,
                            error
                        );
                        // Return null for failed fetches
                        return null;
                    }
                })
            );

            // Filter out any null values from failed fetches
            const validExperiments = detailedExperiments.filter(
                (exp): exp is ExperimentDetailed => exp !== null
            );

            const rows = validExperiments.map((experiment) => ({
                id: experiment.experimentId,
                hypothesis: experiment.hypothesis ?? 'N/A',
                isSurprising: experiment.isSurprising ? 'Yes' : 'No',
                status: experiment.status,
                creationIdx: experiment.creationIdx,
                runtimeMs: experiment.runtimeMs ?? 'N/A',
            }));

            setLastExperimentIdFetched(data.after_experiment_id);
            setExperiments(validExperiments);
            setRows(rows);
        } catch (error) {
            console.error('Error fetching experiments:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRunExperiments();
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
