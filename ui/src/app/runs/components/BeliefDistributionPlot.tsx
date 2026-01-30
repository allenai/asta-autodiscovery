'use client';

import { Box, Typography, styled } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useEffect, useMemo, useRef } from 'react';
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
const safeNumber = (value: number | null | undefined) =>
    Number.isFinite(value) ? (value as number) : 0;

// Converts a categorical belief payload into beta parameters by distributing each
// category count across alpha/beta according to its score weight.
const toBetaParams = (belief: BeliefDistribution | null) => {
    const priorParams = belief?.prior_params;
    if (!belief || !priorParams || priorParams.length < 2) {
        return null;
    }

    let alpha = safeNumber(priorParams[0]);
    let beta = safeNumber(priorParams[1]);

    (Object.entries(SCORE_PER_CATEGORY) as Array<
        [keyof typeof SCORE_PER_CATEGORY, number]
    >).forEach(([key, score]) => {
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
        name: `${label} (α=${params.alpha.toFixed(2)}, β=${params.beta.toFixed(2)})`,
        line: { color, width: 2 },
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

    // Memoize to avoid re-sampling beta curves on every render when inputs are unchanged.
    const plotPayload = useMemo(() => {
        const priorParams = toBetaParams(prior);
        const posteriorParams = toBetaParams(posterior);
        if (!priorParams && !posteriorParams) {
            return null;
        }

        // Build only the traces that exist so missing belief payloads still render.
        const traces = [
            priorParams
                ? toTrace('Prior', priorParams, theme.palette.primary.main)
                : null,
            posteriorParams
                ? toTrace('Posterior', posteriorParams, theme.palette.secondary.main)
                : null,
        ].filter(Boolean) as ReturnType<typeof toTrace>[];

        // Use theme-driven colors to keep axes readable against dark backgrounds.
        const axisColor = theme.color['cream-40']?.rgba?.toString?.() ?? theme.color['cream-100'].hex;
        const gridColor = theme.color['cream-10']?.rgba?.toString?.() ?? 'rgba(255,255,255,0.08)';

        const layout = {
            autosize: true,
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
            margin: { t: 20, r: 16, b: 40, l: 48 },
            showlegend: true,
            legend: { orientation: 'h', x: 0, y: -0.2, font: { color: axisColor } },
            xaxis: {
                title: 'Belief value',
                range: [0, 1],
                color: axisColor,
                gridcolor: gridColor,
                zerolinecolor: gridColor,
            },
            yaxis: {
                title: 'Density',
                color: axisColor,
                gridcolor: gridColor,
                zerolinecolor: gridColor,
            },
        };

        const config = {
            displayModeBar: false,
            responsive: true,
        };

        return { traces, layout, config };
    }, [prior, posterior, theme]);

    useEffect(() => {
        const node = plotContainerRef.current;
        if (!node || !plotPayload) {
            return undefined;
        }

        let plotly: any;

        // Lazy-load Plotly to keep the main bundle smaller and avoid SSR issues.
        const renderPlot = async () => {
            const module = await import('plotly.js-dist-min');
            plotly = (module as any).default ?? module;
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
        <PlotWrapper>
            <Typography variant="subtitle2">Belief Distribution</Typography>
            <Typography variant="caption" sx={{ opacity: 0.7 }}>
                Beta Distributions computed from Category Scores.
            </Typography>
            <PlotContainer ref={plotContainerRef} />
        </PlotWrapper>
    );
}

const PlotWrapper = styled(Box)(({ theme }) => ({
    border: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    borderRadius: '16px',
    padding: theme.spacing(2),
    backgroundColor: theme.color['extra-dark-teal-100'].hex,
}));

const PlotContainer = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(2),
    width: '100%',
    minHeight: '240px',
}));
