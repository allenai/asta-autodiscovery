import CloseIcon from '@mui/icons-material/Close';
import { styled, Dialog, DialogContent, DialogProps, DialogTitle, IconButton } from '@mui/material';
import { ReactNode } from 'react';

import { TEST_ID_DIALOG_CLOSE_BUTTON } from '@/testIds';

type DialogBaseProps = {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    maxWidth?: DialogProps['maxWidth'];
    testId?: string;
};

export const DialogBase = ({
    isOpen,
    onClose,
    title,
    children,
    maxWidth = 'sm',
    testId,
}: DialogBaseProps) => {
    return (
        <Dialog
            open={isOpen}
            onClose={onClose}
            maxWidth={maxWidth}
            PaperProps={testId ? ({ 'data-test-id': testId } as object) : undefined}>
            <ModalTitle>{title}</ModalTitle>
            <ModalCloseButton
                onClick={onClose}
                aria-label="close"
                data-test-id={TEST_ID_DIALOG_CLOSE_BUTTON}>
                <CloseIcon />
            </ModalCloseButton>
            <DialogContent>{children}</DialogContent>
        </Dialog>
    );
};

const ModalTitle = styled(DialogTitle)`
    &.MuiDialogTitle-root {
        color: ${({ theme }) => theme.color['dark-teal-100'].hex};
        font-weight: 500;
        font-size: 1.5rem;
        line-height: ${({ theme }) => theme.spacing(3.5)};
        padding-bottom: 0;
    }
`;

const ModalCloseButton = styled(IconButton)`
    && {
        position: absolute;
        right: ${({ theme }) => theme.spacing(1)};
        top: ${({ theme }) => theme.spacing(1)};
        color: ${({ theme }) => theme.palette.grey[500]};
    }
`;

export const BulletList = styled('ul')`
    margin: ${({ theme }) => theme.spacing(1, 0)};
    padding-left: ${({ theme }) => theme.spacing(3)};
    & > li {
        margin-bottom: ${({ theme }) => theme.spacing(1)};
    }
`;
