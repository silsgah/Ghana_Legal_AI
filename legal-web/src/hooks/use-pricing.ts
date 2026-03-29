'use client';

import { useState, useEffect } from 'react';
import { config } from '@/lib/config';

export interface PricingConfig {
    free_tier_daily_limit: number;
    pro_monthly_price_ghs: number;
    enterprise_monthly_price_ghs: number;
}

const DEFAULT_PRICING: PricingConfig = {
    free_tier_daily_limit: 5,
    pro_monthly_price_ghs: 99,
    enterprise_monthly_price_ghs: 299,
};

/**
 * Fetches live plan pricing from the backend.
 * Falls back to default values while loading or on error.
 * No auth required — calls the public /api/pricing endpoint.
 */
export function usePricing() {
    const [pricing, setPricing] = useState<PricingConfig>(DEFAULT_PRICING);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;

        const fetchPricing = async () => {
            try {
                const res = await fetch(`${config.apiUrl}/api/pricing`);
                if (res.ok && !cancelled) {
                    const data: PricingConfig = await res.json();
                    setPricing(data);
                }
            } catch {
                // Silently fall back to defaults
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        fetchPricing();
        return () => { cancelled = true; };
    }, []);

    return { pricing, loading };
}
