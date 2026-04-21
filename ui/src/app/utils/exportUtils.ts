import { Experiment, ExperimentStatus } from '@/types/Run';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';

export type ExportFormat = 'csv' | 'json';

export function generateFilename(runName: string, format: ExportFormat): string {
    const sanitizedName = runName.replace(/[^a-z0-9]/gi, '-').toLowerCase();
    const timestamp = new Date().toISOString().split('T')[0];
    return `${sanitizedName}_${timestamp}.${format}`;
}

function downloadFile(content: string, filename: string, mimeType: string): void {
    const blob = new Blob([content], { type: `${mimeType};charset=utf-8;` });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

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
        const isInconclusiveOrFailed = exp.status !== ExperimentStatus.SUCCEEDED;

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
    downloadFile(BOM + content, filename, 'text/csv');
}

interface ExperimentExport {
    id: number;
    status: string;
    hypothesis: string | null;
    surprisal: number | null;
    isSurprising: boolean;
    prior: number | null;
    posterior: number | null;
    priorBelief: Experiment['priorBelief'];
    posteriorBelief: Experiment['posteriorBelief'];
    analysis: string | null;
    review: string | null;
    experimentPlan: Experiment['experimentPlan'];
    code: string | null;
    codeOutput: string | null;
    richOutputs: Experiment['richOutputs'];
    runtimeMs: number | null;
    createdAt: string | null;
}

function transformExperimentForExport(exp: Experiment): ExperimentExport {
    return {
        id: exp.idInRun,
        status: exp.status,
        hypothesis: exp.hypothesis,
        surprisal: exp.surprise,
        isSurprising: exp.isSurprising,
        prior: exp.prior,
        posterior: exp.posterior,
        priorBelief: exp.priorBelief,
        posteriorBelief: exp.posteriorBelief,
        analysis: exp.analysis,
        review: exp.review,
        experimentPlan: exp.experimentPlan,
        code: exp.code,
        codeOutput: exp.codeOutput,
        richOutputs: exp.richOutputs,
        runtimeMs: exp.runtimeMs,
        createdAt: exp.createdAt ?? null,
    };
}

export function generateRunJson(experiments: Experiment[]): string {
    const exportData = experiments.map(transformExperimentForExport);
    return JSON.stringify(exportData, null, 2);
}

export function downloadJson(content: string, filename: string): void {
    downloadFile(content, filename, 'application/json');
}
