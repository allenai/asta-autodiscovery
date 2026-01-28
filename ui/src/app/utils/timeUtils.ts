/**
 * Get a human-readable relative time string from a date
 * @param date - The date to compare against now
 * @returns A string like "just now", "2 minutes ago", "1 hour ago"
 */
export const getRelativeTime = (date: Date | null): string => {
    if (!date) return '';

    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

    if (seconds < 10) return 'just now';
    if (seconds < 60) return `${seconds} seconds ago`;

    const minutes = Math.floor(seconds / 60);
    if (minutes === 1) return '1 minute ago';
    if (minutes < 60) return `${minutes} minutes ago`;

    const hours = Math.floor(minutes / 60);
    if (hours === 1) return '1 hour ago';
    return `${hours} hours ago`;
};
