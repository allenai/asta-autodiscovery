/**
 * ExperimentGraph Component
 *
 * This file renders a radial tree visualization representing a DAG (Directed Acyclic Graph)
 * of experiment nodes. Each node represents a single experiment in a scientific discovery run.
 *
 * NODE STRUCTURE:
 * - Each node is an experiment with a surprisal value (belief_change), measuring how much
 *   the experiment changed the agent's beliefs about a hypothesis
 * - Nodes are positioned radially from the root, with parent-child relationships preserved
 * - A fake root node (node_1_0) may be created if multiple experiments lack a parent
 *
 * COLOR CODING:
 * - Node colors are determined by surprisal intensity and whether the node is marked surprising
 * - Color interpolation between base color (#384849 dark gray) and target color:
 *   - Orange (#FFA31C): For nodes marked as surprising (isSurprising = true)
 *   - Cream (#FAF2E9): For regular nodes with high surprisal
 * - Intensity calculation: abs(surprisal) / 0.7, clamped to [0, 1]
 * - Low/no surprisal nodes remain dark gray (#384849)
 * - D3 interpolateRgb handles the gradient between base and target colors
 *
 * INTERACTIONS:
 * - Click nodes to select and view experiment details
 * - Hover over nodes/edges to highlight the ancestral path (magenta) and descendants (pink)
 * - Selected experiments show a green highlight along their path to root
 * - Zoom controls: +/- buttons for zoom, center button to reset view
 * - Pan/zoom: Drag to pan, scroll to zoom
 *
 * DATA FLOW:
 * - Experiments come from RunExperimentsContext
 * - buildHierarchy() converts flat experiment array into D3 tree hierarchy
 * - assignAngularRanges() positions nodes to prevent edge crossings
 * - surprisalColor() calculates node colors based on surprisal intensity and isSurprising flag
 *
 * All information and logic relevant to rendering the experiment tree is contained in this file.
 * The component uses D3.js for tree layout, radial positioning, and zoom/pan interactions.
 */

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
    isSurprising: boolean;
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
    isSurprising: exp.isSurprising,
});

// Calculate node color based on surprisal
const surprisalColor = (node: D3TreeNode): string => {
    const surprisal = node.belief_change;

    if (typeof surprisal !== 'number' || surprisal === null) {
        return '#384849'; // default dark for nodes without surprisal data
    }

    // Calculate intensity where 0.7 = full color, using absolute value
    const intensity = Math.max(0, Math.min(1, Math.abs(surprisal) / 0.7));

    // Base color (low surprisal)
    const baseColor = '#384849';

    // Target color depends on whether node is surprising
    const targetColor = node.isSurprising ? '#FFA31C' : '#FAF2E9';

    // Interpolate between base and target color
    const interpolator = d3.interpolateRgb(baseColor, targetColor);
    return interpolator(intensity);
};

// Build tree hierarchy from flat experiment array
const buildHierarchy = (experiments: Experiment[]): d3.HierarchyNode<TreeNode> | null => {
    if (experiments.length === 0) return null;

    const byId = new Map(experiments.map((e) => [e.experimentId, e]));

    // Check if we need to create a fake root node (node_1_0)
    const needsFakeRoot = experiments.some(
        (e) => e.parentId === 'node_1_0' && !byId.has('node_1_0')
    );

    let root: Experiment | null = null;
    let allExperiments = experiments;

    if (needsFakeRoot) {
        // Create a fake root node
        const fakeRoot: Experiment = {
            experimentId: 'node_1_0',
            parentId: null,
            childIds: experiments
                .filter((e) => e.parentId === 'node_1_0')
                .map((e) => e.experimentId),
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

        // Deduplicate experiments by experimentId to prevent duplicate nodes
        const uniqueExperiments = Array.from(
            new Map(experiments.map((exp) => [exp.experimentId, exp])).values()
        );

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        // Build hierarchy
        const hierarchy = buildHierarchy(uniqueExperiments);
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

        // Get all nodes for later use
        const nodes = layout.descendants() as ExtendedHierarchyPointNode[];

        // Calculate path from selected experiment to root
        const selectedPathIds = new Set<string>();
        if (selectedExperiment) {
            const selectedNode = nodes.find(
                (n) => n.data.data.id === selectedExperiment.experimentId
            );
            if (selectedNode) {
                let current: any = selectedNode;
                while (current) {
                    selectedPathIds.add(current.data.data.id);
                    current = current.parent;
                }
            }
        }

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
            .attr('stroke', (d: any) => {
                const sourceId = d.source.data.data.id;
                const targetId = d.target.data.data.id;
                const inSelectedPath =
                    selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                return inSelectedPath ? '#0FCB8C' : '#334155';
            })
            .attr('stroke-width', (d: any) => {
                const sourceId = d.source.data.data.id;
                const targetId = d.target.data.data.id;
                const inSelectedPath =
                    selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                return inSelectedPath ? 2.5 : 1.2;
            })
            .attr('fill', 'none')
            .style('cursor', 'pointer')
            .on('mouseover', function (_event, d: any) {
                // Highlight path from target node to root (ancestors)
                const pathIds = new Set<string>();
                let current = d.target;
                while (current) {
                    pathIds.add(current.data.data.id);
                    current = current.parent;
                }

                // Collect all descendant IDs from target node
                const descendantIds = new Set<string>();
                const collectDescendants = (node: any) => {
                    if (node.children) {
                        node.children.forEach((child: any) => {
                            descendantIds.add(child.data.data.id);
                            collectDescendants(child);
                        });
                    }
                };
                collectDescendants(d.target);

                // Highlight nodes in path and descendants
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    const isInPath = pathIds.has(n.data.data.id);
                    const isDescendant = descendantIds.has(n.data.data.id);
                    if (isSelected) return '#0FCB8C';
                    if (isInPath && n.data.data.id !== 'node_1_0') return '#F0529C';
                    if (isDescendant && n.data.data.id !== 'node_1_0') return '#f472b6';
                    return '#0f172a';
                });

                // Highlight links in path and descendants
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        const bothInPath = pathIds.has(sourceId) && pathIds.has(targetId);
                        const bothInDescendants =
                            descendantIds.has(sourceId) && descendantIds.has(targetId);
                        const connectsToDescendants =
                            pathIds.has(sourceId) && descendantIds.has(targetId);

                        if (inSelectedPath) return '#0FCB8C';
                        if (bothInPath) return '#F0529C';
                        if (bothInDescendants || connectsToDescendants) return '#f472b6';
                        return '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        const bothInPath = pathIds.has(sourceId) && pathIds.has(targetId);

                        if (inSelectedPath) return 2.5;
                        if (bothInPath) return 2.5;
                        return 1.2;
                    });
            })
            .on('mouseout', function () {
                // Reset all nodes
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    return isSelected ? '#0FCB8C' : '#0f172a';
                });

                // Reset all links (preserving selected path highlighting)
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        return inSelectedPath ? '#0FCB8C' : '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        return inSelectedPath ? 2.5 : 1.2;
                    });
            });

        // Render nodes
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
                // Find path from this node to root (ancestors)
                const pathIds = new Set<string>();
                let current: any = d;
                while (current) {
                    pathIds.add(current.data.data.id);
                    current = current.parent;
                }

                // Collect all descendant IDs from this node
                const descendantIds = new Set<string>();
                const collectDescendants = (node: any) => {
                    if (node.children) {
                        node.children.forEach((child: any) => {
                            descendantIds.add(child.data.data.id);
                            collectDescendants(child);
                        });
                    }
                };
                collectDescendants(d);

                // Highlight nodes in path and descendants
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    const isInPath = pathIds.has(n.data.data.id);
                    const isDescendant = descendantIds.has(n.data.data.id);
                    if (isSelected) return '#0FCB8C';
                    if (isInPath && n.data.data.id !== 'node_1_0') return '#F0529C';
                    if (isDescendant && n.data.data.id !== 'node_1_0') return '#f472b6';
                    return '#0f172a';
                });

                // Highlight links in path and descendants
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        const bothInPath = pathIds.has(sourceId) && pathIds.has(targetId);
                        const bothInDescendants =
                            descendantIds.has(sourceId) && descendantIds.has(targetId);
                        const connectsToDescendants =
                            pathIds.has(sourceId) && descendantIds.has(targetId);

                        if (inSelectedPath) return '#0FCB8C';
                        if (bothInPath) return '#F0529C';
                        if (bothInDescendants || connectsToDescendants) return '#f472b6';
                        return '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        const bothInPath = pathIds.has(sourceId) && pathIds.has(targetId);
                        const bothInDescendants =
                            descendantIds.has(sourceId) && descendantIds.has(targetId);
                        const connectsToDescendants =
                            pathIds.has(sourceId) && descendantIds.has(targetId);

                        if (inSelectedPath) return 2.5;
                        if (bothInPath) return 2.5;
                        if (bothInDescendants || connectsToDescendants) return 1.2;
                        return 1.2;
                    });
            })
            .on('mouseout', function () {
                // Reset all nodes
                nodesG.selectAll('circle.node').attr('stroke', (n: any) => {
                    const isSelected = n.data.data.id === selectedExperiment?.experimentId;
                    return isSelected ? '#0FCB8C' : '#0f172a';
                });

                // Reset all links (preserving selected path highlighting)
                linksG
                    .selectAll('line')
                    .attr('stroke', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        return inSelectedPath ? '#0FCB8C' : '#334155';
                    })
                    .attr('stroke-width', (l: any) => {
                        const sourceId = l.source.data.data.id;
                        const targetId = l.target.data.data.id;
                        const inSelectedPath =
                            selectedPathIds.has(sourceId) && selectedPathIds.has(targetId);
                        return inSelectedPath ? 2.5 : 1.2;
                    });
            })
            .on('click', (_event, d) => {
                // Don't allow clicking the fake root node
                if (d.data.data.id === 'node_1_0') return;

                const experiment = uniqueExperiments.find((e) => e.experimentId === d.data.data.id);
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
                    Surprisal Intensity
                </Typography>
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: '#FFA31C' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        High surprisal
                    </Typography>
                </LegendItem>
                <LegendItem>
                    <LegendCircle style={{ backgroundColor: '#5F6A69' }} />
                    <Typography variant="caption" sx={{ color: '#faf2e9' }}>
                        Low/no surprisal
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
