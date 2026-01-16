'use client';

import { Chip, styled } from '@mui/material';

export default function CreditsChip() {
  return <StyledChip label="Experiment Credits: 1,000"></StyledChip>;
}

const StyledChip = styled(Chip)`
  &.MuiChip-root {
    background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    border-radius: 4px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    font-size: 0.85rem;
    padding: ${({ theme }) => theme.spacing(0.5, 1)};
  }
`;
