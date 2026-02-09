'use client';

import { Toast } from '@/components/Toast';
import { useToasts } from '@/contexts/ToastsContext';

export const Toasts = () => {
    const { toasts } = useToasts();

    return toasts.map((toast, index) => {
        return <Toast key={index} toast={toast} />;
    });
};
