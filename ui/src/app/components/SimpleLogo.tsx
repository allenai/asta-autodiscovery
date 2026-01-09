'use client';

import { styled } from '@mui/material';

export const SimpleLogo = styled('div')`
    border-radius: 25px;
    width: 53px;
    height: 53px;
    line-height: 1;
    font-size: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    background: ${({ theme }) => theme.color.B2.hex};
`;
