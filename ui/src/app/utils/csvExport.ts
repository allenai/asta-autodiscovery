import { Experiment } from '@/types/Run';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';

const CSV_HEADERS = [
    'ID',
    'Hypothesis',
    'Surprisal',
    'Belief Before',
    'Belief After',
    'Direction',
    'Analysis',
    'Review',
    'Objective',
    'Steps',
    'Deliverables',
];

function stripMarkdown(text: string | null): string {
    if (!text) return '';

    return text
        .replace(/^#+\s+/gm, '')
        .replace(/(\*\*|__)(.*?)\1/g, '$2')
        .replace(/(\*|_)(.*?)\1/g, '$2')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/`([^`]+)`/g, '$1')
        .trim();
}

function escapeCsv(value: string | number | null): string {
    if (value === null || value === undefined) return '';
    const str = String(value);

    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
}

export function generateRunCsv(experiments: Experiment[]): string {
    const rows = experiments.map((exp) => {
        const isInconclusiveOrFailed = exp.status !== 'SUCCEEDED';

        const objective = stripMarkdown(exp.experimentPlan?.objective || '');
        const steps = exp.experimentPlan?.steps
            ? Array.isArray(exp.experimentPlan.steps)
                ? exp.experimentPlan.steps.join('; ')
                : String(exp.experimentPlan.steps)
            : '';
        const deliverables = exp.experimentPlan?.deliverables
            ? Array.isArray(exp.experimentPlan.deliverables)
                ? exp.experimentPlan.deliverables.join('; ')
                : String(exp.experimentPlan.deliverables)
            : '';

        const surprisal = isInconclusiveOrFailed
            ? ''
            : exp.surprise
              ? Math.abs(exp.surprise).toFixed(3)
              : '';

        return [
            exp.idInRun,
            exp.hypothesis ?? '',
            surprisal,
            isInconclusiveOrFailed ? '' : getPriorAndPosteriorLabel(exp.prior),
            isInconclusiveOrFailed ? '' : getPriorAndPosteriorLabel(exp.posterior),
            isInconclusiveOrFailed ? '' : getSurprisalDirection(exp.surprise),
            stripMarkdown(exp.analysis),
            stripMarkdown(exp.review),
            objective,
            stripMarkdown(steps),
            stripMarkdown(deliverables),
        ].map(escapeCsv);
    });

    const csvLines = [CSV_HEADERS.map(escapeCsv).join(','), ...rows.map((row) => row.join(','))];

    return csvLines.join('\n');
}

export function downloadCsv(content: string, filename: string): void {
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + content], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}
