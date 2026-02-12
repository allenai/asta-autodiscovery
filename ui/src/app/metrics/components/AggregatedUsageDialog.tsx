'use client';

import { useCallback, useEffect, useState } from 'react';
import {
    Box,
    CircularProgress,
    Dialog,
    DialogContent,
    DialogTitle,
    IconButton,
    Typography,
    styled,
    Tab as MuiTab,
    Tabs,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';

import { getMetricsApi } from '@/api/MetricsApi';
import type { AggregatedUsageBucket, AggregatedUsageResponse } from '@/types/Metrics';

const PALETTE = [
    '#818cf8',
    '#a78bfa',
    '#c084fc',
    '#e879f9',
    '#f472b6',
    '#fb923c',
    '#2dd4bf',
    '#38bdf8',
    '#a3e635',
    '#fbbf24',
];

const fmt = (n: number) => (n || 0).toLocaleString();
const fmtCost = (n: number) => `$${n.toFixed(2)}`;

function prettyName(k: string): string {
    return k
        .replace(/^google\//, '')
        .replace(/^openai\//, '')
        .replace(/^anthropic\//, '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

function assignColors(keys: string[]): Record<string, string> {
    const map: Record<string, string> = {};
    keys.forEach((k, i) => {
        map[k] = PALETTE[i % PALETTE.length];
    });
    return map;
}

interface AggregatedUsageDialogProps {
    open: boolean;
    onClose: () => void;
    startDate?: string;
    endDate?: string;
}

export default function AggregatedUsageDialog({
    open,
    onClose,
    startDate,
    endDate,
}: AggregatedUsageDialogProps) {
    const [data, setData] = useState<AggregatedUsageResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const api = getMetricsApi();
            const { data: usage } = await api.getAggregatedUsage({
                startDate: startDate || undefined,
                endDate: endDate || undefined,
            });
            setData(usage);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load usage data');
        } finally {
            setLoading(false);
        }
    }, [startDate, endDate]);

    useEffect(() => {
        if (open) fetchData();
    }, [open, fetchData]);

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="lg"
            fullWidth
            PaperProps={{
                sx: {
                    bgcolor: '#1a1a1a',
                    backgroundImage: 'none',
                    border: (theme: any) =>
                        `1px solid ${theme.color?.['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'}`,
                    borderRadius: '16px',
                },
            }}>
            <DialogTitle
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    pb: 1,
                }}>
                <Typography
                    sx={{
                        fontSize: '1rem',
                        fontWeight: 600,
                        color: (theme: any) => theme.color?.['cream-100']?.hex || '#fff',
                    }}>
                    Aggregated LLM Usage
                    <Typography
                        component="span"
                        sx={{
                            fontSize: '0.78rem',
                            fontWeight: 300,
                            ml: 1,
                            color: (theme: any) =>
                                theme.color?.['cream-40']?.rgba?.toString() ||
                                'rgba(255,255,255,0.4)',
                        }}>
                        across {data?.runs_included ?? '...'} runs with usage data
                    </Typography>
                </Typography>
                <IconButton onClick={onClose} size="small" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                    <CloseIcon fontSize="small" />
                </IconButton>
            </DialogTitle>
            <DialogContent sx={{ pt: 1 }}>
                {loading && !data && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
                        <CircularProgress size={28} />
                    </Box>
                )}
                {error && (
                    <Typography color="error" sx={{ py: 4, textAlign: 'center' }}>
                        {error}
                    </Typography>
                )}
                {data && <AggregatedUsageContent data={data} />}
            </DialogContent>
        </Dialog>
    );
}

function AggregatedUsageContent({ data }: { data: AggregatedUsageResponse }) {
    const t = data.totals;
    const hasReasoning = t.total_reasoning_tokens > 0;

    const cards: { v: string; l: string; sub?: string }[] = [
        {
            v: fmt(t.total_tokens),
            l: 'Total Tokens',
            sub: `${fmt(Math.round(t.mean_tokens_per_run))} avg/run`,
        },
        { v: String(t.total_calls), l: 'Total Calls' },
        {
            v: fmtCost(t.total_cost_usd),
            l: 'Total LLM Cost',
            sub: `${fmtCost(t.mean_cost_per_run)} avg/run`,
        },
        { v: String(data.runs_included), l: 'Runs Included' },
    ];
    if (hasReasoning) {
        cards.splice(1, 0, {
            v: fmt(t.total_reasoning_tokens),
            l: 'Reasoning Tokens',
        });
    }

    // Available views
    type ViewKey = 'by_agent' | 'by_model' | 'by_node' | 'by_component';
    const viewDefs: { key: ViewKey; label: string }[] = [
        { key: 'by_agent', label: 'By Agent' },
        { key: 'by_model', label: 'By Model' },
        { key: 'by_node', label: 'By Node' },
        { key: 'by_component', label: 'By Component' },
    ];
    const views = viewDefs.filter((v) => data[v.key] && Object.keys(data[v.key]).length > 0);
    const [activeView, setActiveView] = useState(0);

    const agentKeys = Object.keys(data.by_agent || {});

    return (
        <Box>
            {/* Summary Cards */}
            <CardGrid $count={cards.length}>
                {cards.map((c) => (
                    <StatCard key={c.l}>
                        <StatValue>{c.v}</StatValue>
                        <StatLabel>{c.l}</StatLabel>
                        {c.sub && <StatSub>{c.sub}</StatSub>}
                    </StatCard>
                ))}
            </CardGrid>

            {/* Stacked Composition */}
            {agentKeys.length > 0 && (
                <Panel>
                    <PanelTitle>
                        Token Composition{' '}
                        <PanelSubtitle>
                            cumulative prompt / completion / reasoning per agent
                        </PanelSubtitle>
                    </PanelTitle>
                    <LegendRow>
                        <LegendItem>
                            <LegendDot style={{ background: '#818cf8' }} /> Prompt
                        </LegendItem>
                        <LegendItem>
                            <LegendDot style={{ background: '#f472b6' }} /> Completion
                        </LegendItem>
                        <LegendItem>
                            <LegendDot style={{ background: '#2dd4bf' }} /> Reasoning
                        </LegendItem>
                    </LegendRow>
                    {agentKeys
                        .sort(
                            (a, b) =>
                                (data.by_agent[b]?.total_tokens ?? 0) -
                                (data.by_agent[a]?.total_tokens ?? 0)
                        )
                        .map((key) => {
                            const a = data.by_agent[key];
                            const tot = a.total_tokens || 1;
                            const pP = (a.total_prompt_tokens / tot) * 100;
                            const cP = (a.total_completion_tokens / tot) * 100;
                            const rP = (a.total_reasoning_tokens / tot) * 100;
                            return (
                                <StackedRow key={key}>
                                    <StackedLabel>{prettyName(key)}</StackedLabel>
                                    <StackedTrack>
                                        <StackedSeg
                                            style={{ width: `${pP}%`, background: '#818cf8' }}>
                                            {pP > 8 && (
                                                <SegLabel>{fmt(a.total_prompt_tokens)}</SegLabel>
                                            )}
                                        </StackedSeg>
                                        <StackedSeg
                                            style={{ width: `${cP}%`, background: '#f472b6' }}>
                                            {cP > 8 && (
                                                <SegLabel>
                                                    {fmt(a.total_completion_tokens)}
                                                </SegLabel>
                                            )}
                                        </StackedSeg>
                                        {rP > 0 && (
                                            <StackedSeg
                                                style={{ width: `${rP}%`, background: '#2dd4bf' }}>
                                                {rP > 8 && (
                                                    <SegLabel>
                                                        {fmt(a.total_reasoning_tokens)}
                                                    </SegLabel>
                                                )}
                                            </StackedSeg>
                                        )}
                                    </StackedTrack>
                                    <StackedTotal>{fmt(a.total_tokens)}</StackedTotal>
                                </StackedRow>
                            );
                        })}
                </Panel>
            )}

            {/* Tabbed Total Tokens */}
            {views.length > 0 && (
                <Panel>
                    <PanelTitle>
                        Total Tokens <PanelSubtitle>breakdown view</PanelSubtitle>
                    </PanelTitle>
                    <Tabs
                        value={activeView}
                        onChange={(_, v) => setActiveView(v)}
                        sx={{
                            mb: 2,
                            minHeight: 32,
                            '& .MuiTab-root': {
                                minHeight: 32,
                                fontSize: '0.72rem',
                                textTransform: 'none',
                                px: 1.5,
                                color: 'rgba(255,255,255,0.6)',
                                '&.Mui-selected': { color: '#FAF2E9' },
                            },
                        }}>
                        {views.map((v) => (
                            <MuiTab key={v.key} label={v.label} />
                        ))}
                    </Tabs>
                    <AggregatedBarChart
                        data={data[views[activeView].key]}
                        showCost={views[activeView].key === 'by_model'}
                    />
                </Panel>
            )}

            {/* Statistics Table */}
            {agentKeys.length > 0 && (
                <Panel>
                    <PanelTitle>
                        Statistics{' '}
                        <PanelSubtitle>per agent, across {data.runs_included} runs</PanelSubtitle>
                    </PanelTitle>
                    <StatsTable data={data.by_agent} />
                </Panel>
            )}
        </Box>
    );
}

function AggregatedBarChart({
    data,
    showCost,
}: {
    data: Record<string, AggregatedUsageBucket>;
    showCost?: boolean;
}) {
    const entries = Object.entries(data).sort((a, b) => b[1].total_tokens - a[1].total_tokens);
    const maxVal = Math.max(...entries.map(([, d]) => d.total_tokens), 1);
    const colors = assignColors(entries.map(([k]) => k));

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {entries.map(([key, d]) => {
                const pct = (d.total_tokens / maxVal) * 100;
                const color = colors[key];
                const small = pct < 12;
                return (
                    <BarRow key={key}>
                        <BarLabel>{prettyName(key)}</BarLabel>
                        <BarTrack>
                            <BarFill
                                style={{
                                    width: `${Math.max(pct, 1.5)}%`,
                                    background: color,
                                }}>
                                <BarValue $outside={small}>
                                    {fmt(d.total_tokens)}
                                    {showCost &&
                                        d.total_cost_usd > 0 &&
                                        ` (${fmtCost(d.total_cost_usd)})`}
                                </BarValue>
                            </BarFill>
                        </BarTrack>
                        <BarAnnotation>{fmt(Math.round(d.mean_tokens_per_run))} avg</BarAnnotation>
                    </BarRow>
                );
            })}
        </Box>
    );
}

function StatsTable({ data }: { data: Record<string, AggregatedUsageBucket> }) {
    const keys = Object.keys(data).sort(
        (a, b) => (data[b]?.total_tokens ?? 0) - (data[a]?.total_tokens ?? 0)
    );
    const colors = assignColors(keys);

    const totals = { calls: 0, prompt: 0, completion: 0, reasoning: 0, total: 0 };
    keys.forEach((key) => {
        const a = data[key];
        totals.calls += a.total_calls;
        totals.prompt += a.total_prompt_tokens;
        totals.completion += a.total_completion_tokens;
        totals.reasoning += a.total_reasoning_tokens;
        totals.total += a.total_tokens;
    });

    return (
        <StyledTable>
            <thead>
                <tr>
                    <Th $align="left">Agent</Th>
                    <Th>Calls</Th>
                    <Th>Prompt</Th>
                    <Th>Completion</Th>
                    <Th>Reasoning</Th>
                    <Th>Total</Th>
                    <Th>Avg/Run</Th>
                    <Th>Std Dev</Th>
                </tr>
            </thead>
            <tbody>
                {keys.map((key) => {
                    const a = data[key];
                    return (
                        <tr key={key}>
                            <Td $align="left">
                                <Dot style={{ background: colors[key] }} />
                                {prettyName(key)}
                            </Td>
                            <Td>{a.total_calls}</Td>
                            <Td>{fmt(a.total_prompt_tokens)}</Td>
                            <Td>{fmt(a.total_completion_tokens)}</Td>
                            <Td>{fmt(a.total_reasoning_tokens)}</Td>
                            <Td>{fmt(a.total_tokens)}</Td>
                            <Td>{fmt(Math.round(a.mean_tokens_per_run))}</Td>
                            <Td>{fmt(Math.round(a.stddev_tokens_per_run))}</Td>
                        </tr>
                    );
                })}
                <TotalRow>
                    <Td $align="left">Total</Td>
                    <Td>{totals.calls}</Td>
                    <Td>{fmt(totals.prompt)}</Td>
                    <Td>{fmt(totals.completion)}</Td>
                    <Td>{fmt(totals.reasoning)}</Td>
                    <Td>{fmt(totals.total)}</Td>
                    <Td />
                    <Td />
                </TotalRow>
            </tbody>
        </StyledTable>
    );
}

// Styled Components

const CardGrid = styled(Box)<{ $count: number }>`
    display: grid;
    grid-template-columns: repeat(${({ $count }) => $count}, 1fr);
    gap: ${({ theme }) => theme.spacing(1.5)};
    margin-bottom: ${({ theme }) => theme.spacing(2.5)};
`;

const StatCard = styled(Box)`
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 12px;
    padding: ${({ theme }) => theme.spacing(2, 1.5)};
    text-align: center;
`;

const StatValue = styled(Typography)`
    font-size: 1.2rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const StatLabel = styled(Typography)`
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    margin-top: 2px;
`;

const StatSub = styled(Typography)`
    font-size: 0.6rem;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    margin-top: 2px;
`;

const Panel = styled(Box)`
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
    padding: ${({ theme }) => theme.spacing(3, 2.5)};
    margin-bottom: ${({ theme }) => theme.spacing(2)};
`;

const PanelTitle = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const PanelSubtitle = styled('span')`
    font-weight: 300;
    font-size: 0.78rem;
    margin-left: 6px;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
`;

const LegendRow = styled(Box)`
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    padding-left: 160px;
`;

const LegendItem = styled(Box)`
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.72rem;
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const LegendDot = styled(Box)`
    width: 9px;
    height: 9px;
    border-radius: 3px;
`;

const StackedRow = styled(Box)`
    display: grid;
    grid-template-columns: 148px 1fr 80px;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
`;

const StackedLabel = styled(Typography)`
    font-size: 0.75rem;
    text-align: right;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const StackedTrack = styled(Box)`
    height: 28px;
    display: flex;
    border-radius: 5px;
    overflow: hidden;
`;

const StackedSeg = styled(Box)`
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
    transition: width 0.5s ease;
`;

const SegLabel = styled('span')`
    font-size: 0.56rem;
    font-weight: 600;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    padding: 0 4px;
`;

const StackedTotal = styled(Typography)`
    font-size: 0.7rem;
    font-variant-numeric: tabular-nums;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
    text-align: right;
`;

const BarRow = styled(Box)`
    display: grid;
    grid-template-columns: 148px 1fr 80px;
    align-items: center;
    gap: 12px;
`;

const BarLabel = styled(Typography)`
    font-size: 0.75rem;
    text-align: right;
    font-weight: 500;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const BarTrack = styled(Box)`
    position: relative;
    height: 28px;
    display: flex;
    align-items: center;
`;

const BarFill = styled(Box)`
    height: 100%;
    border-radius: 5px;
    display: flex;
    align-items: center;
    min-width: 2px;
    transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
    position: relative;
`;

const BarValue = styled('span')<{ $outside: boolean }>`
    font-size: 0.65rem;
    font-weight: 600;
    white-space: nowrap;
    padding: 0 8px;
    ${({ $outside }) =>
        $outside
            ? `
        position: absolute;
        left: calc(100% + 6px);
        color: rgba(255,255,255,0.8);
    `
            : `
        color: #fff;
    `}
`;

const BarAnnotation = styled(Typography)`
    font-size: 0.62rem;
    font-variant-numeric: tabular-nums;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    text-align: right;
    white-space: nowrap;
`;

const StyledTable = styled('table')`
    width: 100%;
    border-collapse: collapse;
`;

const Th = styled('th')<{ $align?: string }>`
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 500;
    text-align: ${({ $align }) => $align || 'right'};
    padding: 0 10px 10px;
    border-bottom: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const Td = styled('td')<{ $align?: string }>`
    font-size: 0.72rem;
    font-variant-numeric: tabular-nums;
    text-align: ${({ $align }) => $align || 'right'};
    padding: 10px;
    border-bottom: 1px solid
        ${({ theme }) => theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
`;

const Dot = styled('span')`
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    margin-right: 7px;
    vertical-align: middle;
`;

const TotalRow = styled('tr')`
    & td {
        font-weight: 700;
        border-bottom: none;
        border-top: 1px solid
            ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    }
`;
