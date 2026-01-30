import { Paper, styled, Box, Alert, Tooltip, Skeleton } from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import { useCallback, useMemo } from 'react';

import { Experiment, RunStats } from '@/types/Run';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';

const columns: GridColDef[] = [
    {
        field: 'id',
        headerName: 'ID',
        width: 130,
        align: 'center',
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="90%" />;
            }
            return params.value;
        },
    },
    {
        field: 'hypothesis',
        headerName: 'Experiment Hypothesis',
        width: 200,
        flex: 1,
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="100%" />;
            }
            return <HypothesisCell>{params.value}</HypothesisCell>;
        },
    },
    {
        field: 'surprisal',
        headerName: 'Surprisal',
        width: 150,
        align: 'center',
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="70%" />;
            }
            const isSurprising = params.row.isSurprising;
            return (
                <Box
                    sx={(theme) => ({
                        color: isSurprising
                            ? theme.color['warning-orange-100'].hex
                            : theme.color['cream-100'].hex,
                        fontWeight: isSurprising ? 700 : 'normal',
                    })}>
                    {params.value?.toFixed(3) ?? 'N/A'}
                </Box>
            );
        },
    },
    {
        field: 'prior',
        headerName: 'Belief Before',
        width: 150,
        align: 'center',
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="80%" />;
            }
            const value = params.row.priorValue;
            const label = params.value;
            return (
                <Tooltip title={value?.toFixed(3) ?? 'N/A'} arrow>
                    <Box sx={{ cursor: 'pointer' }}>{label}</Box>
                </Tooltip>
            );
        },
    },
    {
        field: 'posterior',
        headerName: 'Belief After',
        width: 150,
        align: 'center',
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="80%" />;
            }
            const value = params.row.posteriorValue;
            const label = params.value;
            return (
                <Tooltip title={value?.toFixed(3) ?? 'N/A'} arrow>
                    <Box sx={{ cursor: 'pointer' }}>{label}</Box>
                </Tooltip>
            );
        },
    },
    {
        field: 'direction',
        headerName: 'Direction',
        width: 120,
        align: 'center',
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="60%" />;
            }
            const direction = params.value;
            return <Box>{direction ?? 'N/A'}</Box>;
        },
    },
];

interface ExperimentsTableProps {
    runStats?: RunStats | null;
}

export function ExperimentsTable({ runStats }: ExperimentsTableProps) {
    const { experiments, lastError, selectExperiment, hasJobCompleted } = useRunExperiments();

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

    const createSkeletonRows = useCallback(() => {
        const pendingCount = runStats?.pendingExperiments ?? 0;
        if (!hasJobCompleted && pendingCount > 0) {
            const skeletonRows = Array.from({ length: pendingCount }, (_, i) => ({
                id: `skeleton-${i}`,
                hypothesis: '',
                prior: '',
                priorValue: null,
                posterior: '',
                posteriorValue: null,
                surprisal: 0,
                isSurprising: false,
                direction: '',
                creationIdx: experiments.length + i,
                runtimeMs: 'N/A',
                isSkeleton: true,
            }));
            return skeletonRows;
        }
        return [];
    }, [runStats?.pendingExperiments, hasJobCompleted, experiments.length]);

    // Convert experiments to rows for DataGrid
    const rows = useMemo(() => {
        const experimentRows = experiments.map((experiment) => {
            return {
                id: experiment.idInRun,
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
                isSkeleton: false,
            };
        });

        // Add skeleton rows for pending experiments if job is not completed
        const skeletonRows = createSkeletonRows();
        return [...experimentRows, ...skeletonRows];
    }, [experiments, runStats, hasJobCompleted]);

    const paginationModel = { page: 0, pageSize: 50 };

    const handleRowClick = (params: any) => {
        // Don't allow clicking on skeleton rows
        if (params.row.isSkeleton) {
            return;
        }
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
                loading={!runStats?.pendingExperiments && !experiments.length}
                initialState={{ pagination: { paginationModel } }}
                pageSizeOptions={[5, 10, 25, 50]}
                sx={{ border: 0 }}
                onRowClick={handleRowClick}
                getRowHeight={() => 'auto'}
            />
        </Paper>
    );
}

const StyledDataGrid = styled(DataGrid)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    backgroundColor: theme.color['extra-dark-teal-100'].hex,
    margin: theme.spacing(0.5, 0, 1, 0),

    '.MuiDataGrid-cell, .MuiDataGrid-row, .MuiDataGrid-columnSeparator, .MuiDataGrid-columnHeader, .MuiDataGrid-filler, .MuiDataGrid-footerContainer, .MuiDataGrid-withBorderColor':
        {
            borderColor: theme.color['cream-4'].rgba.toString(),
        },

    '.MuiDataGrid-columnHeader, .MuiDataGrid-columnHeaders .MuiDataGrid-filler': {
        backgroundColor: theme.color['extra-dark-teal-100'].hex,

        '.MuiDataGrid-sortButton': {
            backgroundColor: theme.color['cream-4'].rgba.toString(),
        },
    },

    '.MuiDataGrid-columnHeaderTitle, .MuiDataGrid-columnHeader svg': {
        color: theme.color['green-40'].hex,
        fontWeight: 700,
    },

    '.MuiDataGrid-footerContainer': {
        color: theme.color['cream-100'].hex,
    },

    '.MuiDataGrid-row:hover, .MuiDataGrid-row.Mui-hovered': {
        backgroundColor: theme.color['cream-4'].rgba.toString(),
        cursor: 'pointer',
    },

    '.MuiTablePagination-root, .MuiTablePagination-selectLabel, .MuiTablePagination-displayedRows, .MuiTablePagination-select, .MuiTablePagination-selectIcon':
        {
            color: theme.color['cream-100'].hex,
        },
}));

const StyledSkeleton = styled(Skeleton)(({ theme }) => ({
    backgroundColor: theme.color['cream-10'].rgba.toString(),
}));

const HypothesisCell = styled(Box)`
    lineHeight: 1.4,
    whiteSpace: 'normal',
    wordWrap: 'break-word',
`;
