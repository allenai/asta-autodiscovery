import { styled } from '@mui/material';
import IconButton from '@mui/material/IconButton';
import { scrollbarStyles } from '@/utils/scrollbar';

export const PanelLayout = styled('div')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    height: 100%;
    padding: ${({ theme }) => theme.spacing(0, 2, 2)};
    justify-content: space-between;
    position: relative;

    @container run-view (width < 1000px) {
        display: grid;
    }

    @container run-view (width < 600px) {
        padding: ${({ theme }) => theme.spacing(0, 1, 1)};
    }

    @container run-view (width < 425px) {
        padding: 0;
    }
`;

export const Background = styled('div')`
    position: absolute;
    inset: 0;
    z-index: 1;

    @container run-view (width < 1000px) {
        display: none;
    }
`;

export const RunPanel = styled('div')<{ $isExpanded: boolean }>`
    flex: 0 1 auto;
    min-width: 0;
    width: ${({ $isExpanded }) => ($isExpanded ? '100%' : '500px')};
    background-color: #163638f3;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(2)};
    overflow: auto;
    z-index: 2;
    ${({ theme }) => scrollbarStyles(theme)}

    @container run-view (width < 1000px) {
        flex: initial;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container run-view (width < 600px) {
        width: 100%;
    }
`;

export const ExperimentPanel = styled('div')<{ $isExpanded: boolean }>`
    flex: 0 1 auto;
    max-width: ${({ $isExpanded }) => ($isExpanded ? 'initial' : '500px')};
    background-color: #163638f3;
    border-radius: 12px;
    position: ${({ $isExpanded }) => ($isExpanded ? 'absolute' : 'relative')};
    overflow-y: auto;
    z-index: 2;
    top: 0;
    bottom: 0;
    ${({ theme }) => scrollbarStyles(theme)}

    @container run-view (width < 1000px) {
        flex: 1 1 auto;
        max-width: initial;
        position: relative;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container run-view (width < 600px) {
        width: 100%;
    }
`;

export const ExperimentActions = styled('div')`
    display: flex;
    gap: ${({ theme }) => theme.spacing(1)};
    position: absolute;
    top: ${({ theme }) => theme.spacing(2)};
    right: ${({ theme }) => theme.spacing(2)};
`;

export const ExperimentActionButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-50'].rgba.toString()};
`;

export const LargeScreenAction = styled('div')`
    @container run-view (width < 1000px) {
        display: none;
    }
`;
