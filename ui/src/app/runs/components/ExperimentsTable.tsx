import { Paper, styled, Box, Alert, Tooltip, Skeleton, GlobalStyles } from '@mui/material';
import {
    DataGrid,
    GridColDef,
    GridRenderCellParams,
    GridRowSelectionModel,
    GridSortModel,
} from '@mui/x-data-grid';
import { useCallback, useEffect, useMemo, useState } from 'react';

import { RunStats } from '@/types/Run';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { useExperimentBookmarks } from '@/contexts/ExperimentBookmarksContext';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';
import { mkExperimentRowAttrs, sortColumnEventName } from '@/analytics/runDetails';
import { track } from '@/analytics/track';
import { useURLSearchParams } from '@/contexts/URLSearchParamsContext';
import { ExperimentBookmarkControl } from './ExperimentBookmarkControl';
import { TEST_ID_EXPERIMENTS_TABLE } from '@/testIds';

const DEFAULT_PAGE_SIZE = -1;

const DEFAULT_COLUMNS: GridColDef[] = [
    {
        field: 'isBookmarked',
        headerName: '',
        width: 40,
        minWidth: 40,
        align: 'center',
        sortable: false,
        filterable: false,
        disableColumnMenu: true,
        resizable: false,
        headerClassName: 'bookmark-column-header',
        renderCell: (params: GridRenderCellParams) => {
            return <ExperimentBookmarkControl experiment={params.row.experiment} />;
        },
    },
    {
        field: 'id',
        headerName: 'ID',
        align: 'left',
        width: 45,
        minWidth: 45,
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
        flex: 3,
        minWidth: 0,
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="100%" />;
            }
            return (
                <HypothesisCell>
                    <HypothesisText>{params.value}</HypothesisText>
                </HypothesisCell>
            );
        },
    },
    {
        field: 'surprisal',
        headerName: 'Surprisal',
        flex: 1,
        minWidth: 70,
        maxWidth: 90,
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
                        textAlign: 'right',
                    })}>
                    {params.value?.toFixed(3) ?? 'N/A'}
                </Box>
            );
        },
    },
    {
        field: 'prior',
        headerName: 'Belief Before',
        align: 'center',
        flex: 1,
        minWidth: 80,
        maxWidth: 120,
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="80%" />;
            }
            const value = params.row.priorValue;
            const label = params.value;
            return (
                <Tooltip title={value?.toFixed(3) ?? 'N/A'} arrow>
                    <BeliefValue sx={{ cursor: 'pointer' }}>{label}</BeliefValue>
                </Tooltip>
            );
        },
    },
    {
        field: 'posterior',
        headerName: 'Belief After',
        align: 'center',
        flex: 1,
        minWidth: 80,
        maxWidth: 120,
        renderCell: (params: GridRenderCellParams) => {
            if (params.row.isSkeleton) {
                return <StyledSkeleton variant="text" width="80%" />;
            }
            const value = params.row.posteriorValue;
            const label = params.value;
            return (
                <Tooltip title={value?.toFixed(3) ?? 'N/A'} arrow>
                    <BeliefValue sx={{ cursor: 'pointer' }}>{label}</BeliefValue>
                </Tooltip>
            );
        },
    },
    {
        field: 'direction',
        headerName: 'Direction',
        align: 'center',
        flex: 1,
        minWidth: 50,
        maxWidth: 120,
        resizable: false,
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
    const {
        experiments,
        lastError,
        selectExperiment,
        selectedExperiment,
        hasJobCompleted,
        shouldScrollToSelected,
    } = useRunExperiments();
    const { isExperimentBookmarksEnabled, bookmarkedExperimentIds } = useExperimentBookmarks();
    const { getSearchParam, setSearchParam, deleteSearchParam } = useURLSearchParams();
    const columns = useMemo(
        () =>
            isExperimentBookmarksEnabled
                ? DEFAULT_COLUMNS
                : DEFAULT_COLUMNS.filter((col) => col.field !== 'isBookmarked'),
        [isExperimentBookmarksEnabled]
    );
    const [sortModel, setSortModel] = useState<GridSortModel>([]);

    const [paginationModel, setPaginationModel] = useState(() => {
        const raw = getSearchParam('pageSize');
        const pageSize = raw !== null ? parseInt(raw, 10) : DEFAULT_PAGE_SIZE;
        return { page: 0, pageSize: isNaN(pageSize) ? DEFAULT_PAGE_SIZE : pageSize };
    });

    const handlePaginationModelChange = useCallback(
        (newModel: { page: number; pageSize: number }) => {
            setPaginationModel(newModel);
            if (newModel.pageSize === DEFAULT_PAGE_SIZE) {
                deleteSearchParam('pageSize');
            } else {
                setSearchParam('pageSize', String(newModel.pageSize));
            }
        },
        [setSearchParam, deleteSearchParam]
    );

    // Apply default Surprisal sort when the session completes.
    useEffect(() => {
        if (hasJobCompleted) {
            setSortModel([{ field: 'surprisal', sort: 'desc' }]);
        }
    }, [hasJobCompleted]);

    const handleSortModelChange = useCallback((newSortModel: GridSortModel) => {
        setSortModel(newSortModel);
        // Track sorting event
        if (newSortModel.length > 0) {
            const { field, sort } = newSortModel[0];
            if (sort) {
                track(sortColumnEventName, {
                    columnName: field,
                    direction: sort,
                });
            }
        }
    }, []);

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
                isBookmarked: false,
                experiment: null,
            }));
            return skeletonRows;
        }
        return [];
    }, [runStats?.pendingExperiments, hasJobCompleted, experiments.length]);

    // Convert experiments to rows for DataGrid
    const rows = useMemo(() => {
        const experimentRows = experiments.map((experiment) => {
            // For failed or inconclusive experiments, show N/A in all cells
            const isInconclusiveOrFailed = experiment.status !== 'SUCCEEDED';

            return {
                id: experiment.idInRun,
                hypothesis: experiment.hypothesis ?? 'N/A',
                prior: isInconclusiveOrFailed ? 'N/A' : getPriorAndPosteriorLabel(experiment.prior),
                priorValue: isInconclusiveOrFailed ? null : experiment.prior,
                posterior: isInconclusiveOrFailed
                    ? 'N/A'
                    : getPriorAndPosteriorLabel(experiment.posterior),
                posteriorValue: isInconclusiveOrFailed ? null : experiment.posterior,
                surprisal: isInconclusiveOrFailed
                    ? null
                    : experiment.surprise
                      ? Math.abs(experiment.surprise)
                      : experiment.surprise,
                isSurprising: isInconclusiveOrFailed ? false : experiment.isSurprising,
                direction: isInconclusiveOrFailed
                    ? 'N/A'
                    : getSurprisalDirection(experiment.surprise),
                creationIdx: experiment.creationIdx,
                runtimeMs: isInconclusiveOrFailed ? 'N/A' : experiment.runtimeMs ?? 'N/A',
                isSkeleton: false,
                isBookmarked: bookmarkedExperimentIds.has(experiment.experimentId),
                experiment,
            };
        });

        // Add skeleton rows for pending experiments if job is not completed
        const skeletonRows = createSkeletonRows();
        return [...experimentRows, ...skeletonRows];
    }, [experiments, runStats, hasJobCompleted, bookmarkedExperimentIds]);

    // Set up row selection based on selectedExperiment
    const rowSelectionModel: GridRowSelectionModel = useMemo(() => {
        if (selectedExperiment) {
            return {
                type: 'include',
                ids: new Set([selectedExperiment.idInRun]),
            };
        }
        return {
            type: 'include',
            ids: new Set(),
        };
    }, [selectedExperiment]);

    const handleRowClick = useCallback(
        (params: any) => {
            // Don't allow clicking on skeleton rows
            if (params.row.isSkeleton) {
                return;
            }
            const exp = experiments.find((exp) => exp.idInRun === params.id);
            if (exp) {
                selectExperiment(exp, { scroll: false });
            }
        },
        [experiments, selectExperiment]
    );

    // Scroll to the selected experiment when it changes, unless the caller opted out
    useEffect(() => {
        const selectedRowID = selectedExperiment?.idInRun;
        const timeoutId = setTimeout(() => {
            if (selectedRowID && shouldScrollToSelected.current) {
                const row = document.querySelector(`.MuiDataGrid-row[data-id="${selectedRowID}"]`);
                row?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center',
                });
            }
            shouldScrollToSelected.current = true;
        }, 50); // Debounce to allow DataGrid to render the new selection
        return () => clearTimeout(timeoutId);
    }, [selectedExperiment?.idInRun]);

    return (
        <>
            <GlobalStyles
                styles={(theme: any) => ({
                    // Column header menus
                    '.MuiDataGrid-menu .MuiPaper-root': {
                        backgroundColor: theme.color['teal-100'].hex,
                        color: theme.color['cream-100'].hex,
                    },
                    '.MuiDataGrid-menu .MuiMenuItem-root:hover': {
                        backgroundColor: theme.color['cream-10'].rgba.toString(),
                    },
                    '.MuiDataGrid-menu .MuiListItemIcon-root, .MuiDataGrid-menu .MuiSvgIcon-root': {
                        color: theme.color['green-100'].hex,
                    },
                    // Filter panel
                    '.MuiDataGrid-panel .MuiDataGrid-paper': {
                        backgroundColor: theme.color['teal-100'].hex,
                        color: theme.color['cream-100'].hex,
                    },
                    '.MuiDataGrid-panel .MuiInputLabel-root, .MuiDataGrid-panel .MuiInputBase-input, .MuiDataGrid-panel .MuiSelect-select':
                        {
                            color: theme.color['cream-100'].hex,
                        },
                    '.MuiDataGrid-panel .MuiOutlinedInput-notchedOutline': {
                        borderColor: theme.color['cream-20'].rgba.toString(),
                    },
                    '.MuiDataGrid-panel .MuiSvgIcon-root': {
                        color: theme.color['cream-100'].hex,
                    },
                    '.MuiDataGrid-panel .MuiButton-root': {
                        color: theme.color['green-100'].hex,
                    },
                    '.MuiDataGrid-panel .MuiInputLabel-root.Mui-focused': {
                        color: theme.color['green-100'].hex,
                    },
                    '.MuiDataGrid-panel .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline':
                        {
                            borderColor: theme.color['green-100'].hex,
                        },
                    // Column control panel
                    '.MuiDataGrid-panel .MuiDataGrid-columnsManagementHeader, .MuiDataGrid-panel .MuiDataGrid-columnsManagementFooter':
                        {
                            borderColor: theme.color['cream-20'].rgba.toString(),
                        },
                    '.MuiDataGrid-panel .MuiButton-root.Mui-disabled': {
                        color: theme.color['cream-100'].hex,
                    },
                })}
            />
            <Wrapper data-test-id={TEST_ID_EXPERIMENTS_TABLE}>
                {lastError && (
                    <Alert severity="error" sx={{ m: 1 }}>
                        {lastError}
                    </Alert>
                )}
                <StyledDataGrid
                    rows={rows}
                    columns={columns}
                    loading={!runStats?.pendingExperiments && !experiments.length}
                    paginationModel={paginationModel}
                    onPaginationModelChange={handlePaginationModelChange}
                    initialState={{
                        sorting: {
                            sortModel:
                                runStats?.completedExperiments === runStats?.requestedExperiments
                                    ? [{ field: 'surprisal', sort: 'desc' }]
                                    : [],
                        },
                    }}
                    pageSizeOptions={[5, 10, 25, 50, 100, { value: -1, label: 'All' }]}
                    sx={{ border: 0 }}
                    onRowClick={handleRowClick}
                    sortModel={sortModel}
                    onSortModelChange={handleSortModelChange}
                    getRowHeight={() => 'auto'}
                    rowSelectionModel={rowSelectionModel}
                    slotProps={{
                        row: mkExperimentRowAttrs(),
                    }}
                    showToolbar={true}
                    hideFooter={true}
                />
            </Wrapper>
        </>
    );
}

const Wrapper = styled(Paper)`
    background: transparent;
    container: experiment-table-wrapper / inline-size;
    width: 100%;
`;

const StyledDataGrid = styled(DataGrid)(({ theme }) => ({
    container: 'experiment-table / inline-size',
    color: theme.color['cream-100'].hex,
    backgroundColor: theme.color['extra-dark-teal-100'].hex,
    margin: theme.spacing(0.5, 0, 1, 0),
    '--DataGrid-rowBorderColor': theme.color['cream-20'].rgba.toString(),

    '.MuiDataGrid-cell, .MuiDataGrid-row, .MuiDataGrid-columnSeparator, .MuiDataGrid-columnHeader, .MuiDataGrid-filler, .MuiDataGrid-footerContainer, .MuiDataGrid-withBorderColor':
        {
            borderColor: theme.color['cream-4'].rgba.toString(),
        },

    '.MuiDataGrid-columnHeader, .MuiDataGrid-columnHeaders .MuiDataGrid-filler': {
        backgroundColor: theme.color['extra-dark-teal-100'].hex,

        '.MuiDataGrid-sortButton': {
            backgroundColor: theme.color['cream-4'].rgba.toString(),
        },

        '@container experiment-table (width < 800px)': {
            fontSize: '.85em',
        },
    },

    '.MuiDataGrid-columnHeaderTitle, .MuiDataGrid-columnHeader svg, .MuiDataGrid-toolbar svg': {
        color: theme.color['green-40'].hex,
        fontWeight: 700,
    },

    '.MuiDataGrid-toolbar': {
        borderBottomColor: theme.color['cream-20'].rgba.toString(),
    },

    '.MuiDataGrid-toolbar .MuiOutlinedInput-root.Mui-focused .MuiOutlinedInput-notchedOutline': {
        borderColor: theme.color['green-100'].hex,
    },

    '.MuiDataGrid-columnHeader:focus, .MuiDataGrid-columnHeader:focus-within': {
        outline: `1px solid ${theme.color['green-100'].hex}`,
    },

    '.bookmark-column-header .MuiDataGrid-columnSeparator': {
        display: 'none',
    },

    '.MuiDataGrid-cell[data-field="isBookmarked"]': {
        padding: 0,
    },

    '.MuiDataGrid-columnSeparator': {
        '& svg': {
            color: theme.color['cream-20'].rgba.toString(),
        },

        '&:hover svg': {
            color: theme.color['green-100'].hex,
        },
    },

    '.MuiDataGrid-columnHeader:has(+ .MuiDataGrid-filler) .MuiDataGrid-columnSeparator, .MuiDataGrid-columnHeader:has(+ .MuiDataGrid-scrollbarFiller) .MuiDataGrid-columnSeparator':
        {
            display: 'none',
        },

    '.MuiDataGrid-toolbar .MuiInputBase-input': {
        color: theme.color['cream-100'].hex,
    },

    '.MuiDataGrid-footerContainer': {
        color: theme.color['cream-100'].hex,
    },

    '.MuiDataGrid-cell': {
        paddingTop: theme.spacing(1),
        paddingBottom: theme.spacing(1),

        '@container experiment-table (width < 800px)': {
            paddingLeft: theme.spacing(0.5),
            paddingRight: theme.spacing(0.5),
        },

        '&:active, &:focus, &:focus-within': {
            outline: 'none',
        },
    },

    '.MuiDataGrid-row:nth-of-type(even)': {
        backgroundColor: theme.color['cream-4'].rgba.toString(),
    },

    '.MuiDataGrid-row:hover, .MuiDataGrid-row.Mui-hovered': {
        backgroundColor: theme.color['cream-10'].rgba.toString(),
        cursor: 'pointer',
    },

    '.MuiDataGrid-row.Mui-selected': {
        position: 'relative',
        '&::before': {
            content: '""',
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: '4px',
            backgroundColor: theme.color['green-100'].hex,
        },
    },

    '.MuiDataGrid-row.Mui-selected:not(:nth-of-type(even))': {
        backgroundColor: '#0D2529',
    },

    '.MuiDataGrid-row.Mui-selected:hover, .MuiDataGrid-row.Mui-selected.Mui-hovered': {
        backgroundColor: theme.color['cream-10'].rgba.toString(),
    },

    '.MuiTablePagination-root, .MuiTablePagination-selectLabel, .MuiTablePagination-displayedRows, .MuiTablePagination-select, .MuiTablePagination-selectIcon':
        {
            color: theme.color['cream-100'].hex,
        },

    // Custom scrollbar styling
    '& ::-webkit-scrollbar': {
        width: '12px',
        height: '12px',
    },
    '& ::-webkit-scrollbar-track': {
        background: theme.color['cream-4'].rgba.toString(),
        borderRadius: '6px',
    },
    '& ::-webkit-scrollbar-thumb': {
        background: theme.color['cream-20'].rgba.toString(),
        borderRadius: '6px',
        border: `2px solid ${theme.color['cream-4'].rgba.toString()}`,
    },
    scrollbarWidth: 'thin',
    scrollbarColor: `${theme.color['cream-20'].rgba.toString()} ${theme.color['cream-4'].rgba.toString()}`,
}));

const StyledSkeleton = styled(Skeleton)(({ theme }) => ({
    backgroundColor: theme.color['cream-10'].rgba.toString(),
}));

const HypothesisCell = styled(Box)`
    container: hypothesis-cell / inline-size;
`;

const HypothesisText = styled('div')`
    display: -webkit-box;
    line-height: 1.4;
    overflow: hidden;
    white-space: normal;
    word-wrap: break-word;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;

    @container hypothesis-cell (width < 150px) {
        word-break: break-all;
        -webkit-line-clamp: 4;
    }

    @container hypothesis-cell (width < 40px) {
        visibility: hidden;
        -webkit-line-clamp: 1;
    }
`;

const BeliefValue = styled(Box)`
    word-wrap: break-word;
`;
