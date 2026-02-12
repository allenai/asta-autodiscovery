'use client';

import { useState } from 'react';
import { Box, Typography, styled, Tab as MuiTab, Tabs } from '@mui/material';

import type { LLMUsageSummary, LLMUsageBucket } from '@/types/Metrics';

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

interface LLMUsageDashboardProps {
    usage: LLMUsageSummary;
    costByModel?: Record<string, number>;
}

export default function LLMUsageDashboard({ usage, costByModel }: LLMUsageDashboardProps) {
    const t = usage.totals;
    const hasReasoning = (t.reasoning_tokens || 0) > 0;

    // Summary cards
    const cards: { v: string; l: string }[] = [{ v: fmt(t.total_tokens), l: 'Total Tokens' }];
    if (hasReasoning) cards.push({ v: fmt(t.reasoning_tokens), l: 'Reasoning Tokens' });
    cards.push(
        { v: fmt(t.prompt_tokens), l: 'Prompt Tokens' },
        { v: fmt(t.completion_tokens), l: 'Completion Tokens' },
        { v: String(t.calls), l: 'Total Calls' }
    );

    // Available views
    type ViewKey = 'by_agent' | 'by_model' | 'by_node' | 'by_component';
    const viewDefs: { key: ViewKey; label: string }[] = [
        { key: 'by_agent', label: 'By Agent' },
        { key: 'by_model', label: 'By Model' },
        { key: 'by_node', label: 'By Node' },
        { key: 'by_component', label: 'By Component' },
    ];
    const views = viewDefs.filter((v) => usage[v.key] && Object.keys(usage[v.key]).length > 0);
    const [activeView, setActiveView] = useState(0);

    // Agent keys for stacked chart
    const agentKeys = Object.keys(usage.by_agent || {});

    return (
        <Box>
            {/* Summary Cards */}
            <CardGrid $count={cards.length}>
                {cards.map((c) => (
                    <StatCard key={c.l}>
                        <StatValue>{c.v}</StatValue>
                        <StatLabel>{c.l}</StatLabel>
                    </StatCard>
                ))}
            </CardGrid>

            {/* Stacked Composition */}
            {agentKeys.length > 0 && (
                <Panel>
                    <PanelTitle>
                        Token Composition{' '}
                        <PanelSubtitle>prompt / completion / reasoning per agent</PanelSubtitle>
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
                    {agentKeys.map((key) => {
                        const a = usage.by_agent[key];
                        const tot = a.total_tokens || 1;
                        const pP = (a.prompt_tokens / tot) * 100;
                        const cP = (a.completion_tokens / tot) * 100;
                        const rP = ((a.reasoning_tokens || 0) / tot) * 100;
                        return (
                            <StackedRow key={key}>
                                <StackedLabel>{prettyName(key)}</StackedLabel>
                                <StackedTrack>
                                    <StackedSeg style={{ width: `${pP}%`, background: '#818cf8' }}>
                                        {pP > 8 && <SegLabel>{fmt(a.prompt_tokens)}</SegLabel>}
                                    </StackedSeg>
                                    <StackedSeg style={{ width: `${cP}%`, background: '#f472b6' }}>
                                        {cP > 8 && <SegLabel>{fmt(a.completion_tokens)}</SegLabel>}
                                    </StackedSeg>
                                    {rP > 0 && (
                                        <StackedSeg
                                            style={{ width: `${rP}%`, background: '#2dd4bf' }}>
                                            {rP > 8 && (
                                                <SegLabel>{fmt(a.reasoning_tokens)}</SegLabel>
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
                    <TotalTokensChart
                        data={usage[views[activeView].key]}
                        costByModel={views[activeView].key === 'by_model' ? costByModel : undefined}
                    />
                </Panel>
            )}

            {/* Detail Table */}
            {agentKeys.length > 0 && (
                <Panel>
                    <PanelTitle>
                        Detailed Breakdown <PanelSubtitle>by agent</PanelSubtitle>
                    </PanelTitle>
                    <DetailTable usage={usage} />
                </Panel>
            )}
        </Box>
    );
}

function TotalTokensChart({
    data,
    costByModel,
}: {
    data: Record<string, LLMUsageBucket>;
    costByModel?: Record<string, number>;
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
                const cost = costByModel?.[key];
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
                                    {cost != null && ` ($${cost.toFixed(3)})`}
                                </BarValue>
                            </BarFill>
                        </BarTrack>
                    </BarRow>
                );
            })}
        </Box>
    );
}

function DetailTable({ usage }: { usage: LLMUsageSummary }) {
    const agentKeys = Object.keys(usage.by_agent);
    const colors = assignColors(agentKeys);
    const totals = { calls: 0, prompt: 0, completion: 0, reasoning: 0, total: 0 };

    agentKeys.forEach((key) => {
        const a = usage.by_agent[key];
        totals.calls += a.calls;
        totals.prompt += a.prompt_tokens;
        totals.completion += a.completion_tokens || 0;
        totals.reasoning += a.reasoning_tokens || 0;
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
                </tr>
            </thead>
            <tbody>
                {agentKeys.map((key) => {
                    const a = usage.by_agent[key];
                    return (
                        <tr key={key}>
                            <Td $align="left">
                                <Dot style={{ background: colors[key] }} />
                                {prettyName(key)}
                            </Td>
                            <Td>{a.calls}</Td>
                            <Td>{fmt(a.prompt_tokens)}</Td>
                            <Td>{fmt(a.completion_tokens)}</Td>
                            <Td>{fmt(a.reasoning_tokens)}</Td>
                            <Td>{fmt(a.total_tokens)}</Td>
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
    grid-template-columns: 148px 1fr;
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
