import { Button, styled } from '@mui/material';
import Link from 'next/link';

import { mkFeedbackBtnTrackAttrs } from '@/analytics/run';

export const FeedbackButton = () => {
    return (
        <Link
            href="https://docs.google.com/forms/d/e/1FAIpQLScmKqOj9EuOrfNlO0ySm_5ITPH80anDgC3FDBuSEeesgztv1Q/viewform"
            passHref
            target="_blank"
            rel="noopener noreferrer"
            {...mkFeedbackBtnTrackAttrs()}>
            <StyledButton variant="outlined">Feedback</StyledButton>
        </Link>
    );
};

const StyledButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;

        & .MuiButton-endIcon {
            margin: 0 0 0 ${({ theme }) => theme.spacing(0.75)};
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};

        &:hover {
            border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        }
    }
`;
