export const getPriorAndPosteriorLabel = (score: number | null): string => {
    if (score === null) {
        return 'Uncertain';
    }

    if (score > 0 && score < 0.25) {
        return 'Likely False';
    }

    if (score >= 0.25 && score < 0.5) {
        return 'Maybe False';
    }

    if (score === 0.5) {
        return 'Uncertain';
    }

    if (score > 0.5 && score < 0.75) {
        return 'Maybe True';
    }

    if (score >= 0.75 && score <= 1) {
        return 'Likely True';
    }

    return 'Uncertain';
};

export const getSurprisalDirection = (surprise: number | null): string => {
    if (surprise === null || surprise === 0) {
        return 'Neutral';
    }
    return surprise > 0 ? 'Positive' : 'Negative';
};

/**
 * Escapes markdown special characters to prevent unintended formatting.
 * Primarily used to escape tildes (~) which are interpreted as strikethrough syntax.
 */
export const escapeMarkdown = (text: string): string => {
    return text.replace(/~/g, '\\~');
};
