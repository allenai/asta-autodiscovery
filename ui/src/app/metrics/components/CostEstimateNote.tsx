import { Box, Typography, styled } from '@mui/material';

// Keep in sync with the date-aware pricing in api/metrics/costs.py.
const ACCOUNTED_PRICE_CHANGES = [
    'Gemini 3.7 Flash and Gemini 3.8 Flash: $0.75 input / $3.75 output per 1M tokens for runs created before Jan 1, 2027 (UTC); $1.50 / $7.50 from that date.',
];

export default function CostEstimateNote() {
    return (
        <Note role="note" aria-label="About cost estimates">
            <Text>
                <strong>Costs are estimates, not billing data.</strong> They multiply recorded token
                counts by a fixed price table maintained with this app. When a provider changes its
                prices, the table changes too, and older runs may be re-estimated at the new rates,
                so historical costs may not match what was billed. Regional pricing, discounts, and
                other billing adjustments are not modeled.
            </Text>
            <Text sx={{ mt: 0.75 }}>
                Historical price changes that <strong>are</strong> accounted for (each run uses the
                rate in effect when it was created, for all of its tokens):
            </Text>
            <List>
                {ACCOUNTED_PRICE_CHANGES.map((change) => (
                    <li key={change}>
                        <Text>{change}</Text>
                    </li>
                ))}
            </List>
        </Note>
    );
}

const Note = styled(Box)`
    margin-bottom: ${({ theme }) => theme.spacing(2)};
    padding: ${({ theme }) => theme.spacing(1.25, 2)};
    border: 1px solid
        ${({ theme }) => theme.color['cream-10']?.rgba?.toString() || 'rgba(255,255,255,0.1)'};
    border-radius: 8px;
    background: ${({ theme }) =>
        theme.color['cream-4']?.rgba?.toString() || 'rgba(255,255,255,0.04)'};
`;

const Text = styled(Typography)`
    font-size: 0.75rem;
    line-height: 1.5;
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;

const List = styled('ul')`
    margin: ${({ theme }) => theme.spacing(0.5, 0, 0)};
    padding-left: ${({ theme }) => theme.spacing(2.5)};
    color: ${({ theme }) => theme.color['cream-60']?.rgba?.toString() || 'rgba(255,255,255,0.6)'};
`;
