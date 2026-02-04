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

    if (delta >= 0) {
        // Positive belief change - use green with varying intensity
        const saturation = 60 + 30 * intensity;
        const lightness = 80 - 45 * intensity;
        return `hsl(145, ${saturation}%, ${lightness}%)`; // Green hue (145)
    } else {
        // Negative belief change - use red with varying intensity
        const saturation = 60 + 30 * intensity;
        const lightness = 80 - 45 * intensity;
        return `hsl(0, ${saturation}%, ${lightness}%)`; // Red hue (0)
    }
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

// Assign angular ranges to ensure children stay near parents and edges don't cross
const assignAngularRanges = (
    node: ExtendedHierarchyPointNode,
    minAngle: number,
    maxAngle: number
) => {
    const angleRange = maxAngle - minAngle;
    const children = node.children as ExtendedHierarchyPointNode[] | undefined;

    if (!children || children.length === 0) {
        // Leaf node - position at center of range
        node.angle = (minAngle + maxAngle) / 2;
        node.xPos = node.y * Math.cos(node.angle);
        node.yPos = node.y * Math.sin(node.angle);
        return;
    }

    // Count total leaves in each child's subtree for proportional allocation
    const getLeafCount = (n: ExtendedHierarchyPointNode): number => {
        if (!n.children || n.children.length === 0) return 1;
        return (n.children as ExtendedHierarchyPointNode[]).reduce(
            (sum, child) => sum + getLeafCount(child),
            0
        );
    };

    const totalLeaves = children.reduce((sum, child) => sum + getLeafCount(child), 0);

    // Distribute angular range among children proportionally
    let currentAngle = minAngle;
    children.forEach((child) => {
        const childLeaves = getLeafCount(child);
        const childAngleRange = (childLeaves / totalLeaves) * angleRange;
        const childMaxAngle = currentAngle + childAngleRange;

        assignAngularRanges(child, currentAngle, childMaxAngle);
        currentAngle = childMaxAngle;
    });

    // Position parent at center of its assigned range
    node.angle = (minAngle + maxAngle) / 2;
    node.xPos = node.y * Math.cos(node.angle);
    node.yPos = node.y * Math.sin(node.angle);
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

        // Assign angular ranges to keep children near parents and prevent crossings
        assignAngularRanges(layout, 0, 2 * Math.PI);

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
            .attr('fill', 'none')
            .style('cursor', 'pointer')
            .on('mouseover', function (_event, d: any) {
                // Highlight path from target node to root
                const pathIds = new Set<string>();
                let current = d.target;
                while (current) {
                    pathIds.add(current.data.data.id);
                    current = current.parent;
                }

                // Highlight nodes in path with brighter stroke
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    const isInPath = pathIds.has(n.data.data.id);
                    if (isSelected) return '#0FCB8C';
                    if (isInPath && n.data.data.id !== 'node_1_0') return '#F0529C';
                    return '#0f172a';
                });

                // Highlight links in path
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        return pathIds.has(sourceId) && pathIds.has(targetId) ? '#F0529C' : '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        return pathIds.has(sourceId) && pathIds.has(targetId) ? 2.5 : 1.2;
                    });
            })
            .on('mouseout', function () {
                // Reset all nodes
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    return isSelected ? '#0FCB8C' : '#0f172a';
                });

                // Reset all links
                linksG.selectAll('line').attr('stroke', '#334155').attr('stroke-width', 1.2);
            });

        // Render nodes
        const nodes = layout.descendants() as ExtendedHierarchyPointNode[];

        // First render yellow rings for surprising nodes
        nodesG
            .selectAll('circle.surprising-ring')
            .data(nodes.filter((d) => {
                const exp = experiments.find((e) => e.experimentId === d.data.data.id);
                return exp?.isSurprising === true;
            }))
            .join('circle')
            .attr('class', 'surprising-ring')
            .attr('cx', (d) => d.xPos ?? 0)
            .attr('cy', (d) => d.yPos ?? 0)
            .attr('r', 20)
            .attr('fill', 'none')
            .attr('stroke', '#fbbf24')
            .attr('stroke-width', 3)
            .attr('opacity', 0.8);

        // Then render the main node circles
        nodesG
            .selectAll('circle.node')
            .data(nodes)
            .join('circle')
            .attr('class', 'node')
            .attr('cx', (d) => d.xPos ?? 0)
            .attr('cy', (d) => d.yPos ?? 0)
            .attr('r', 18)
            .attr('fill', (d) => surprisalColor(d.data.data))
            .attr('stroke', (d) => {
                const isSelected = d.data.data.id === selectedExperiment?.experimentId;
                return isSelected ? '#0FCB8C' : '#0f172a';
            })
            .attr('stroke-width', (d) => {
                const isSelected = d.data.data.id === selectedExperiment?.experimentId;
                return isSelected ? 3 : 1.5;
            })
            .attr('opacity', (d) => (d.data.data.id === 'node_1_0' ? 0.3 : 1))
            .style('cursor', (d) => (d.data.data.id === 'node_1_0' ? 'default' : 'pointer'))
            .on('mouseover', function (_event, d) {
                // Find path from this node to root
                const pathIds = new Set<string>();
                let current: any = d;
                while (current) {
                    pathIds.add(current.data.data.id);
                    current = current.parent;
                }

                // Highlight nodes in path with brighter stroke
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    const isInPath = pathIds.has(n.data.data.id);
                    if (isSelected) return '#0FCB8C';
                    if (isInPath && n.data.data.id !== 'node_1_0') return '#F0529C';
                    return '#0f172a';
                });

                // Highlight links in path
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        return pathIds.has(sourceId) && pathIds.has(targetId) ? '#F0529C' : '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        return pathIds.has(sourceId) && pathIds.has(targetId) ? 2.5 : 1.2;
                    });
            })
            .on('mouseout', function () {
                // Reset all nodes
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    return isSelected ? '#0FCB8C' : '#0f172a';
                });

                // Reset all links
                linksG.selectAll('line').attr('stroke', '#334155').attr('stroke-width', 1.2);
            })
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
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: 'transparent', border: '3px solid #fbbf24' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        Surprising finding
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
