import { Link, Typography } from '@mui/material';

import { BulletList, DialogBase } from '@/shared/DialogBase';
import { TEST_ID_ATTRIBUTION_DIALOG } from '@/testIds';

type AttributionDialogProps = {
    isOpen: boolean;
    onClose: () => void;
};

export const AttributionDialog = ({ isOpen, onClose }: AttributionDialogProps) => {
    return (
        <DialogBase isOpen={isOpen} onClose={onClose} title="Attribution & Transparency" testId={TEST_ID_ATTRIBUTION_DIALOG}>
            <Typography variant="body1" sx={{ mb: 2 }}>
                <strong>Research corpus</strong>
                <br />
                Asta accesses scientific papers and metadata through Ai2&apos;s{' '}
                <Link
                    href="https://www.semanticscholar.org/paper/The-Semantic-Scholar-Open-Data-Platform-Kinney-Anastasiades/cb92a7f9d9dbcf9145e32fdfa0e70e2a6b828eb1"
                    target="_blank"
                    rel="noopener noreferrer">
                    Semantic Scholar Open Data Platform
                </Link>
                .
            </Typography>

            <Typography variant="body1" sx={{ mb: 2 }}>
                <strong>Model use</strong>
                <br />
                Asta&apos;s open agent framework integrates third party large language models to
                power different research capabilities:
            </Typography>
            <BulletList>
                <li>Find papers: Gemini</li>
                <li>Generate a report: Claude Sonnet</li>
                <li>Analyze data: GPT</li>
                <li>AstaLabs AutoDiscovery: Gemini</li>
            </BulletList>
            <Typography variant="body1" sx={{ mb: 2 }}>
                OpenAI&apos;s{' '}
                <Link
                    href="https://platform.openai.com/docs/guides/moderation"
                    target="_blank"
                    rel="noopener noreferrer">
                    Moderation API
                </Link>{' '}
                is used to screen initial queries for potentially harmful or unsafe content. Model
                version selections are periodically updated.
            </Typography>

            <Typography variant="body1" sx={{ mb: 1 }}>
                <strong>Model attributions</strong>
            </Typography>
            <BulletList>
                <li>
                    Claude models are developed by Anthropic, PBC, and provided under the{' '}
                    <Link
                        href="https://www.anthropic.com/legal/commercial-terms"
                        target="_blank"
                        rel="noopener noreferrer">
                        Anthropic Commercial Terms of Service
                    </Link>
                    .
                </li>
                <li>
                    Gemini models are developed by Google LLC, and provided under the{' '}
                    <Link
                        href="https://cloud.google.com/terms/service-terms"
                        target="_blank"
                        rel="noopener noreferrer">
                        Google Cloud Platform Service Terms
                    </Link>
                    .
                </li>
                <li>
                    GPT models are developed by OpenAI, LLC, and provided under the{' '}
                    <Link
                        href="https://openai.com/policies/services-agreement/"
                        target="_blank"
                        rel="noopener noreferrer">
                        OpenAI Services Agreement
                    </Link>
                    .
                </li>
            </BulletList>
        </DialogBase>
    );
};
