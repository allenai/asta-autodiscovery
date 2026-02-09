'use client';

import { PropsWithChildren, createContext, useContext, useMemo, useState } from 'react';
import { v4 as uuidV4 } from 'uuid';

export enum ToastType {
    'SUCCESS' = 'SUCCESS',
    'ERROR' = 'ERROR',
    'INFO' = 'INFO',
    'WARNING' = 'WARNING',
}

export type Toast = {
    id: string;
    type: ToastType;
    title?: string;
    text?: string;
};

export interface ToastState {
    toasts: Toast[];
    addToast: (toast: Omit<Toast, 'id'>) => void;
    addWarningToast: (title: string, text?: string) => void;
    addInfoToast: (title: string, text?: string) => void;
    addErrorToast: (title: string, text?: string) => void;
    addSuccessToast: (title: string, text?: string) => void;
    removeToast: (toastId: string) => void;
}

export const DEFAULT_STATE: ToastState = {
    toasts: [],
    addToast: () => {},
    removeToast: () => {},
    addWarningToast: () => {},
    addInfoToast: () => {},
    addErrorToast: () => {},
    addSuccessToast: () => {},
};

export const ToastsContext = createContext<ToastState>(DEFAULT_STATE);

export const useToasts = (): ToastState => {
    const context = useContext(ToastsContext);
    if (!context) {
        throw new Error('useToasts must be used within a ToastsContextProvider');
    }
    return context;
};

export type ToastsContextProviderProps = PropsWithChildren<{}>;

export const ToastsContextProvider = ({ children }: ToastsContextProviderProps) => {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const addToast = (toast: Omit<Toast, 'id'>) => {
        const id = uuidV4();
        setToasts((prevToasts: Toast[]) => [...prevToasts, { ...toast, id }]);
    };

    const addSuccessToast = (title: string, text?: string) => {
        addToast({ type: ToastType.SUCCESS, title, text });
    };

    const addWarningToast = (title: string, text?: string) => {
        addToast({ type: ToastType.WARNING, title, text });
    };

    const addInfoToast = (title: string, text?: string) => {
        addToast({ type: ToastType.INFO, title, text });
    };

    const addErrorToast = (title: string, text?: string) => {
        addToast({ type: ToastType.ERROR, title, text });
    };

    const removeToast = (toastId: string) => {
        setToasts((prevToasts: Toast[]) => prevToasts.filter((toast) => toast.id !== toastId));
    };
    const memoizedState = useMemo<ToastState>(
        () => ({
            toasts,
            addToast,
            removeToast,
            addSuccessToast,
            addWarningToast,
            addInfoToast,
            addErrorToast,
        }),
        [toasts, removeToast, addSuccessToast, addWarningToast, addInfoToast, addErrorToast]
    );

    return <ToastsContext.Provider value={memoizedState}>{children}</ToastsContext.Provider>;
};
