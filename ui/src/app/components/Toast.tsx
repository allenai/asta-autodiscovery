'use client';

import CloseIcon from '@mui/icons-material/Close';
import { Alert, AlertTitle, IconButton, styled } from '@mui/material';
import { useEffect, useState } from 'react';

import { Toast as ToastModel, ToastType, useToasts } from '@/contexts/ToastsContext';
import { filterTransientProps } from '@/utils/styledProps';

type ToastProps = {
    toast: ToastModel;
};

const TOAST_DURATION_MS = 8000; // How long a toast is on screen before hiding

export const Toast = ({ toast }: ToastProps) => {
    const { removeToast } = useToasts();
    const severity = getToastSeverity(toast.type);
    let timer: NodeJS.Timeout;
    const [isHidden, setIsHidden] = useState(false);

    const startTimer = (): void => {
        timer = setTimeout(handleClose, TOAST_DURATION_MS);
    };

    const cancelTimer = (): void => {
        clearTimeout(timer);
    };

    const handleClose = (): void => {
        cancelTimer();
        setIsHidden(true);
        // wait for the animation to finish before removing the toast
        setTimeout(() => {
            removeToast(toast.id);
        }, 300);
    };

    useEffect(() => {
        startTimer();
        return cancelTimer;
    }, []);

    return (
        <StyledAlert
            $isHidden={isHidden}
            variant="filled"
            severity={severity}
            action={
                <IconButton aria-label="close" color="inherit" size="small" onClick={handleClose}>
                    <CloseIcon fontSize="inherit" />
                </IconButton>
            }>
            {toast.title && <AlertTitle>{toast.title}</AlertTitle>}
            <div style={{ whiteSpace: 'pre-line' }}>{toast.text}</div>
        </StyledAlert>
    );
};

const StyledAlert = styled(Alert, {
    shouldForwardProp: filterTransientProps,
})<{ $isHidden: boolean }>`
    @keyframes slideIn {
        0% {
            transform: translate(-50%, -100%);
            opacity: 0;
        }
        100% {
            transform: translate(-50%, 0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        0% {
            transform: translate(-50%, 0);
            opacity: 1;
        }
        100% {
            transform: translate(-50%, -100%);
            opacity: 0;
        }
    }

    animation: ${({ $isHidden }) =>
        $isHidden ? 'slideOut 0.3s ease-in forwards' : 'slideIn 0.3s ease-out forwards'};
    left: 50%;
    position: absolute;
    top: ${({ theme }) => theme.spacing(3)};
    z-index: 1200;
`;

// matches the severity of the toast type to the severity of the Alert component: https://mui.com/material-ui/api/alert/
const getToastSeverity = (type: string) => {
    switch (type) {
        case ToastType.SUCCESS:
            return 'success';
        case ToastType.ERROR:
            return 'error';
        case ToastType.WARNING:
            return 'warning';
        case ToastType.INFO:
            return 'info';
        default:
            return 'info';
    }
};
