import { Paper, styled, Box, Alert, Tooltip } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useMemo } from 'react';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';

import { Experiment } from '@/types/Run';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';

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
        renderCell: (params: GridRenderCellParams) => {
            const value = params.row.priorValue;
            const label = params.value;
            return (
                <Tooltip title={value != null ? value.toFixed(3) : 'N/A'} arrow>
                    <Box sx={{ cursor: 'pointer' }}>{label}</Box>
                </Tooltip>
            );
        },
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
        renderCell: (params: GridRenderCellParams) => {
            const value = params.row.posteriorValue;
            const label = params.value;
            return (
                <Tooltip title={value != null ? value.toFixed(3) : 'N/A'} arrow>
                    <Box sx={{ cursor: 'pointer' }}>{label}</Box>
                </Tooltip>
            );
        },
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
            const isSurprising = params.row.isSurprising;
            return (
                <Box
                    sx={(theme) => ({
                        color: isSurprising
                            ? theme.color['warning-orange-100'].hex
                            : theme.color['cream-100'].hex,
                        fontWeight: isSurprising ? 700 : 'normal',
                    })}>
                    {params.value.toFixed(3)}
                </Box>
            );
        },
    },
    {
        field: 'direction',
        headerName: 'Direction',
        width: 120,
        renderCell: (params: GridRenderCellParams) => {
            const direction = params.value;
            return <Box>{direction}</Box>;
        },
    },
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
            return {
                id: experiment.experimentId,
                hypothesis: experiment.hypothesis ?? 'N/A',
                prior: getPriorAndPosteriorLabel(experiment.prior),
                priorValue: experiment.prior,
                posterior: getPriorAndPosteriorLabel(experiment.posterior),
                posteriorValue: experiment.posterior,
                surprisal: experiment.surprise
                    ? Math.abs(experiment.surprise)
                    : experiment.surprise,
                isSurprising: experiment.isSurprising,
                direction: getSurprisalDirection(experiment.surprise),
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
