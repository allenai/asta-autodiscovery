/**
 * Whether to show Asta marketing: promotional elements that only make sense on a
 * deployment run by the Asta team, such as the "Try Asta" banner. Asta branding
 * and attribution are not marketing and show regardless.
 *
 * Off unless VITE_ENABLE_ASTA_MARKETING is set to true at build time. Gate any
 * new promotional element on this flag.
 */
export const isAstaMarketingEnabled = ['1', 'true', 'yes'].includes(
    import.meta.env.VITE_ENABLE_ASTA_MARKETING?.trim().toLowerCase() ?? ''
);
