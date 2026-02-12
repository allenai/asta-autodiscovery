'use client';

import { useState } from 'react';
import { Box, Typography, styled } from '@mui/material';

import type { DailyMetrics } from '@/types/Metrics';

interface CostBreakdownChartProps {
    timeSeries: DailyMetrics[];
}

function fmtAxis(v: number): string {
    if (v >= 1) return `$${v.toFixed(0)}`;
    if (v >= 0.1) return `$${v.toFixed(1)}`;
    return `$${v.toFixed(2)}`;
}

function niceMax(v: number): number {
    if (v <= 0) return 0.01;
    const order = Math.pow(10, Math.floor(Math.log10(v)));
    const mantissa = v / order;
    if (mantissa <= 1) return order;
    if (mantissa <= 2) return 2 * order;
    if (mantissa <= 5) return 5 * order;
    return 10 * order;
}

export default function CostBreakdownChart({ timeSeries }: CostBreakdownChartProps) {
    const [hovered, setHovered] = useState<DailyMetrics | null>(null);
    const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

    if (timeSeries.length === 0) {
        return (
            <ChartPanel>
                <PanelTitle>Daily LLM Cost</PanelTitle>
                <Typography
                    variant="body2"
                    sx={{
                        color: (theme: any) =>
                            theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)',
                    }}>
                    No data available.
                </Typography>
            </ChartPanel>
        );
    }

    const rawMax = Math.max(...timeSeries.map((d) => d.llm_cost_usd), 0.01);
    const maxCost = niceMax(rawMax);

    // Show at most last 30 days
    const recent = timeSeries.slice(-30);

    // Y-axis ticks (0, 25%, 50%, 75%, 100%)
    const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
        value: maxCost * f,
        pct: f * 100,
    }));

    return (
        <ChartPanel>
            <PanelTitle>Daily LLM Cost</PanelTitle>
            <ChartArea>
                <YAxis>
                    {ticks
                        .slice()
                        .reverse()
                        .map((t) => (
                            <YTick key={t.pct}>{fmtAxis(t.value)}</YTick>
                        ))}
                </YAxis>
                <BarRegion>
                    {/* Grid lines — offset by 18px for day labels below bars */}
                    {ticks.slice(1).map((t) => (
                        <GridLine key={t.pct} style={{ bottom: `${18 + (t.pct / 100) * 120}px` }} />
                    ))}
                    <BarContainer>
                        {recent.map((day) => {
                            const llmPct = (day.llm_cost_usd / maxCost) * 100;
                            return (
                                <DayColumn
                                    key={day.date}
                                    onMouseEnter={(e) => {
                                        setHovered(day);
                                        const rect = (
                                            e.currentTarget as HTMLElement
                                        ).getBoundingClientRect();
                                        const parent = (e.currentTarget as HTMLElement)
                                            .closest('[data-chart-area]')
                                            ?.getBoundingClientRect();
                                        if (parent) {
                                            setTooltipPos({
                                                x: rect.left - parent.left + rect.width / 2,
                                                y: rect.top - parent.top,
                                            });
                                        }
                                    }}
                                    onMouseLeave={() => setHovered(null)}>
                                    <StackedBar>
                                        <BarSegment
                                            style={{ height: `${llmPct}%`, background: '#818cf8' }}
                                        />
                                    </StackedBar>
                                    <DayLabel>{day.date.slice(5)}</DayLabel>
                                </DayColumn>
                            );
                        })}
                    </BarContainer>
                    {hovered && (
                        <Tooltip
                            style={{
                                left: Math.min(tooltipPos.x, 280),
                                top: Math.max(tooltipPos.y - 8, 0),
                                transform: 'translate(-50%, -100%)',
                            }}>
                            <TooltipDate>{hovered.date}</TooltipDate>
                            <TooltipRow>
                                <TooltipDot style={{ background: '#818cf8' }} />
                                LLM: ${hovered.llm_cost_usd.toFixed(2)}
                            </TooltipRow>
                        </Tooltip>
                    )}
                </BarRegion>
            </ChartArea>
        </ChartPanel>
    );
}

const ChartPanel = styled(Box)`
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 14px;
    padding: ${({ theme }) => theme.spacing(3, 2.5)};
`;

const PanelTitle = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    margin-bottom: ${({ theme }) => theme.spacing(1)};
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
`;

const ChartArea = styled(Box)`
    display: flex;
    gap: 4px;
`;

ChartArea.defaultProps = { 'data-chart-area': true } as any;

const YAxis = styled(Box)`
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 140px;
    padding-bottom: 20px;
    flex-shrink: 0;
    width: 40px;
`;

const YTick = styled(Typography)`
    font-size: 0.5rem;
    font-variant-numeric: tabular-nums;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    text-align: right;
    line-height: 1;
`;

const BarRegion = styled(Box)`
    flex: 1;
    position: relative;
    height: 140px;
    min-width: 0;
`;

const GridLine = styled(Box)`
    position: absolute;
    left: 0;
    right: 0;
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    pointer-events: none;
`;

const BarContainer = styled(Box)`
    display: flex;
    gap: 3px;
    align-items: flex-end;
    height: 140px;
    overflow-x: auto;
`;

const DayColumn = styled(Box)`
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    min-width: 20px;
    cursor: pointer;

    &:hover > div:first-of-type {
        opacity: 0.85;
    }
`;

const StackedBar = styled(Box)`
    display: flex;
    flex-direction: column-reverse;
    width: 100%;
    max-width: 24px;
    height: 120px;
    border-radius: 3px 3px 0 0;
    overflow: hidden;
    transition: opacity 0.15s;
`;

const BarSegment = styled(Box)`
    width: 100%;
    min-height: 0;
    transition: height 0.4s ease;
`;

const DayLabel = styled(Typography)`
    font-size: 0.52rem;
    color: ${({ theme }) => theme.color['cream-40']?.rgba?.toString() || 'rgba(255,255,255,0.4)'};
    margin-top: 2px;
    white-space: nowrap;
`;

const Tooltip = styled(Box)`
    position: absolute;
    z-index: 10;
    background: rgba(20, 24, 32, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 8px;
    padding: 8px 12px;
    pointer-events: none;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
`;

const TooltipDate = styled(Typography)`
    font-size: 0.7rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['cream-100']?.hex || '#fff'};
    margin-bottom: 4px;
`;

const TooltipRow = styled(Box)`
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.68rem;
    color: ${({ theme }) => theme.color['cream-80']?.rgba?.toString() || 'rgba(255,255,255,0.8)'};
    line-height: 1.6;
`;

const TooltipDot = styled(Box)`
    width: 7px;
    height: 7px;
    border-radius: 2px;
    flex-shrink: 0;
`;
