import { styled } from '@mui/material';

import { useRunExperiments } from '@/contexts/RunExperimentsContext';

export const ExperimentGraph = () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { experiments, selectedExperiment, selectExperiment } = useRunExperiments();

    return <GraphContainer>{/* GRAPH GOES HERE */}</GraphContainer>;
};

const GraphContainer = styled('div')`
    display: flex;
    height: 100%;
    width: 100%;
`;
