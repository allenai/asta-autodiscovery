import { Theme } from '@mui/material';
import { css } from '@emotion/react';

/**
 * Returns CSS for custom scrollbar styling that matches the app's dark theme.
 * Supports both webkit browsers (Chrome, Safari, Edge) and Firefox.
 *
 * Usage:
 * ```
 * const StyledComponent = styled('div')`
 *   overflow: auto;
 *   ${({ theme }) => scrollbarStyles(theme)}
 * `;
 * ```
 */
export const scrollbarStyles = (theme: Theme) => css`
    /* Webkit browsers (Chrome, Safari, Edge) */
    &::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }

    &::-webkit-scrollbar-track {
        background: ${theme.color['cream-4'].rgba.toString()};
        border-radius: 6px;
    }

    &::-webkit-scrollbar-thumb {
        background: ${theme.color['cream-20'].rgba.toString()};
        border-radius: 6px;
        border: 2px solid ${theme.color['cream-4'].rgba.toString()};
    }

    /* Firefox */
    scrollbar-width: thin;
    scrollbar-color: ${theme.color['cream-20'].rgba.toString()}
        ${theme.color['cream-4'].rgba.toString()};
`;
