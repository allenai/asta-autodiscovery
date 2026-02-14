import { styled } from '@mui/material';
import IconButton from '@mui/material/IconButton';
import debounce from 'lodash.debounce';

import { scrollbarStyles } from '@/utils/scrollbar';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { width } from '@mui/system';

interface UsePanelWidthPxResult {
    widthPx: number | null;
    setWidthPx: (widthPx: number | null | ((prevWidthPx: number | null) => number | null)) => void;
}

export const PanelGroup = ({ children }: { children: React.ReactNode }) => {
    return (
        <PanelsContainer>
            <PanelLayout>{children}</PanelLayout>
        </PanelsContainer>
    );
};

export const PanelDragHandle = ({
    side,
    onDragMove,
    onDragEnd,
    dragWidthPx,
    minWidthPx,
}: {
    side: 'left' | 'right';
    onDragMove: (deltaX: number) => void;
    onDragEnd: (widthPx: number) => void;
    dragWidthPx?: number;
    minWidthPx?: number;
}) => {
    const widthPxRef = useRef(dragWidthPx ?? 0);
    useEffect(() => {
        widthPxRef.current = dragWidthPx ?? 0;
    }, [dragWidthPx]);

    const onDragMoveRef = useRef(onDragMove);
    useEffect(() => {
        onDragMoveRef.current = onDragMove;
    }, [onDragMove]);

    const reportMoveDebouncedRef = useRef(
        debounce(
            (widthPx: number) => {
                onDragMoveRef.current(widthPx);
            },
            16,
            { leading: true, trailing: true, maxWait: 16 }
        )
    );

    const onMouseMoveRef = useRef((e: MouseEvent) => {
        e.preventDefault();
        const deltaX = side === 'left' ? -e.movementX : e.movementX;
        const newWidthPx = widthPxRef.current + deltaX;
        widthPxRef.current =
            minWidthPx !== undefined ? Math.max(minWidthPx, newWidthPx) : newWidthPx;
        reportMoveDebouncedRef.current(widthPxRef.current);
    });

    const onMouseUpRef = useRef((e: MouseEvent) => {
        e.preventDefault();
        document.documentElement.removeEventListener('mousemove', onMouseMoveRef.current);
        document.documentElement.removeEventListener('mouseup', onMouseUpRef.current);
        const deltaX = side === 'left' ? -e.movementX : e.movementX;
        const newWidthPx = widthPxRef.current + deltaX;
        widthPxRef.current =
            minWidthPx !== undefined ? Math.max(minWidthPx, newWidthPx) : newWidthPx;
        onDragEnd(widthPxRef.current);
    });

    const onMouseDown = useCallback((e: React.MouseEvent) => {
        e.preventDefault();

        document.documentElement.addEventListener('mousemove', onMouseMoveRef.current);
        document.documentElement.addEventListener('mouseup', onMouseUpRef.current);
    }, []);

    useEffect(() => {
        return () => {
            document.documentElement.removeEventListener('mousemove', onMouseMoveRef.current);
            document.documentElement.removeEventListener('mouseup', onMouseUpRef.current);
        };
    }, []);

    return <DragHandle $side={side} onMouseDown={onMouseDown} />;
};

const getWidthFromStorage = (key: string): number | null => {
    const stored = localStorage.getItem(key);
    const widthPx = stored ? parseInt(stored, 10) : null;
    if (widthPx && !isNaN(widthPx)) {
        return widthPx;
    }
    return null;
};

export const usePanelWidthPx = (
    key: string,
    initialWidthPx: number | null
): UsePanelWidthPxResult => {
    const [widthPx, setWidthPx] = useState<number | null>(
        getWidthFromStorage(key) ?? initialWidthPx
    );

    // Update if key changes
    useEffect(() => {
        const widthPx = getWidthFromStorage(key);
        if (widthPx) {
            setWidthPx(widthPx);
        }
    }, [key]);

    // Ref to save widthPx to localstorage
    const saveWidthPxToStorage = useRef((key: string, widthPx: number | null) => {
        if (widthPx === null) {
            localStorage.removeItem(key);
        } else {
            localStorage.setItem(key, widthPx.toString());
        }
    });

    // Debounce saving widthPx, or save on unmount
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            saveWidthPxToStorage.current(key, widthPx);
        }, 0);
        return () => {
            clearTimeout(timeoutId);
            saveWidthPxToStorage.current(key, widthPx);
        };
    }, [key, widthPx]);

    const result = useMemo(() => ({ widthPx, setWidthPx }), [widthPx, setWidthPx]);
    return result;
};

export const PanelsContainer = styled('div')`
    container: panel-container / inline-size;
    height: 100%;
`;

export const PanelLayout = styled('div')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    height: 100%;
    padding: ${({ theme }) => theme.spacing(0, 2, 2)};
    justify-content: space-between;
    position: relative;

    @container panel-container (width < 1000px) {
        display: grid;
    }

    @container panel-container (width < 600px) {
        padding: ${({ theme }) => theme.spacing(0, 1, 1)};
    }

    @container panel-container (width < 425px) {
        padding: 0;
    }
`;

export const Background = styled('div')`
    position: absolute;
    inset: 0;
    z-index: 1;

    @container panel-container (width < 1000px) {
        display: none;
    }
`;

export const RunPanel = styled('div')<{ $isExpanded: boolean; $dragWidthPx: number | null }>`
    flex: 0 1 auto;
    min-width: 0;
    width: ${({ $isExpanded, $dragWidthPx }) =>
        $isExpanded ? '100%' : $dragWidthPx ? `${$dragWidthPx}px` : '700px'};
    background-color: #163638f3;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(2)};
    overflow: auto;
    position: relative;
    z-index: 2;
    ${({ theme }) => scrollbarStyles(theme)}

    @container panel-container (width < 1000px) {
        flex: initial;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container panel-container (width < 600px) {
        width: 100%;
    }
`;

export const ExperimentPanel = styled('div')<{ $isExpanded: boolean; $dragWidthPx: number | null }>`
    flex: 0 1 auto;
    max-width: ${({ $isExpanded, $dragWidthPx }) =>
        $isExpanded ? 'initial' : $dragWidthPx ? `${$dragWidthPx}px` : '500px'};
    background-color: #163638f3;
    border-radius: 12px;
    position: ${({ $isExpanded }) => ($isExpanded ? 'absolute' : 'relative')};
    overflow-y: auto;
    z-index: 2;
    top: 0;
    bottom: 0;
    ${({ theme }) => scrollbarStyles(theme)}

    @container panel-container (width < 1000px) {
        flex: 1 1 auto;
        max-width: initial;
        position: relative;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container panel-container (width < 600px) {
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
    @container panel-container (width < 1000px) {
        display: none;
    }
`;

const DragHandle = styled('div')<{ $side: 'left' | 'right' }>`
    position: absolute;
    top: 0;
    bottom: 0;
    ${({ $side }) => ($side === 'left' ? 'left: 0;' : 'right: 0;')}
    width: 8px;
    cursor: ew-resize;
    z-index: 3;

    &:after {
        content: '';
        position: fixed;
        top: 50%;
        width: 5px;
        height: 40px;
        border-radius: 8px;
        background-color: ${({ theme }) => theme.color['cream-20'].rgba.toString()};
        transform: translateY(-50%);
    }

    &:hover {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }
`;
