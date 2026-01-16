'use client';

import { Box, styled } from '@mui/material';

import AuthButton from '@/components/AuthButton';
import CreditsChip from '@/components/CreditsChip';

export default function Header() {
  return (
    <StyledHeader>
      <CreditsChip />
      <AuthButton />
    </StyledHeader>
  );
}

const StyledHeader = styled(Box)`
  display: flex;
  gap: ${({ theme }) => theme.spacing(2)};
  justify-content: flex-end;
  padding: ${({ theme }) => theme.spacing(2)};
`;
