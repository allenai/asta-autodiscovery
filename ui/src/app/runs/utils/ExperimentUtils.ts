export const SurprisalLabels = {
    MUCH_MORE_FALSE: 'Much more false',
    MORE_FALSE: 'More false',
    NEUTRAL: 'Neutral',
    MORE_TRUE: 'More true',
    MUCH_MORE_TRUE: 'Much more true',
} as const;

export type SurprisalScale = keyof typeof SurprisalLabels;

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

    if (score >= 0.5 && score < 0.75) {
        return 'Maybe True';
    }

    if (score >= 0.75 && score <= 1) {
        return 'Likely True';
    }

    return 'Uncertain';
};

// TODO: Update the scale thresholds here
export const getSurprisalScale = (score: number | null): SurprisalScale => {
    if (score === null) {
        return 'NEUTRAL';
    }

    if (score >= 0 && score < 0.25) {
        return 'MUCH_MORE_FALSE';
    }

    if (score >= 0.25 && score < 0.5) {
        return 'MUCH_MORE_TRUE';
    }

    if (score >= 0.5 && score < 0.75) {
        return 'MORE_FALSE';
    }

    if (score >= 0.75 && score <= 1) {
        return 'MORE_TRUE';
    }

    return 'NEUTRAL';
};

export const getSurprisalColor = (scale: SurprisalScale): string => {
    switch (scale) {
        case 'MUCH_MORE_FALSE':
            return '#FD4645'; // red
        case 'MORE_FALSE':
            return '#FB9C97'; // orange
        case 'NEUTRAL':
            return '#FAF2E9'; // gray
        case 'MORE_TRUE':
            return '#A6C68E'; // green
        case 'MUCH_MORE_TRUE':
            return '#549C35'; // bright green
        default:
            return '#FAF2E9';
    }
};
