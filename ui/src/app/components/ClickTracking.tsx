'use client';

import { useEffect } from 'react';

import { listenForTrackEvents } from '@/analytics/clickTracking';

export default function ClickTracking() {
    useEffect(() => listenForTrackEvents(document.body), []);

    return null;
}
