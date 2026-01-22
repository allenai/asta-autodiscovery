import { Box, Typography, styled } from '@mui/material';

export const ExamplesBox = () => {
    return (
        <div>
            <Typography variant="h5" sx={{ mb: 2 }}>
                Example Sessions
            </Typography>
            <Wrapper>[Examples go here]</Wrapper>
        </div>
    );
};

const Wrapper = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
}));
