'use client';

import { styled } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import { useEffect, useId, useMemo, useRef, useState } from 'react';

import type { BeliefDistribution } from '@/types/Run';

type BeliefDistributionPlotProps = {
    prior: BeliefDistribution | null;
    posterior: BeliefDistribution | null;
    isSurprising?: boolean;
};

// Encodes the belief-category -> score mapping so we can convert categorical counts
// into a single point on the Likely False <-> Likely True axis.
const SCORE_PER_CATEGORY = {
    definitely_false: 0.0,
    maybe_false: 0.25,
    uncertain: 0.5,
    maybe_true: 0.75,
    definitely_true: 1.0,
} as const;

const safeNumber = (value: unknown) =>
    typeof value === 'number' && Number.isFinite(value) ? value : 0;

// Collapse a categorical belief distribution into a single 0-1 mean on the axis.
const toMean = (belief: BeliefDistribution | null): number | null => {
    const params = belief?.prior_params;
    if (!belief || !params || params.length < 2) {
        return null;
    }
    let alpha = safeNumber(params[0]);
    let beta = safeNumber(params[1]);
    (
        Object.entries(SCORE_PER_CATEGORY) as Array<[keyof typeof SCORE_PER_CATEGORY, number]>
    ).forEach(([key, score]) => {
        const count = safeNumber(belief[key as keyof BeliefDistribution]);
        alpha += count * score;
        beta += count * (1 - score);
    });
    if (alpha <= 0 || beta <= 0) {
        return null;
    }
    return alpha / (alpha + beta);
};

// Minimum gap between the two labels when they'd otherwise collide.
const LABEL_GAP_PX = 12;

const clampCenter = (center: number, width: number, bound: number) => {
    const half = width / 2;
    if (center - half < 0) return half;
    if (center + half > bound) return bound - half;
    return center;
};

export function BeliefDistributionPlot({
    prior,
    posterior,
    isSurprising,
}: BeliefDistributionPlotProps) {
    const theme = useTheme() as any;
    const markerId = useId();

    const { priorMean, posteriorMean } = useMemo(
        () => ({ priorMean: toMean(prior), posteriorMean: toMean(posterior) }),
        [prior, posterior]
    );

    const containerRef = useRef<HTMLDivElement>(null);
    const priorLabelRef = useRef<HTMLDivElement>(null);
    const posteriorLabelRef = useRef<HTMLDivElement>(null);
    const surprisalLabelRef = useRef<HTMLSpanElement>(null);
    const leftSideLabelRef = useRef<HTMLSpanElement>(null);
    const rightSideLabelRef = useRef<HTMLSpanElement>(null);
    const [labelOffsetsPx, setLabelOffsetsPx] = useState<{ prior: number; posterior: number }>({
        prior: 0,
        posterior: 0,
    });
    const [surprisalOffsetPx, setSurprisalOffsetPx] = useState(0);

    const priorPct = priorMean !== null ? priorMean * 100 : null;
    const posteriorPct = posteriorMean !== null ? posteriorMean * 100 : null;

    // Measure labels and container to resolve collisions and clamp to bounds.
    useEffect(() => {
        const container = containerRef.current;
        if (!container) return undefined;

        const recompute = () => {
            const containerWidth = container.offsetWidth;
            if (containerWidth === 0) return;

            const priorEl = priorLabelRef.current;
            const postEl = posteriorLabelRef.current;
            const priorWidth = priorEl?.offsetWidth ?? 0;
            const postWidth = postEl?.offsetWidth ?? 0;

            const priorDotX = priorPct !== null ? (priorPct * containerWidth) / 100 : null;
            const postDotX = posteriorPct !== null ? (posteriorPct * containerWidth) / 100 : null;

            let priorCenter = priorDotX ?? 0;
            let postCenter = postDotX ?? 0;

            if (priorDotX !== null && postDotX !== null) {
                const sep = (priorWidth + postWidth) / 2 + LABEL_GAP_PX;
                const leftIsPrior = priorDotX <= postDotX;
                const leftWidth = leftIsPrior ? priorWidth : postWidth;
                const rightWidth = leftIsPrior ? postWidth : priorWidth;
                const leftDotX = leftIsPrior ? priorDotX : postDotX;
                const rightDotX = leftIsPrior ? postDotX : priorDotX;

                let leftCenter = leftDotX;
                let rightCenter = rightDotX;

                // Resolve overlap by pushing outward from the midpoint, then repair
                // any boundary violations by transferring the deficit to the partner
                // so the required separation is preserved even when one side is pinned.
                if (rightCenter - leftCenter < sep) {
                    const midpoint = (leftDotX + rightDotX) / 2;
                    leftCenter = midpoint - sep / 2;
                    rightCenter = midpoint + sep / 2;
                }

                const leftMin = leftWidth / 2;
                const rightMax = containerWidth - rightWidth / 2;

                if (leftCenter < leftMin) {
                    leftCenter = leftMin;
                    if (rightCenter < leftCenter + sep) {
                        rightCenter = leftCenter + sep;
                    }
                }
                if (rightCenter > rightMax) {
                    rightCenter = rightMax;
                    if (leftCenter > rightCenter - sep) {
                        leftCenter = rightCenter - sep;
                    }
                }
                // Re-check left in case the right-clamp pushed it off the left edge
                // (happens only when the container is too narrow to fit both labels).
                if (leftCenter < leftMin) {
                    leftCenter = leftMin;
                }

                priorCenter = leftIsPrior ? leftCenter : rightCenter;
                postCenter = leftIsPrior ? rightCenter : leftCenter;
            } else {
                if (priorDotX !== null) {
                    priorCenter = clampCenter(priorCenter, priorWidth, containerWidth);
                }
                if (postDotX !== null) {
                    postCenter = clampCenter(postCenter, postWidth, containerWidth);
                }
            }

            setLabelOffsetsPx({
                prior: priorDotX !== null ? priorCenter - priorDotX : 0,
                posterior: postDotX !== null ? postCenter - postDotX : 0,
            });

            // Clamp the surprisal label so it doesn't collide with the fixed
            // "Likely False" / "Likely True" end labels. Same spirit as the
            // before/after collision pass, just with two immovable obstacles.
            const surpEl = surprisalLabelRef.current;
            if (surpEl && priorDotX !== null && postDotX !== null) {
                const surpWidth = surpEl.offsetWidth;
                const leftSideWidth = leftSideLabelRef.current?.offsetWidth ?? 0;
                const rightSideWidth = rightSideLabelRef.current?.offsetWidth ?? 0;
                const midpointX = (priorDotX + postDotX) / 2;
                const leftBound = leftSideWidth + LABEL_GAP_PX + surpWidth / 2;
                const rightBound = containerWidth - rightSideWidth - LABEL_GAP_PX - surpWidth / 2;
                let surpCenter = midpointX;
                if (surpCenter < leftBound) surpCenter = leftBound;
                if (surpCenter > rightBound) surpCenter = rightBound;
                setSurprisalOffsetPx(surpCenter - midpointX);
            } else {
                setSurprisalOffsetPx(0);
            }
        };

        recompute();

        const observer = new ResizeObserver(() => recompute());
        observer.observe(container);
        return () => observer.disconnect();
    }, [priorPct, posteriorPct, priorMean, posteriorMean, isSurprising]);

    if (priorMean === null && posteriorMean === null) {
        return null;
    }

    const pinkColor = theme.color['pink-100'].hex;
    const greenColor = theme.color['green-100'].hex;
    const surprisalColor = theme.color['warning-orange-100']?.hex ?? '#FFA31C';
    const creamColor = theme.color['cream-100'].hex;
    const axisLineColor = theme.color['cream-20']?.rgba?.toString?.() ?? 'rgba(255,255,255,0.3)';
    const mutedLabelColor = theme.color['cream-60']?.rgba?.toString?.() ?? 'rgba(255,255,255,0.7)';
    const arrowColor = isSurprising ? surprisalColor : creamColor;

    const hasArrow =
        priorPct !== null && posteriorPct !== null && Math.abs(priorPct - posteriorPct) > 0.5;
    const midpointPct = hasArrow ? ((priorPct as number) + (posteriorPct as number)) / 2 : null;
    const arrowMarkerId = `belief-arrow-${markerId}`;

    return (
        <PlotContainer ref={containerRef}>
            <LabelRow>
                {posteriorPct !== null && posteriorMean !== null && (
                    <TopLabel
                        ref={posteriorLabelRef}
                        style={{
                            left: `calc(${posteriorPct}% + ${labelOffsetsPx.posterior}px)`,
                            color: greenColor,
                        }}>
                        After ({posteriorMean.toFixed(3)})
                    </TopLabel>
                )}
                {priorPct !== null && priorMean !== null && (
                    <TopLabel
                        ref={priorLabelRef}
                        style={{
                            left: `calc(${priorPct}% + ${labelOffsetsPx.prior}px)`,
                            color: pinkColor,
                        }}>
                        Before ({priorMean.toFixed(3)})
                    </TopLabel>
                )}
            </LabelRow>

            <AxisTrack>
                <AxisSvg>
                    <defs>
                        <marker
                            id={arrowMarkerId}
                            markerWidth="10"
                            markerHeight="10"
                            refX="16"
                            refY="5"
                            orient="auto"
                            markerUnits="userSpaceOnUse">
                            <path
                                d="M0,0 L9,5 L0,10 z"
                                fill={arrowColor}
                                stroke={arrowColor}
                                strokeWidth="1"
                                strokeLinejoin="round"
                            />
                        </marker>
                    </defs>
                    <line
                        x1="0"
                        y1="50%"
                        x2="100%"
                        y2="50%"
                        stroke={axisLineColor}
                        strokeWidth="1"
                    />
                    {hasArrow && (
                        <line
                            x1={`${priorPct}%`}
                            y1="50%"
                            x2={`${posteriorPct}%`}
                            y2="50%"
                            stroke={arrowColor}
                            strokeWidth="1"
                            markerEnd={`url(#${arrowMarkerId})`}
                        />
                    )}
                </AxisSvg>
                {priorPct !== null && (
                    <Dot style={{ left: `${priorPct}%`, backgroundColor: pinkColor }} />
                )}
                {posteriorPct !== null && (
                    <Dot style={{ left: `${posteriorPct}%`, backgroundColor: greenColor }} />
                )}
            </AxisTrack>

            <BottomRow>
                <SideLabel ref={leftSideLabelRef} style={{ left: 0, color: mutedLabelColor }}>
                    Likely False
                </SideLabel>
                {isSurprising && midpointPct !== null && (
                    <SurprisalLabel
                        ref={surprisalLabelRef}
                        style={{
                            left: `calc(${midpointPct}% + ${surprisalOffsetPx}px)`,
                            color: surprisalColor,
                        }}>
                        Surprisal
                    </SurprisalLabel>
                )}
                <SideLabel ref={rightSideLabelRef} style={{ right: 0, color: mutedLabelColor }}>
                    Likely True
                </SideLabel>
            </BottomRow>
        </PlotContainer>
    );
}

const PlotContainer = styled('div')({
    margin: '16px 0 24px 0',
    width: '100%',
    position: 'relative',
});

const LabelRow = styled('div')({
    position: 'relative',
    height: '20px',
    marginBottom: '4px',
});

const TopLabel = styled('div')({
    position: 'absolute',
    bottom: 0,
    transform: 'translateX(-50%)',
    fontSize: '13px',
    fontWeight: 500,
    whiteSpace: 'nowrap',
});

const AxisTrack = styled('div')({
    position: 'relative',
    width: '100%',
    height: '12px',
});

const AxisSvg = styled('svg')({
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    overflow: 'visible',
});

const Dot = styled('div')({
    position: 'absolute',
    top: '50%',
    width: '14px',
    height: '14px',
    borderRadius: '50%',
    transform: 'translate(-50%, -50%)',
});

const BottomRow = styled('div')({
    position: 'relative',
    marginTop: '6px',
    height: '18px',
});

const SideLabel = styled('span')({
    position: 'absolute',
    top: 0,
    fontSize: '11px',
    whiteSpace: 'nowrap',
});

const SurprisalLabel = styled('span')({
    position: 'absolute',
    top: 0,
    transform: 'translateX(-50%)',
    fontSize: '11px',
    fontWeight: 500,
    whiteSpace: 'nowrap',
});
