'use client';

import React, { useEffect, useState } from 'react';
import {
    X, Check, Zap, Shield, ArrowRight, Loader2,
    UserCheck, GraduationCap, Crown, Briefcase, Building2,
} from 'lucide-react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useUsage } from '@/hooks/use-usage';
import { usePricing, type PricingConfig } from '@/hooks/use-pricing';
import { config } from '@/lib/config';
import Script from 'next/script';

interface UpgradeModalProps {
    isOpen: boolean;
    onClose: () => void;
}

type TierId = 'free' | 'student' | 'professional' | 'firm' | 'institution';
type Cycle = 'monthly' | 'yearly';

interface TierDef {
    id: TierId;
    name: string;
    description: string;
    icon: React.ReactNode;
    features: (pricing: PricingConfig) => string[];
    accent: string;        // CSS color var
    highlighted: boolean;  // "Most Popular" treatment
}

const TIERS: TierDef[] = [
    {
        id: 'free',
        name: 'Free',
        description: 'Try it out with limited access',
        icon: <UserCheck size={18} />,
        features: (p) => [
            `${p.free_tier_daily_limit} queries per day`,
            'Basic case law search',
            'Web access',
            'No credit card required',
        ],
        accent: 'var(--muted-foreground)',
        highlighted: false,
    },
    {
        id: 'student',
        name: 'Student',
        description: 'For law students and academics',
        icon: <GraduationCap size={18} />,
        features: (p) => [
            `${p.student_daily_limit} queries per day`,
            'All three expert modes',
            'Citation export',
            'Chat history',
            'Web and mobile access',
        ],
        accent: 'var(--info)',
        highlighted: false,
    },
    {
        id: 'professional',
        name: 'Professional',
        description: 'For practising lawyers',
        icon: <Crown size={18} />,
        features: () => [
            'Unlimited queries',
            'All three expert modes',
            'Full citation export',
            'Chat history saved',
            'Priority response speed',
            '1 user seat',
        ],
        accent: 'var(--ghana-gold)',
        highlighted: true,
    },
    {
        id: 'firm',
        name: 'Firm',
        description: 'For law firms up to 5 lawyers',
        icon: <Briefcase size={18} />,
        features: () => [
            'Everything in Professional',
            'Up to 5 user seats',
            'Firm admin dashboard',
            'Usage analytics per user',
            'Team management',
        ],
        accent: 'var(--ghana-green)',
        highlighted: false,
    },
    {
        id: 'institution',
        name: 'Institution',
        description: 'For universities and large organisations',
        icon: <Building2 size={18} />,
        features: () => [
            'Everything in Firm',
            'Unlimited user seats',
            'Custom branding option',
            'API access included',
            'Bulk user management',
            'Dedicated account manager',
        ],
        accent: 'var(--primary)',
        highlighted: false,
    },
];

// Map a tier × cycle to the PricingConfig price field and plan-code field.
// Keeping these as direct lookups (not computed names) so TypeScript catches
// any rename in the PricingConfig interface.
function priceForTier(tier: TierId, cycle: Cycle, p: PricingConfig): number {
    if (tier === 'free') return 0;
    if (cycle === 'monthly') {
        if (tier === 'student') return p.student_monthly_price_ghs;
        if (tier === 'professional') return p.pro_monthly_price_ghs;
        if (tier === 'firm') return p.firm_monthly_price_ghs;
        return p.institution_monthly_price_ghs;
    }
    if (tier === 'student') return p.student_yearly_price_ghs;
    if (tier === 'professional') return p.pro_yearly_price_ghs;
    if (tier === 'firm') return p.firm_yearly_price_ghs;
    return p.institution_yearly_price_ghs;
}

function planCodeForTier(tier: TierId, cycle: Cycle, p: PricingConfig): string {
    if (tier === 'free') return '';
    if (cycle === 'monthly') {
        if (tier === 'student') return p.paystack_plan_student_monthly;
        if (tier === 'professional') return p.paystack_plan_pro_monthly;
        if (tier === 'firm') return p.paystack_plan_firm_monthly;
        return p.paystack_plan_institution_monthly;
    }
    if (tier === 'student') return p.paystack_plan_student_yearly;
    if (tier === 'professional') return p.paystack_plan_pro_yearly;
    if (tier === 'firm') return p.paystack_plan_firm_yearly;
    return p.paystack_plan_institution_yearly;
}

export function UpgradeModal({ isOpen, onClose }: UpgradeModalProps) {
    const { usage, fetchUsage } = useUsage();
    const { user } = useUser();
    const { getToken } = useAuth();
    const { pricing, loading: pricingLoading } = usePricing();
    const [isMounted, setIsMounted] = useState(false);
    const [verifying, setVerifying] = useState(false);
    const [verifyError, setVerifyError] = useState<string | null>(null);
    const [cycle, setCycle] = useState<Cycle>('monthly');

    useEffect(() => { setIsMounted(true); }, []);

    if (!isMounted || !isOpen) return null;

    const currentPlan = (usage?.plan || 'free') as TierId | 'enterprise';
    const isLegacyEnterprise = currentPlan === 'enterprise';

    const verifyPayment = async (reference: string) => {
        setVerifying(true);
        setVerifyError(null);
        try {
            const token = await getToken();
            const res = await fetch(`${config.apiUrl}/api/billing/verify-payment`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ reference }),
            });
            const data = await res.json();
            if (!res.ok) {
                setVerifyError(data.detail || 'We could not confirm your payment. Reference: ' + reference);
                return;
            }
            await fetchUsage();
            onClose();
        } catch {
            setVerifyError('Network error confirming your payment. Reference: ' + reference);
        } finally {
            setVerifying(false);
        }
    };

    const openManageSubscription = async () => {
        setVerifyError(null);
        try {
            const token = await getToken();
            const res = await fetch(`${config.apiUrl}/api/billing/manage-subscription`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            });
            const data = await res.json();
            if (!res.ok || !data.link) {
                setVerifyError(data.detail || 'Could not load subscription management. Please email support.');
                return;
            }
            window.open(data.link, '_blank', 'noopener,noreferrer');
        } catch {
            setVerifyError('Network error loading subscription management.');
        }
    };

    const startCheckoutForTier = (tier: TierId) => {
        setVerifyError(null);

        if (tier === 'free') return;

        // Already on this tier → open Paystack-hosted manage page.
        if (currentPlan === tier) {
            openManageSubscription();
            return;
        }

        const planCode = planCodeForTier(tier, cycle, pricing);
        const amountPesewas = Math.round(priceForTier(tier, cycle, pricing) * 100);

        // @ts-ignore — PaystackPop is injected by the inline.js script
        if (typeof window.PaystackPop === 'undefined') {
            window.open('https://paystack.com/pay/ghana-legal-pro', '_blank');
            return;
        }

        const baseConfig: Record<string, unknown> = {
            key: process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY || '',
            email: user?.primaryEmailAddress?.emailAddress || 'user@ghanalegal.ai',
            currency: 'GHS',
            channels: ['card', 'mobile_money', 'bank', 'ussd'],
            metadata: {
                clerk_id: user?.id,
                // Resolver uses these to upgrade the correct tier × cycle.
                plan: tier,
                cycle,
                custom_fields: [
                    { display_name: 'Clerk User ID', variable_name: 'clerk_id', value: user?.id || '' },
                    { display_name: 'Plan', variable_name: 'plan', value: tier },
                    { display_name: 'Billing Cycle', variable_name: 'cycle', value: cycle },
                ],
            },
            callback: function (response: { reference: string }) {
                setTimeout(() => { verifyPayment(response.reference); }, 0);
            },
            onClose: function () {},
        };

        if (planCode) {
            baseConfig.plan = planCode;
        } else {
            console.warn(`Paystack plan code not configured for ${tier}_${cycle}. Falling back to one-off charge (no auto-renewal).`);
            baseConfig.amount = amountPesewas;
        }

        // @ts-ignore
        const handler = window.PaystackPop.setup(baseConfig);
        handler.openIframe();
    };

    // Per-tier button content and behaviour.
    function ctaFor(tier: TierDef): { label: string; disabled: boolean; onClick: () => void } {
        if (tier.id === 'free') {
            return {
                label: currentPlan === 'free' ? 'Current Plan' : 'Cancel current plan to downgrade',
                disabled: true,
                onClick: () => {},
            };
        }
        if (currentPlan === tier.id) {
            return {
                label: 'Manage / Cancel',
                disabled: false,
                onClick: () => openManageSubscription(),
            };
        }
        return {
            label: `Choose ${tier.name}`,
            disabled: false,
            onClick: () => startCheckoutForTier(tier.id),
        };
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 overflow-y-auto"
             style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}>

            <Script src="https://js.paystack.co/v1/inline.js" strategy="lazyOnload" />

            {/* Modal Container */}
            <form
                onSubmit={(e) => e.preventDefault()}
                className="relative w-full max-w-7xl my-8 rounded-3xl overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200"
                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>

                <button
                    onClick={onClose}
                    type="button"
                    className="absolute top-4 right-4 z-10 p-2 rounded-full hover:bg-white/10 transition-colors"
                    style={{ color: 'var(--muted-foreground)' }}>
                    <X size={20} />
                </button>

                {/* Header */}
                <div className="p-8 md:p-10 text-center border-b border-white/5 relative overflow-hidden">
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full max-w-3xl opacity-30 pointer-events-none"
                         style={{ background: 'radial-gradient(circle, var(--primary-muted) 0%, transparent 70%)' }} />

                    <h2 className="text-3xl md:text-4xl font-bold mb-3 tracking-tight" style={{ color: 'var(--foreground)' }}>
                        Choose your <span style={{ color: 'var(--ghana-gold)' }}>LexGH</span> plan
                    </h2>
                    <p className="text-base max-w-2xl mx-auto mb-6" style={{ color: 'var(--muted-foreground)' }}>
                        Pay monthly or save with yearly billing. Cancel anytime.
                    </p>

                    {/* Billing-cycle toggle */}
                    <div className="inline-flex items-center gap-1 p-1 rounded-full relative z-10"
                         style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                        <button type="button" onClick={() => setCycle('monthly')}
                                className="px-5 py-2 text-[13px] font-semibold rounded-full transition-colors"
                                style={{
                                    background: cycle === 'monthly' ? 'var(--ghana-gold)' : 'transparent',
                                    color: cycle === 'monthly' ? '#000' : 'var(--muted-foreground)',
                                }}>
                            Monthly
                        </button>
                        <button type="button" onClick={() => setCycle('yearly')}
                                className="px-5 py-2 text-[13px] font-semibold rounded-full flex items-center gap-2 transition-colors"
                                style={{
                                    background: cycle === 'yearly' ? 'var(--ghana-gold)' : 'transparent',
                                    color: cycle === 'yearly' ? '#000' : 'var(--muted-foreground)',
                                }}>
                            Yearly
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                                  style={{
                                      background: cycle === 'yearly' ? 'rgba(0,0,0,0.15)' : 'var(--ghana-green)',
                                      color: cycle === 'yearly' ? '#000' : '#fff',
                                  }}>
                                Save up to 20%
                            </span>
                        </button>
                    </div>
                </div>

                {/* Legacy Enterprise banner */}
                {isLegacyEnterprise && (
                    <div className="px-6 py-3 flex items-center justify-between gap-3 flex-wrap"
                         style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                        <div className="text-sm flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
                            <Shield size={14} style={{ color: 'var(--primary)' }} />
                            You&apos;re on the legacy <strong>Enterprise</strong> plan. Contact support to move to Institution.
                        </div>
                        <button type="button" onClick={openManageSubscription}
                                className="text-xs font-semibold px-3 py-1.5 rounded-lg"
                                style={{ background: 'var(--primary)', color: '#fff' }}>
                            Manage Subscription
                        </button>
                    </div>
                )}

                {/* Pricing Grid — 5 tiers */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-0 divide-y sm:divide-y-0 sm:divide-x divide-white/5"
                     style={{ background: 'var(--surface-2)' }}>

                    {TIERS.map(tier => {
                        const price = priceForTier(tier.id, cycle, pricing);
                        const isCurrent = currentPlan === tier.id;
                        const cta = ctaFor(tier);
                        const cardStyle: React.CSSProperties = tier.highlighted
                            ? {
                                background: 'linear-gradient(to bottom, var(--primary-muted), transparent)',
                                boxShadow: 'inset 0 2px 0 var(--ghana-gold)',
                            }
                            : {};

                        return (
                            <div key={tier.id}
                                 className="p-6 md:p-7 flex flex-col relative transition-colors duration-300 hover:bg-white/[0.02]"
                                 style={cardStyle}>

                                {/* Badges */}
                                {tier.highlighted && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full shadow-lg whitespace-nowrap"
                                         style={{ background: 'var(--ghana-gold)', color: '#000' }}>
                                        Most Popular
                                    </div>
                                )}
                                {isCurrent && (
                                    <div className="absolute top-0 right-0 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest rounded-bl-xl rounded-tr-3xl"
                                         style={{ background: 'var(--surface-3)', color: 'var(--ghana-green)' }}>
                                        Current
                                    </div>
                                )}

                                {/* Title row */}
                                <div className="flex items-center gap-2 mb-1.5" style={{ color: tier.accent }}>
                                    {tier.icon}
                                    <h3 className="text-lg font-bold">{tier.name}</h3>
                                </div>

                                {/* Price */}
                                <div className="flex items-baseline gap-1 mb-4 min-h-[44px]">
                                    {pricingLoading ? (
                                        <span className="h-9 w-20 rounded-lg inline-block animate-pulse"
                                              style={{ background: 'rgba(255,255,255,0.08)' }} />
                                    ) : tier.id === 'free' ? (
                                        <span className="text-3xl font-bold">Free</span>
                                    ) : (
                                        <>
                                            <span className="text-xs font-medium" style={{ color: 'var(--muted-foreground)' }}>GHS</span>
                                            <span className="text-3xl font-bold" style={{ color: 'var(--foreground)' }}>
                                                {price.toLocaleString()}
                                            </span>
                                            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                /{cycle === 'monthly' ? 'mo' : 'yr'}
                                            </span>
                                        </>
                                    )}
                                </div>

                                <p className="text-xs mb-5 flex-shrink-0 min-h-[32px]" style={{ color: 'var(--muted-foreground)' }}>
                                    {tier.description}
                                </p>

                                {/* Features */}
                                <ul className="space-y-2 mb-6 flex-1">
                                    {tier.features(pricing).map(f => (
                                        <li key={f} className="flex gap-2 text-xs leading-relaxed" style={{ color: 'var(--foreground)' }}>
                                            <Check size={14} className="flex-shrink-0 mt-0.5" style={{ color: tier.accent }} />
                                            <span>{f}</span>
                                        </li>
                                    ))}
                                </ul>

                                {/* CTA */}
                                <button
                                    type="button"
                                    onClick={cta.onClick}
                                    disabled={cta.disabled}
                                    className="w-full py-2.5 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition-transform hover:scale-[1.02] active:scale-[0.98]"
                                    style={
                                        cta.disabled
                                            ? { borderWidth: 1, borderStyle: 'solid', borderColor: 'var(--border)', color: 'var(--muted-foreground)' }
                                            : tier.highlighted
                                                ? { background: 'var(--ghana-gold)', color: '#000', boxShadow: '0 6px 20px rgba(240,192,64,0.25)' }
                                                : { background: tier.accent, color: '#fff' }
                                    }>
                                    {cta.label}
                                    {!cta.disabled && <ArrowRight size={13} />}
                                </button>
                            </div>
                        );
                    })}
                </div>

                {/* Status footers */}
                {verifying && (
                    <div className="px-6 py-3 flex items-center justify-center gap-2 text-sm"
                         style={{ background: 'var(--surface-2)', color: 'var(--ghana-gold)', borderTop: '1px solid var(--border)' }}>
                        <Loader2 size={16} className="animate-spin" />
                        Confirming your payment — please don&apos;t close this window…
                    </div>
                )}
                {verifyError && !verifying && (
                    <div className="px-6 py-3 text-sm text-center"
                         style={{ background: 'rgba(239,68,68,0.08)', color: 'var(--error)', borderTop: '1px solid var(--border)' }}>
                        {verifyError}
                    </div>
                )}

                <div className="p-3.5 text-center text-xs"
                     style={{ background: 'var(--surface-1)', color: 'var(--muted-foreground)', borderTop: '1px solid var(--border)' }}>
                    <Zap size={11} className="inline mr-1" style={{ color: 'var(--ghana-gold)' }} />
                    Card payments auto-renew. Mobile Money / Bank / USSD require manual renewal each cycle.
                    Securely processed by Paystack.
                </div>
            </form>
        </div>
    );
}
