'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@clerk/nextjs';
import { config } from '@/lib/config';

export interface UsageQuota {
    allowed: boolean;
    remaining: number;
    plan: string;
    daily_limit: number;
    used_today: number;
}

export function useUsage() {
    const { getToken, isSignedIn } = useAuth();
    const [usage, setUsage] = useState<UsageQuota | null>(null);
    const [loading, setLoading] = useState(true);

    const fetchUsage = async () => {
        if (!isSignedIn) return;
        
        try {
            const token = await getToken();
            const res = await fetch(`${config.apiUrl}/api/usage`, {
                headers: {
                    Authorization: `Bearer ${token}`
                }
            });
            
            if (res.ok) {
                const data = await res.json();
                setUsage(data);
            }
        } catch (error) {
            console.error("Failed to fetch usage:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUsage();
        // Since WebSocket doesn't trigger a re-fetch natively, we can poll
        // every 30 seconds to keep it updated while chat window is open
        const interval = setInterval(fetchUsage, 30000);
        return () => clearInterval(interval);
    }, [isSignedIn, getToken]);

    // Expose a method to manually refresh (e.g. after a message is sent)
    return { usage, loading, fetchUsage };
}
