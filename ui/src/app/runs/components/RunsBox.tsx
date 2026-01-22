import { Box, Button, Typography, styled } from '@mui/material';
import AddBoxIcon from '@mui/icons-material/AddBox';

export const RunsBox = () => {
    return (
        <>
            <Header>
                <Headline variant="h5">Your Sessions</Headline>
                <div>
                    <CreateRunButton
                        variant="contained"
                        fullWidth
                        startIcon={<StyledAddBoxIcon />}
                        onClick={undefined}
                        disabled={false}>
                        {'New exploration'}
                    </CreateRunButton>
                </div>
            </Header>
            <Wrapper>[Runs go here]</Wrapper>
        </>
    );
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Header = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
}));

const Wrapper = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    padding: theme.spacing(2),
    borderRadius: theme.spacing(1.5),
    marginTop: theme.spacing(1),
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Headline = styled(Typography)(({ theme }) => ({
    color: '#0FCB8C',
    fontSize: 24,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

// const RunItem = styled('div')(({ theme }) => ({
//     marginBottom: theme.spacing(2),
// }));

const CreateRunButton = styled(Button)`
    background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    cursor: pointer;
`;

const StyledAddBoxIcon = styled(AddBoxIcon)`
    color: ${({ theme }) => theme.color['green-100'].hex};
`;
