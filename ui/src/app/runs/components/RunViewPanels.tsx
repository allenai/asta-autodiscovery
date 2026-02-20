import { styled } from '@mui/material';
import IconButton from '@mui/material/IconButton';
import debounce from 'lodash.debounce';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { scrollbarStyles } from '@/utils/scrollbar';

const MS_PER_FRAME = Math.floor(1000 / 60);
const SAVE_DEBOUNCE_MS = 500;

export const PanelGroup = ({ children }: { children: React.ReactNode }) => {
    return (
        <PanelsContainer>
            <PanelLayout>{children}</PanelLayout>
        </PanelsContainer>
    );
};

export const PanelDragHandle = ({
    side,
    onWidthPxChange,
    dragWidthPx,
    minWidthPx,
}: {
    side: 'left' | 'right';
    onWidthPxChange: (widthPx: number) => void;
    dragWidthPx?: number;
    minWidthPx?: number;
}) => {
    const startMouseXRef = useRef<number | null>(null);
    const startWidthPxRef = useRef<number | null>(null);

    const calcWidthPxRef = useRef((e: MouseEvent) => {
        const deltaX = e.clientX - startMouseXRef.current!;
        const newWidthPx =
            side === 'left' ? startWidthPxRef.current! - deltaX : startWidthPxRef.current! + deltaX;
        const result = Math.max(minWidthPx ?? 0, newWidthPx);
        return result;
    });

    // Save latest onWidthPxChange in ref
    const onWidthPxChangeRef = useRef(onWidthPxChange);
    useEffect(() => {
        onWidthPxChangeRef.current = onWidthPxChange;
    }, [onWidthPxChange]);

    const reportMoveDebounced = useMemo(
        () =>
            debounce(
                (widthPx: number) => {
                    onWidthPxChangeRef.current(widthPx);
                },
                MS_PER_FRAME,
                { leading: true, trailing: true, maxWait: MS_PER_FRAME }
            ),
        [onWidthPxChangeRef]
    );

    const onMouseMoveRef = useRef((e: MouseEvent) => {
        e.preventDefault();
        const newWidthPx = calcWidthPxRef.current(e);
        reportMoveDebounced(newWidthPx);
    });

    const onMouseUpRef = useRef((e: MouseEvent) => {
        e.preventDefault();
        document.documentElement.removeEventListener('mousemove', onMouseMoveRef.current);
        document.documentElement.removeEventListener('mouseup', onMouseUpRef.current);
        const newWidthPx = calcWidthPxRef.current(e);
        reportMoveDebounced(newWidthPx);
    });

    const onMouseDown = useCallback(
        (e: React.MouseEvent) => {
            e.preventDefault();
            startMouseXRef.current = e.clientX;
            startWidthPxRef.current = dragWidthPx ?? 0;

            document.documentElement.addEventListener('mousemove', onMouseMoveRef.current);
            document.documentElement.addEventListener('mouseup', onMouseUpRef.current);
        },
        [dragWidthPx]
    );

    useEffect(() => {
        return () => {
            document.documentElement.removeEventListener('mousemove', onMouseMoveRef.current);
            document.documentElement.removeEventListener('mouseup', onMouseUpRef.current);
        };
    }, []);

    return <DragHandle $side={side} onMouseDown={onMouseDown} />;
};

const getWidthFromStorage = (key: string): number | null => {
    try {
        const stored = localStorage.getItem(key);
        const widthPx = stored ? parseInt(stored, 10) : null;
        if (widthPx !== null && !isNaN(widthPx)) {
            return widthPx;
        }
    } catch {
        // may throw in privacy mode
    }
    return null;
};

export const usePanelWidthPx = (
    key: string,
    initialWidthPx: number | null
): [number | null, React.Dispatch<React.SetStateAction<number | null>>] => {
    const [widthPx, setWidthPx] = useState<number | null>(
        () => getWidthFromStorage(key) ?? initialWidthPx
    );

    // Update if key changes
    useEffect(() => {
        const widthPx = getWidthFromStorage(key);
        if (widthPx !== null) {
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
        }, SAVE_DEBOUNCE_MS);
        return () => {
            clearTimeout(timeoutId);
            saveWidthPxToStorage.current(key, widthPx);
        };
    }, [key, widthPx]);

    return useMemo(() => [widthPx, setWidthPx], [widthPx, setWidthPx]);
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

export const RunPanel = styled('div')`
    flex: 0 1 auto;
    min-width: 0;
    width: var(--run-panel-width, 700px);
    background-color: #163638f3;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 0;
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
        border-radius: 0;
        background-color: transparent;
    }
`;

export const ExperimentPanel = styled('div')<{ $isExpanded: boolean }>`
    flex: 0 1 auto;
    max-width: ${({ $isExpanded }) =>
        $isExpanded ? 'initial' : 'var(--experiment-panel-width, 500px)'};
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
        border-radius: 0;
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
    ${({ $side }) => ($side === 'left' ? 'left: 0px;' : 'right: 0px;')}
    width: 10px;
    cursor: ew-resize;
    z-index: 3;
    display: grid;
    place-items: center;
    opacity: 0.5;
    transition:
        opacity 0.2s ease-in-out,
        background-color 0.2s ease-in-out;

    &:after {
        content: '';
        position: fixed;
        width: 4px;
        height: 40px;
        border-radius: 8px;
        background-color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
    }

    &:hover,
    &:active {
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
        opacity: 1;
        transition:
            opacity 0s,
            background-color 0s;
    }
`;
