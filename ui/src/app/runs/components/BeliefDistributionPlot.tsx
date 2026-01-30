'use client';

import { styled } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useEffect, useMemo, useRef, useState } from 'react';
import betaPdf from '@stdlib/stats-base-dists-beta-pdf';

import type { BeliefDistribution } from '@/types/Run';

type BeliefDistributionPlotProps = {
    prior: BeliefDistribution | null;
    posterior: BeliefDistribution | null;
};

// Encodes the belief-category -> score mapping so we can convert categorical counts
// into a single beta distribution (alpha/beta).
const SCORE_PER_CATEGORY = {
    definitely_false: 0.0,
    maybe_false: 0.25,
    uncertain: 0.5,
    maybe_true: 0.75,
    definitely_true: 1.0,
} as const;

// Normalizes missing/invalid values to 0 so partial data doesn't crash the plot.
const safeNumber = (value: unknown) =>
    typeof value === 'number' && Number.isFinite(value) ? value : 0;

// Converts a categorical belief payload into beta parameters by distributing each
// category count across alpha/beta according to its score weight.
const toBetaParams = (belief: BeliefDistribution | null) => {
    const priorParams = belief?.prior_params;
    if (!belief || !priorParams || priorParams.length < 2) {
        return null;
    }

    let alpha = safeNumber(priorParams[0]);
    let beta = safeNumber(priorParams[1]);

    const scoreEntries = Object.entries(SCORE_PER_CATEGORY) as Array<
        [keyof typeof SCORE_PER_CATEGORY, number]
    >;

    scoreEntries.forEach(([key, score]) => {
        const count = safeNumber(belief[key as keyof BeliefDistribution]);
        alpha += count * score;
        beta += count * (1 - score);
    });

    return alpha > 0 && beta > 0 ? { alpha, beta } : null;
};

// Samples the beta PDF on a fixed grid; epsilon avoids singularities at 0/1 for
// extreme alpha/beta while keeping the shape visually accurate.
const buildBetaSeries = (alpha: number, beta: number, points = 200) => {
    const epsilon = 1e-4;
    const step = (1 - 2 * epsilon) / (points - 1);
    const x = Array.from({ length: points }, (_, i) => epsilon + step * i);
    const y = x.map((value) => betaPdf(value, alpha, beta));
    return { x, y };
};

// Wraps trace construction for plot assembly.
const toTrace = (label: string, params: { alpha: number; beta: number }, color: string) => {
    const { x, y } = buildBetaSeries(params.alpha, params.beta);
    return {
        x,
        y,
        type: 'scatter' as const,
        mode: 'lines' as const,
        name: label,
        line: { color, width: 2.5 },
        hoverinfo: 'skip' as const,
    };
};

/**
 * Renders a Plotly beta distribution comparison for prior and posterior beliefs.
 *
 * Args:
 *   prior: Belief distribution payload for the prior update.
 *   posterior: Belief distribution payload for the posterior update.
 */
export function BeliefDistributionPlot({ prior, posterior }: BeliefDistributionPlotProps) {
    const theme = useTheme() as any;
    const plotContainerRef = useRef<HTMLDivElement | null>(null);
    const [containerWidth, setContainerWidth] = useState<number | null>(null);

    useEffect(() => {
        if (!plotContainerRef.current) {
            return undefined;
        }
        const node = plotContainerRef.current;
        const observer = new ResizeObserver((entries) => {
            const entry = entries[0];
            if (entry?.contentRect) {
                setContainerWidth(entry.contentRect.width);
            }
        });
        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    // Memoize to avoid re-sampling beta curves on every render when inputs are unchanged.
    const plotPayload = useMemo(() => {
        const priorParams = toBetaParams(prior);
        const posteriorParams = toBetaParams(posterior);
        if (!priorParams && !posteriorParams) {
            return null;
        }

        const priorMean = priorParams
            ? priorParams.alpha / (priorParams.alpha + priorParams.beta)
            : null;
        const posteriorMean = posteriorParams
            ? posteriorParams.alpha / (posteriorParams.alpha + posteriorParams.beta)
            : null;

        // Build only the traces that exist so missing belief payloads still render.
        const traces = [
            priorParams
                ? toTrace('Belief before experiment', priorParams, theme.palette.primary.main)
                : null,
            posteriorParams
                ? toTrace('Belief after experiment', posteriorParams, theme.palette.secondary.main)
                : null,
        ].filter(Boolean) as ReturnType<typeof toTrace>[];

        // Use theme-driven colors to keep axes readable against dark backgrounds.
        const axisColor =
            theme.color['cream-40']?.rgba?.toString?.() ?? theme.color['cream-100'].hex;
        const gridColor = theme.color['cream-10']?.rgba?.toString?.() ?? 'rgba(255,255,255,0.08)';

        const verticalGridLines = Array.from({ length: 9 }, (_, idx) => ({
            type: 'line',
            xref: 'x',
            yref: 'paper',
            x0: (idx + 1) / 10,
            x1: (idx + 1) / 10,
            y0: 0,
            y1: 1,
            line: { color: gridColor, width: 1 },
        }));

        const meanLines = [
            priorMean !== null
                ? {
                      type: 'line',
                      xref: 'x',
                      yref: 'paper',
                      x0: priorMean,
                      x1: priorMean,
                      y0: 0,
                      y1: 1,
                      line: { color: theme.palette.primary.main, width: 1.5, dash: 'dot' },
                  }
                : null,
            posteriorMean !== null
                ? {
                      type: 'line',
                      xref: 'x',
                      yref: 'paper',
                      x0: posteriorMean,
                      x1: posteriorMean,
                      y0: 0,
                      y1: 1,
                      line: { color: theme.palette.secondary.main, width: 1.5, dash: 'dot' },
                  }
                : null,
        ].filter(Boolean);

        const surprisalLine =
            priorMean !== null && posteriorMean !== null
                ? [
                      {
                          type: 'line',
                          xref: 'x',
                          yref: 'paper',
                          x0: Math.min(priorMean, posteriorMean),
                          x1: Math.max(priorMean, posteriorMean),
                          y0: -0.16,
                          y1: -0.16,
                          line: { color: axisColor, width: 1.5 },
                      },
                      {
                          type: 'line',
                          xref: 'x',
                          yref: 'paper',
                          x0: priorMean,
                          x1: priorMean,
                          y0: -0.18,
                          y1: -0.14,
                          line: { color: axisColor, width: 1.5 },
                      },
                      {
                          type: 'line',
                          xref: 'x',
                          yref: 'paper',
                          x0: posteriorMean,
                          x1: posteriorMean,
                          y0: -0.18,
                          y1: -0.14,
                          line: { color: axisColor, width: 1.5 },
                      },
                  ]
                : [];

        const clamp = (value: number, min: number, max: number) =>
            Math.max(min, Math.min(max, value));
        const meanOffset = 0.02;
        // Place labels on opposite sides based on mean ordering to reduce collisions,
        // and stagger vertically when means are close to keep both readable.
        const isCompact = (containerWidth ?? 800) < 640;
        const labelYTop = isCompact ? 1.08 : 1.12;
        const labelYBottom = isCompact ? 1.02 : 1.04;
        const meanLabelFontSize = isCompact ? 11 : 12;
        const axisLabelFontSize = isCompact ? 12 : 13;
        const meansClose =
            priorMean !== null && posteriorMean !== null
                ? Math.abs(priorMean - posteriorMean) < 0.12
                : false;
        const priorOnLeft =
            priorMean !== null && posteriorMean !== null ? priorMean < posteriorMean : true;

        const buildMeanLabel = ({
            mean,
            label,
            color,
            side,
            y,
        }: {
            mean: number;
            label: string;
            color: string;
            side: 'left' | 'right';
            y: number;
        }) => ({
            x: clamp(mean + (side === 'right' ? meanOffset : -meanOffset), 0.02, 0.98),
            y,
            xref: 'x',
            yref: 'paper',
            text: `${label}<br>Mean: ${mean.toFixed(2)}`,
            showarrow: false,
            xanchor: side === 'right' ? 'left' : 'right',
            align: side === 'right' ? 'left' : 'right',
            font: { color, size: meanLabelFontSize },
        });

        const priorLabel =
            priorMean !== null
                ? buildMeanLabel({
                      mean: priorMean,
                      label: 'Belief Before',
                      color: theme.palette.primary.main,
                      side: priorOnLeft ? 'left' : 'right',
                      y: meansClose && !priorOnLeft ? labelYBottom : labelYTop,
                  })
                : null;

        const posteriorLabel =
            posteriorMean !== null
                ? buildMeanLabel({
                      mean: posteriorMean,
                      label: 'Belief After',
                      color: theme.palette.secondary.main,
                      side: priorOnLeft ? 'right' : 'left',
                      y: meansClose && priorOnLeft ? labelYBottom : labelYTop,
                  })
                : null;

        const annotations = [
            priorLabel,
            posteriorLabel,
            {
                x: 0,
                y: -0.14,
                xref: 'x',
                yref: 'paper',
                text: 'Likely False',
                showarrow: false,
                xanchor: 'left',
                font: { color: axisColor, size: axisLabelFontSize },
            },
            {
                x: 1,
                y: -0.14,
                xref: 'x',
                yref: 'paper',
                text: 'Likely True',
                showarrow: false,
                xanchor: 'right',
                font: { color: axisColor, size: axisLabelFontSize },
            },
            priorMean !== null && posteriorMean !== null
                ? {
                      x: (priorMean + posteriorMean) / 2,
                      y: -0.28,
                      xref: 'x',
                      yref: 'paper',
                      text: 'Surprisal',
                      showarrow: false,
                      xanchor: 'center',
                      font: { color: axisColor, size: 13 },
                  }
                : null,
        ].filter(Boolean);

        const layout = {
            autosize: true,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: {
                t: isCompact ? 20 : 24,
                r: isCompact ? 44 : 66,
                b: isCompact ? 64 : 72,
                l: isCompact ? 44 : 66,
            },
            showlegend: false,
            hovermode: false,
            shapes: [...verticalGridLines, ...meanLines, ...surprisalLine],
            annotations,
            dragmode: false,
            xaxis: {
                range: [0, 1],
                color: axisColor,
                gridcolor: gridColor,
                zeroline: false,
                showticklabels: false,
                showline: false,
                ticklen: 0,
                ticklabelposition: 'outside',
                fixedrange: true,
            },
            yaxis: {
                color: axisColor,
                gridcolor: gridColor,
                zeroline: false,
                gridwidth: 1,
                showticklabels: false,
                showline: false,
                fixedrange: true,
            },
        };

        const config = {
            displayModeBar: false,
            responsive: true,
            scrollZoom: false,
            doubleClick: false,
        };

        return { traces, layout, config };
    }, [prior, posterior, theme, containerWidth]);

    useEffect(() => {
        const node = plotContainerRef.current;
        if (!node || !plotPayload) {
            return undefined;
        }

        let plotly: any;

        // Lazy-load Plotly to keep the main bundle smaller and avoid SSR issues.
        const renderPlot = async () => {
            const plotlyModule = await import('plotly.js-dist-min');
            plotly = (plotlyModule as any).default ?? plotlyModule;
            await plotly.react(node, plotPayload.traces, plotPayload.layout, plotPayload.config);
        };

        renderPlot();

        return () => {
            // Clean up the Plotly instance so it doesn't leak DOM handlers.
            if (plotly?.purge) {
                plotly.purge(node);
            }
        };
    }, [plotPayload]);

    if (!plotPayload) {
        return null;
    }

    return (
        <PlotContainer
            ref={plotContainerRef}
            style={{ minHeight: (containerWidth ?? 800) < 640 ? '260px' : '320px' }}
        />
    );
}

const PlotContainer = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(2),
    width: '100%',
    minHeight: '320px',
}));
