import { useEffect, useRef, useState } from 'react';
import { styled, Typography, IconButton } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RemoveIcon from '@mui/icons-material/Remove';
import CenterFocusStrongIcon from '@mui/icons-material/CenterFocusStrong';
import * as d3 from 'd3';

import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { Experiment, BeliefDistribution } from '@/types/Run';

// Type definitions for D3 tree nodes
type D3TreeNode = {
    id: string;
    parent_id: string | null;
    belief_change: number | null;
    prior: BeliefDistribution | null;
    posterior: BeliefDistribution | null;
};

type TreeNode = {
    data: D3TreeNode;
    children?: TreeNode[];
};

// Extend D3's HierarchyPointNode with our custom fields
interface ExtendedHierarchyPointNode extends d3.HierarchyPointNode<TreeNode> {
    angle?: number;
    xPos?: number;
    yPos?: number;
}

// Transform Experiment to D3TreeNode format
const toD3TreeNode = (exp: Experiment): D3TreeNode => ({
    id: exp.experimentId,
    parent_id: exp.parentId,
    belief_change: exp.surprise,
    prior: exp.priorBelief,
    posterior: exp.posteriorBelief,
});

// Calculate node color based on belief change (surprisal)
const surprisalColor = (node: D3TreeNode): string => {
    const priorMean = node.prior?.mean ?? node.prior?._empirical_mean;
    const postMean = node.posterior?.mean ?? node.posterior?._empirical_mean;

    if (typeof priorMean !== 'number' || typeof postMean !== 'number') {
        return '#94a3b8'; // default gray for nodes without belief data
    }

    const delta = postMean - priorMean;
    const intensity = Math.max(0, Math.min(1, Math.abs(node.belief_change ?? delta ?? 0)));

    const hue = delta >= 0 ? 145 : 0; // green for positive, red for negative
    const saturation = 60 + 30 * intensity;
    const lightness = 80 - 45 * intensity;

    return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// Build tree hierarchy from flat experiment array
const buildHierarchy = (experiments: Experiment[]): d3.HierarchyNode<TreeNode> | null => {
    if (experiments.length === 0) return null;

    const byId = new Map(experiments.map((e) => [e.experimentId, e]));

    // Check if we need to create a fake root node (node_1_0)
    const needsFakeRoot = experiments.some((e) => e.parentId === 'node_1_0' && !byId.has('node_1_0'));

    let root: Experiment | null = null;
    let allExperiments = experiments;

    if (needsFakeRoot) {
        // Create a fake root node
        const fakeRoot: Experiment = {
            experimentId: 'node_1_0',
            parentId: null,
            childIds: experiments.filter((e) => e.parentId === 'node_1_0').map((e) => e.experimentId),
            creationIdx: -1,
            idInRun: 0,
            status: 'FAKE_ROOT',
            isSurprising: false,
            surprise: null,
            prior: null,
            posterior: null,
            priorBelief: null,
            posteriorBelief: null,
            runtimeMs: null,
            hypothesis: null,
            analysis: null,
            experimentPlan: null,
            review: null,
            code: null,
            codeOutput: null,
            richOutputs: null,
        };
        allExperiments = [fakeRoot, ...experiments];
        byId.set('node_1_0', fakeRoot);
        root = fakeRoot;
    } else {
        // Find root node (no parentId or parentId not in set)
        root = allExperiments.find((e) => !e.parentId || !byId.has(e.parentId)) || null;
    }

    if (!root) return null;

    const toTree = (exp: Experiment): TreeNode => ({
        data: toD3TreeNode(exp),
        children: allExperiments
            .filter((e) => e.parentId === exp.experimentId)
            .map(toTree)
            .filter(Boolean),
    });

    return d3.hierarchy(toTree(root));
};

// Adjust angular spacing to prevent node overlaps
const adjustAngularSpacing = (layout: ExtendedHierarchyPointNode, radius: number) => {
    const minDist = 48; // minimum pixel distance between nodes
    const depthBuckets = new Map<number, ExtendedHierarchyPointNode[]>();

    // Group nodes by depth level
    layout.descendants().forEach((d: ExtendedHierarchyPointNode) => {
        if (!depthBuckets.has(d.depth)) {
            depthBuckets.set(d.depth, []);
        }
        depthBuckets.get(d.depth)!.push(d);
    });

    // Iteratively adjust angles to enforce minimum spacing
    depthBuckets.forEach((arr) => {
        if (arr.length < 2) return;

        const r = Math.max(arr[0]?.y || radius, 1);
        const maxIter = 12;

        for (let iter = 0; iter < maxIter; iter++) {
            let moved = false;

            for (let i = 0; i < arr.length; i++) {
                for (let j = i + 1; j < arr.length; j++) {
                    const a = arr[i];
                    const b = arr[j];

                    // Calculate shortest angular difference (wrap-aware)
                    let diff = (b.angle ?? 0) - (a.angle ?? 0);
                    diff = ((diff + Math.PI) % (2 * Math.PI)) - Math.PI;

                    const gapArc = Math.abs(diff) * r;
                    if (gapArc < minDist) {
                        const delta = (minDist / r - Math.abs(diff)) / 2;
                        const sign = diff >= 0 ? 1 : -1;
                        a.angle = (a.angle ?? 0) - delta * sign;
                        b.angle = (b.angle ?? 0) + delta * sign;
                        moved = true;
                    }
                }
            }

            if (!moved) break;
        }

        // Recalculate Cartesian positions after angle adjustments
        arr.forEach((d) => {
            d.xPos = d.y * Math.cos(d.angle ?? 0);
            d.yPos = d.y * Math.sin(d.angle ?? 0);
        });
    });
};

export const ExperimentGraph = () => {
    const { experiments, selectedExperiment, selectExperiment } = useRunExperiments();

    const svgRef = useRef<SVGSVGElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
    const [hasInteracted, setHasInteracted] = useState(false);
    const currentTransformRef = useRef<d3.ZoomTransform>(d3.zoomIdentity);
    const zoomBehaviorRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown>>();

    // Set up resize observer
    useEffect(() => {
        if (!containerRef.current) return;

        const observer = new ResizeObserver((entries) => {
            const { width, height } = entries[0].contentRect;
            setDimensions({ width, height });
        });

        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    // Main D3 rendering effect
    useEffect(() => {
        if (!svgRef.current || experiments.length === 0) {
            // Clear SVG if no experiments
            if (svgRef.current) {
                d3.select(svgRef.current).selectAll('*').remove();
            }
            return;
        }

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        // Build hierarchy
        const hierarchy = buildHierarchy(experiments);
        if (!hierarchy) return;

        // Configure radial tree layout
        const radius = Math.min(dimensions.width, dimensions.height) / 2 - 40;
        const tree = d3
            .tree<TreeNode>()
            .size([2 * Math.PI, radius])
            .separation((a, b) => {
                const base = a.parent === b.parent ? 1 : 2;
                const minPx = 42;
                const r = (a.y + b.y) / 2 || radius;
                const minAngle = minPx / r;
                return Math.max(base, minAngle);
            });

        const layout = tree(hierarchy) as ExtendedHierarchyPointNode;

        // Calculate polar coordinates
        layout.each((d: ExtendedHierarchyPointNode) => {
            d.angle = d.x - Math.PI / 2;
            d.xPos = d.y * Math.cos(d.angle);
            d.yPos = d.y * Math.sin(d.angle);
        });

        // Adjust angular spacing to prevent overlaps
        adjustAngularSpacing(layout, radius);

        // Create groups for links and nodes
        const graphG = svg.append('g').attr('class', 'tree-group');
        const linksG = graphG.append('g').attr('class', 'links');
        const nodesG = graphG.append('g').attr('class', 'nodes');

        // Render links
        const links = layout.links();
        linksG
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('x1', (d: any) => d.source.xPos ?? 0)
            .attr('y1', (d: any) => d.source.yPos ?? 0)
            .attr('x2', (d: any) => d.target.xPos ?? 0)
            .attr('y2', (d: any) => d.target.yPos ?? 0)
            .attr('stroke', '#334155')
            .attr('stroke-width', 1.2)
            .attr('fill', 'none');

        // Render nodes
        const nodes = layout.descendants() as ExtendedHierarchyPointNode[];
        nodesG
            .selectAll('circle')
            .data(nodes)
            .join('circle')
            .attr('cx', (d) => d.xPos ?? 0)
            .attr('cy', (d) => d.yPos ?? 0)
            .attr('r', 18)
            .attr('fill', (d) => surprisalColor(d.data.data))
            .attr('stroke', (d) => {
                const isSelected = d.data.data.id === selectedExperiment?.experimentId;
                return isSelected ? '#fbbf24' : '#0f172a';
            })
            .attr('stroke-width', (d) => {
                const isSelected = d.data.data.id === selectedExperiment?.experimentId;
                return isSelected ? 3 : 1.5;
            })
            .attr('opacity', (d) => (d.data.data.id === 'node_1_0' ? 0.3 : 1))
            .style('cursor', (d) => (d.data.data.id === 'node_1_0' ? 'default' : 'pointer'))
            .on('click', (_event, d) => {
                // Don't allow clicking the fake root node
                if (d.data.data.id === 'node_1_0') return;

                const experiment = experiments.find((e) => e.experimentId === d.data.data.id);
                if (experiment) {
                    selectExperiment(experiment);
                }
            });

        // Set up zoom behavior
        const zoom = d3
            .zoom<SVGSVGElement, unknown>()
            .scaleExtent([0.4, 3])
            .on('zoom', (event) => {
                if (!hasInteracted) setHasInteracted(true);
                currentTransformRef.current = event.transform;
                graphG.attr('transform', event.transform.toString());
            });

        zoomBehaviorRef.current = zoom;
        svg.call(zoom);

        // Center tree initially or preserve previous transform
        const centerTransform = d3.zoomIdentity.translate(
            dimensions.width / 2,
            dimensions.height / 2
        );

        if (
            currentTransformRef.current.k === 1 &&
            currentTransformRef.current.x === 0 &&
            currentTransformRef.current.y === 0
        ) {
            // First render - initialize zoom with centered transform
            svg.call(zoom.transform, centerTransform);
            currentTransformRef.current = centerTransform;
        } else {
            // Preserve zoom/pan from previous render
            svg.call(zoom.transform, currentTransformRef.current);
        }
    }, [experiments, dimensions, selectedExperiment, selectExperiment, hasInteracted]);

    // Zoom control handlers
    const handleZoomIn = () => {
        if (!svgRef.current || !zoomBehaviorRef.current) return;
        const svg = d3.select(svgRef.current);
        svg.transition().duration(250).call(zoomBehaviorRef.current.scaleBy, 1.3);
    };

    const handleZoomOut = () => {
        if (!svgRef.current || !zoomBehaviorRef.current) return;
        const svg = d3.select(svgRef.current);
        svg.transition().duration(250).call(zoomBehaviorRef.current.scaleBy, 0.77);
    };

    const handleResetView = () => {
        if (!svgRef.current || !zoomBehaviorRef.current) return;
        const svg = d3.select(svgRef.current);
        const centerTransform = d3.zoomIdentity.translate(
            dimensions.width / 2,
            dimensions.height / 2
        );
        svg.transition()
            .duration(250)
            .call(zoomBehaviorRef.current.transform, centerTransform)
            .on('end', () => {
                // Reset interaction state after animation completes
                setHasInteracted(false);
            });
    };

    // Handle empty state
    if (experiments.length === 0) {
        return (
            <GraphContainer ref={containerRef}>
                <EmptyState>
                    <Typography variant="body2" color="textSecondary">
                        No experiments to display
                    </Typography>
                </EmptyState>
            </GraphContainer>
        );
    }

    return (
        <GraphContainer ref={containerRef}>
            <StyledSVG ref={svgRef} />

            {/* Stats Overlay */}
            <StatsOverlay>
                <Typography variant="caption" sx={{ color: '#0fcb8c' }}>
                    {experiments.length} {experiments.length === 1 ? 'experiment' : 'experiments'}
                </Typography>
            </StatsOverlay>

            {/* Color Legend */}
            <LegendOverlay>
                <Typography variant="caption" fontWeight="bold" sx={{ color: '#faf2e9', mb: 0.5 }}>
                    Belief Change
                </Typography>
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: 'hsl(145, 90%, 35%)' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        Increased confidence
                    </Typography>
                </LegendItem>
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: 'hsl(0, 90%, 35%)' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        Decreased confidence
                    </Typography>
                </LegendItem>
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: '#94a3b8' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        No belief data
                    </Typography>
                </LegendItem>
            </LegendOverlay>

            {/* Zoom Controls */}
            <ControlsOverlay>
                <ZoomControls>
                    <StyledIconButton size="small" onClick={handleZoomIn}>
                        <AddIcon fontSize="small" />
                    </StyledIconButton>
                    <StyledIconButton size="small" onClick={handleZoomOut}>
                        <RemoveIcon fontSize="small" />
                    </StyledIconButton>
                </ZoomControls>
                {hasInteracted && (
                    <StyledIconButton size="small" onClick={handleResetView}>
                        <CenterFocusStrongIcon fontSize="small" />
                    </StyledIconButton>
                )}
            </ControlsOverlay>
        </GraphContainer>
    );
};

// Styled Components
const GraphContainer = styled('div')`
    width: 100%;
    height: 100%;
    position: relative;
    overflow: hidden;
`;

const StyledSVG = styled('svg')`
    width: 100%;
    height: 100%;
    display: block;
    cursor: grab;

    &:active {
        cursor: grabbing;
    }
`;

const EmptyState = styled('div')`
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
`;

const StatsOverlay = styled('div')`
    position: absolute;
    top: 16px;
    left: 16px;
    background: rgba(22, 54, 56, 0.9);
    border-radius: 8px;
    padding: 8px 12px;
    z-index: 10;
    backdrop-filter: blur(4px);
`;

const LegendOverlay = styled('div')`
    position: absolute;
    bottom: 16px;
    right: 16px;
    background: rgba(22, 54, 56, 0.9);
    border-radius: 8px;
    padding: 12px;
    z-index: 10;
    backdrop-filter: blur(4px);
    display: flex;
    flex-direction: column;
    gap: 4px;
`;

const LegendItem = styled('div')`
    display: flex;
    align-items: center;
    gap: 8px;
`;

const LegendCircle = styled('div')`
    width: 16px;
    height: 16px;
    border-radius: 50%;
    flex-shrink: 0;
`;

const ControlsOverlay = styled('div')`
    position: absolute;
    top: 16px;
    right: 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    z-index: 10;
`;

const ZoomControls = styled('div')`
    display: flex;
    flex-direction: column;
    gap: 4px;
`;

const StyledIconButton = styled(IconButton)`
    background: rgba(22, 54, 56, 0.9);
    backdrop-filter: blur(4px);
    color: #0fcb8c;

    &:hover {
        background: rgba(22, 54, 56, 1);
        color: #3fd5a3;
    }
`;
