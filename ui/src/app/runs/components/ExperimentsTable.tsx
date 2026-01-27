import { Paper, styled, Box, Alert } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useMemo } from 'react';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';

import { Experiment } from '@/types/Run';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import {
    SurprisalLabels,
    SurprisalScale,
    getPriorAndPosteriorLabel,
    getSurprisalColor,
    getSurprisalScale,
} from '@/runs/utils/ExperimentUtils';

const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 130 },
    { field: 'hypothesis', headerName: 'Hypothesis', width: 200, flex: 1 },
    {
        field: 'prior',
        headerName: 'Before',
        width: 150,
        renderHeader: () => (
            <ColumnHeaderWrapper>
                <span>Before</span>
                <ScienceOutlinedIcon fontSize="small" />
            </ColumnHeaderWrapper>
        ),
    },
    {
        field: 'posterior',
        headerName: 'After',
        width: 150,
        renderHeader: () => (
            <ColumnHeaderWrapper>
                <span>After</span>
                <ScienceOutlinedIcon fontSize="small" />
            </ColumnHeaderWrapper>
        ),
    },
    {
        field: 'surprisal',
        headerName: 'Surprisal',
        width: 150,
        renderHeader: () => (
            <ColumnHeaderWrapper>
                <span>Surprisal</span>
                <LightbulbOutlinedIcon fontSize="small" />
            </ColumnHeaderWrapper>
        ),
        renderCell: (params: GridRenderCellParams) => {
            const scale = params.row.surprisalScale as SurprisalScale;
            const color = getSurprisalColor(scale);
            return <Box sx={{ color }}>{params.value}</Box>;
        },
    },
    { field: 'status', headerName: 'Status', width: 120 },
];

export function ExperimentsTable() {
    const { experiments, isLoading, lastError, selectExperiment } = useRunExperiments();

    // Create a map for O(1) lookups when clicking rows
    const experimentsMap = useMemo(() => {
        return experiments.reduce(
            (acc, exp) => {
                acc[exp.experimentId] = exp;
                return acc;
            },
            {} as Record<string, Experiment>
        );
    }, [experiments]);

    // Convert experiments to rows for DataGrid
    const rows = useMemo(() => {
        return experiments.map((experiment) => {
            const surprisalScale = getSurprisalScale(experiment.surprise);
            return {
                id: experiment.experimentId,
                hypothesis: experiment.hypothesis ?? 'N/A',
                prior: getPriorAndPosteriorLabel(experiment.prior),
                posterior: getPriorAndPosteriorLabel(experiment.posterior),
                surprisal: SurprisalLabels[surprisalScale],
                surprisalScale,
                status: experiment.status,
                creationIdx: experiment.creationIdx,
                runtimeMs: experiment.runtimeMs ?? 'N/A',
            };
        });
    }, [experiments]);

    const paginationModel = { page: 0, pageSize: 5 };

    const handleRowClick = (params: any) => {
        selectExperiment(experimentsMap[params.id]);
    };

    return (
        <Paper sx={{ height: '100%', width: '100%' }}>
            {lastError && (
                <Alert severity="error" sx={{ m: 1 }}>
                    {lastError}
                </Alert>
            )}
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
    backgroundColor: theme.color['extra-dark-teal-100'].hex,
    margin: theme.spacing(0.5, 0, 1, 0),

    '.MuiDataGrid-cell, .MuiDataGrid-columnHeaders, .MuiDataGrid-row, .MuiDataGrid-columnSeparator':
        {
            borderColor: theme.color['cream-4'].rgba.toString(),
        },

    '.MuiDataGrid-columnHeaderTitle, .MuiDataGrid-columnHeader svg': {
        color: theme.color['green-40'].hex,
        fontWeight: 700,
    },
}));

const ColumnHeaderWrapper = styled(Box)`
    align-items: center;
    color: ${({ theme }) => theme.color['green-40'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(0.5)};
`;
