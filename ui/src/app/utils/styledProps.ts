/**
 * Helper to filter out transient props (props starting with $) from being forwarded to DOM elements.
 * Use this when wrapping MUI components with styled() to prevent transient props from appearing in the DOM.
 *
 * @example
 * const MyComponent = styled(Box, {
 *   shouldForwardProp: filterTransientProps,
 * })<{ $myProp: string }>`
 *   color: ${({ $myProp }) => $myProp};
 * `;
 */
export const filterTransientProps = (prop: PropertyKey): boolean => {
    return typeof prop === 'string' && !prop.startsWith('$');
};
