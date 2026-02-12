import { Button, styled } from '@mui/material';
import ArrowForwardIcon from '@mui/icons-material/ArrowForwardOutlined';
import { useState } from 'react';

import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { getPriorAndPosteriorLabel } from '../utils/ExperimentUtils';

export const COLLAPSED_SURPRISALS_COUNT = 2;

export const TopSurprisalsList = () => {
    const { experiments, hasJobCompleted, isLoading } = useRunExperiments();
    if (!hasJobCompleted || experiments.length === 0 || isLoading) {
        return null; // Don't show the component until the job has completed
    }
    return <TopSurprisalsListImpl />;
};

export const TopSurprisalsListImpl = () => {
    const { experiments, selectedExperiment, selectExperiment } = useRunExperiments();

    const surprisals = experiments
        .filter((exp) => exp.isSurprising)
        .sort((a, b) => (a.surprise ?? 0) - (b.surprise ?? 0));

    const [isListExpanded, setIsListExpanded] = useState(
        surprisals.length <= COLLAPSED_SURPRISALS_COUNT
    ); // Expand by default if there are few experiments

    const surprisalsToShow = isListExpanded
        ? surprisals
        : surprisals.slice(0, COLLAPSED_SURPRISALS_COUNT);

    return (
        <Wrapper>
            <Header>
                <Title>Top Surprisals</Title>
                <Actions>{/* <div>Threshold 0 |------| 100</div> */}</Actions>
            </Header>
            <List>
                {surprisalsToShow.map((experiment) => (
                    <Item
                        key={experiment.experimentId}
                        $isSelected={selectedExperiment?.experimentId === experiment.experimentId}
                        onClick={() => selectExperiment(experiment)}>
                        <Description>
                            <Belief>
                                It's{' '}
                                <BeliefLabel>
                                    {getPriorAndPosteriorLabel(experiment.posterior)}
                                </BeliefLabel>{' '}
                                that:{' '}
                            </Belief>
                            <Hypothesis>{experiment.hypothesis}</Hypothesis>
                        </Description>
                        <Link className="view-details">
                            View details <ArrowForwardIcon fontSize="small" />
                        </Link>
                    </Item>
                ))}
            </List>
            <ExpandListButton
                variant="outlined"
                onClick={() => setIsListExpanded(() => !isListExpanded)}>
                {isListExpanded
                    ? 'Collapse surprisals'
                    : `View all ${surprisals.length.toLocaleString()} surprisals`}
            </ExpandListButton>
        </Wrapper>
    );
};

const Wrapper = styled('div')`
    margin-bottom: ${({ theme }) => theme.spacing(4)};
`;

const Header = styled('div')`
    display: flex;
    justify-content: space-between;
`;

const Title = styled('h3')`
    font-size: ${({ theme }) => theme.typography.h6.fontSize};
    color: ${({ theme }) => theme.color['green-40'].hex};
    margin: 0;
`;

const Actions = styled('div')`
    display: flex;
    gap: 8px;
`;

const List = styled('ul')`
    margin: ${({ theme }) => theme.spacing(1, 0, 0, 0)};
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    list-style: none;
`;

const Item = styled('li')<{ $isSelected?: boolean }>`
    padding: 14px 16px 12px 16px;
    background-color: ${({ theme }) => theme.color['cream-100'].hex}0C;
    border: 1px solid ${({ theme }) => theme.color['cream-100'].hex}2F;
    border-radius: 4px;
    position: relative;
    cursor: pointer;
    transition: all 250ms ease-in-out;

    &:hover {
        border-color: ${({ theme }) => theme.color['cream-100'].hex}80;

        .view-details {
            color: ${({ theme }) => theme.color['green-100'].hex};
        }
    }

    &:after {
        content: '';
        display: block;
        position: absolute;
        top: 0;
        left: 0;
        bottom: 0;
        width: 4px;
        background-color: ${({ theme, $isSelected }) =>
            $isSelected ? theme.color['green-100'].hex : 'transparent'};
    }
`;

const Description = styled('div')``;

const Belief = styled('span')``;

const BeliefLabel = styled('strong')`
    color: #ffa31c;
`;

const Hypothesis = styled('span')``;

const Link = styled('div')`
    margin-top: ${({ theme }) => theme.spacing(1)};
    color: ${({ theme }) => theme.color['green-30'].hex};
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 14px;
    transition: color 250ms ease-in-out;
`;

const ExpandListButton = styled(Button)`
    margin-top: ${({ theme }) => theme.spacing(1)};
    color: ${({ theme }) => theme.color['green-30'].hex};
    border-color: ${({ theme }) => theme.color['green-30'].hex}CC;

    &:hover {
        color: ${({ theme }) => theme.color['green-100'].hex};
        border-color: ${({ theme }) => theme.color['green-100'].hex};
    }
`;
