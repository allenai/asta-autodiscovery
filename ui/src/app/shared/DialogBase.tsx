import CloseIcon from '@mui/icons-material/Close';
import { styled, Dialog, DialogContent, DialogProps, DialogTitle, IconButton } from '@mui/material';
import { ReactNode } from 'react';

type DialogBaseProps = {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: ReactNode;
    maxWidth?: DialogProps['maxWidth'];
};

export const DialogBase = ({
    isOpen,
    onClose,
    title,
    children,
    maxWidth = 'sm',
}: DialogBaseProps) => {
    return (
        <Dialog open={isOpen} onClose={onClose} maxWidth={maxWidth}>
            <ModalTitle>{title}</ModalTitle>
            <ModalCloseButton onClick={onClose} aria-label="close">
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
