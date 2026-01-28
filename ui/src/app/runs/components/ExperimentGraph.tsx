import { styled } from '@mui/material';
import { useCallback, useState } from 'react';

export const ExperimentGraph = () => {
    const [counter, setCounter] = useState(0);

    const onClickGraph = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
        event.preventDefault();
        setCounter((prev) => prev + 1);
    }, []);

    return (
        <GraphContainer>
            <MockGraph key={counter} onClick={onClickGraph} />
        </GraphContainer>
    );
};

const GraphContainer = styled('div')`
    display: flex;
    height: 100%;
    width: 100%;
`;

const MockGraph = styled('div')`
    animation: flash 0.25s ease-in-out;
    flex: 1 1 auto;
    background-color: #ccc;

    @keyframes flash {
        0% {
            filter: brightness(1);
        }
        10% {
            filter: brightness(2);
        }
        100% {
            filter: brightness(1);
        }
    }
`;
