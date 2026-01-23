import { Box, Typography, styled } from '@mui/material';

export const IntroBox = () => {
    return (
        <Wrapper>
            <Title>AutoDiscovery</Title>
            <Description>
                Uncover surprising insights hidden in your data. AutoDiscovery uses Bayesian
                surprise (a measure of how much a finding shifts our beliefs) to autonomously
                explore your datasets and identify discoveries that genuinely change what we know,
                not just what's obvious or diverse.
            </Description>
        </Wrapper>
    );
};

const Wrapper = styled(Box)(({ theme }) => ({
    background: `radial-gradient(155.14% 72.67% at 0% 0%, rgba(255, 163, 28, 0.10) 0%, rgba(255, 163, 28, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%)`,
    border: '1px solid rgba(250, 242, 233, 0.30)',
    borderColor:
        'radial-gradient(155.14% 72.67% at 0% 0%, rgba(255, 163, 28, 0.10) 0%, rgba(255, 163, 28, 0.00) 100%), linear-gradient(93deg, rgba(15, 203, 140, 0.10) -26.7%, rgba(15, 203, 140, 0.00) 114.84%);',
    borderRadius: theme.spacing(1.5),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    padding: theme.spacing(4.5),
}));

const Title = styled(Typography)(({ theme }) => ({
    color: theme.color['green-100'].hex,
    fontSize: '2.5rem',
    lineHeight: 1,
    fontWeight: 'bold',
}));

const Description = styled(Typography)(({ theme }) => ({
    maxWidth: '600px',
    marginTop: theme.spacing(2),
    fontSize: '1.125rem',
    lineHeight: 1.5,
    fontWeight: 400,
}));
