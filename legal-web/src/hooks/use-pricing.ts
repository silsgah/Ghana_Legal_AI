'use client';

import { useState, useEffect } from 'react';
import { config } from '@/lib/config';

export interface PricingConfig {
    // Daily query limits (-1 = unlimited)
    free_tier_daily_limit: number;
    student_daily_limit: number;
    professional_daily_limit: number;
    firm_daily_limit: number;
    institution_daily_limit: number;
    // Monthly prices (GHS)
    student_monthly_price_ghs: number;
    pro_monthly_price_ghs: number;
    firm_monthly_price_ghs: number;
    institution_monthly_price_ghs: number;
    // Yearly prices (GHS)
    student_yearly_price_ghs: number;
    pro_yearly_price_ghs: number;
    firm_yearly_price_ghs: number;
    institution_yearly_price_ghs: number;
    // Legacy — kept for back-compat with accounts on the deprecated tier
    enterprise_monthly_price_ghs: number;
}

const DEFAULT_PRICING: PricingConfig = {
    free_tier_daily_limit: 5,
    student_daily_limit: 50,
    professional_daily_limit: -1,
    firm_daily_limit: -1,
    institution_daily_limit: -1,
    student_monthly_price_ghs: 50,
    pro_monthly_price_ghs: 350,
    firm_monthly_price_ghs: 800,
    institution_monthly_price_ghs: 3500,
    student_yearly_price_ghs: 500,
    pro_yearly_price_ghs: 3500,
    firm_yearly_price_ghs: 8000,
    institution_yearly_price_ghs: 35000,
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
                    const data: Partial<PricingConfig> = await res.json();
                    // Merge with defaults so any field the API omits (e.g. a
                    // newly-added tier on an older deployed backend) still
                    // has a sane fallback rather than rendering as 0/NaN.
                    setPricing({ ...DEFAULT_PRICING, ...data });
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
