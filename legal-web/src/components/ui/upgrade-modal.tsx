'use client';

import React, { useState } from 'react';
import Script from 'next/script';
import {
    Check, Zap, ArrowRight, Loader2,
    UserCheck, GraduationCap, Crown, Briefcase, Building2,
} from 'lucide-react';
import { useUser, useAuth } from '@clerk/nextjs';
import { useUsage } from '@/hooks/use-usage';
import { usePricing, type PricingConfig } from '@/hooks/use-pricing';
import { config } from '@/lib/config';
import { cn } from '@/lib/utils';
import {
    Dialog,
    DialogContent,
    DialogTitle,
    DialogDescription,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

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
    accent: string;
    highlighted: boolean;
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
    const [verifying, setVerifying] = useState(false);
    const [verifyError, setVerifyError] = useState<string | null>(null);
    const [cycle, setCycle] = useState<Cycle>('monthly');

    const currentPlan = (usage?.plan || 'free') as TierId;

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

        if (currentPlan === tier) {
            openManageSubscription();
            return;
        }

        const planCode = planCodeForTier(tier, cycle, pricing);
        const amountPesewas = Math.round(priceForTier(tier, cycle, pricing) * 100);

        // @ts-expect-error — PaystackPop is injected by the inline.js script
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
            console.warn(`Paystack plan code not configured for ${tier}_${cycle}. Falling back to one-off charge.`);
            baseConfig.amount = amountPesewas;
        }

        // @ts-expect-error — PaystackPop is injected by the inline.js script
        const handler = window.PaystackPop.setup(baseConfig);
        handler.openIframe();
    };

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
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <Script src="https://js.paystack.co/v1/inline.js" strategy="lazyOnload" />

            <DialogContent
                className="max-w-7xl w-[95vw] max-h-[92vh] overflow-y-auto p-0 gap-0 sm:rounded-2xl"
            >
                {/* Header */}
                <div className="relative p-8 md:p-10 text-center border-b border-border overflow-hidden">
                    <div
                        aria-hidden
                        className="absolute inset-0 pointer-events-none opacity-40"
                        style={{
                            background:
                                'radial-gradient(60% 80% at 50% 0%, color-mix(in oklch, var(--primary) 18%, transparent) 0%, transparent 60%)',
                        }}
                    />

                    <DialogTitle className="relative text-3xl md:text-4xl font-bold mb-2 tracking-tight">
                        Choose your{' '}
                        <span className="text-gradient-gold">LexGH</span>{' '}
                        plan
                    </DialogTitle>
                    <DialogDescription className="relative text-base max-w-2xl mx-auto mb-6">
                        Pay monthly or save with yearly billing. Cancel anytime.
                    </DialogDescription>

                    {/* Billing-cycle toggle */}
                    <div className="relative inline-flex items-center gap-1 p-1 rounded-full bg-muted border border-border">
                        <button
                            type="button"
                            onClick={() => setCycle('monthly')}
                            className={cn(
                                'px-5 py-2 text-[13px] font-semibold rounded-full transition-colors',
                                cycle === 'monthly'
                                    ? 'bg-[var(--ghana-gold)] text-black'
                                    : 'text-muted-foreground hover:text-foreground'
                            )}
                        >
                            Monthly
                        </button>
                        <button
                            type="button"
                            onClick={() => setCycle('yearly')}
                            className={cn(
                                'px-5 py-2 text-[13px] font-semibold rounded-full flex items-center gap-2 transition-colors',
                                cycle === 'yearly'
                                    ? 'bg-[var(--ghana-gold)] text-black'
                                    : 'text-muted-foreground hover:text-foreground'
                            )}
                        >
                            Yearly
                            <span
                                className={cn(
                                    'text-[10px] font-bold px-1.5 py-0.5 rounded',
                                    cycle === 'yearly'
                                        ? 'bg-black/15 text-black'
                                        : 'bg-[var(--ghana-green)] text-white'
                                )}
                            >
                                Save up to 20%
                            </span>
                        </button>
                    </div>
                </div>

                {/* Pricing grid */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 divide-y sm:divide-y-0 sm:divide-x divide-border bg-muted/40">
                    {TIERS.map((tier) => {
                        const price = priceForTier(tier.id, cycle, pricing);
                        const isCurrent = currentPlan === tier.id;
                        const cta = ctaFor(tier);

                        return (
                            <div
                                key={tier.id}
                                className={cn(
                                    'relative p-6 md:p-7 flex flex-col transition-colors duration-300 hover:bg-card/40',
                                    tier.highlighted &&
                                        'bg-gradient-to-b from-[color:color-mix(in_oklch,var(--primary)_8%,transparent)] to-transparent shadow-[inset_0_2px_0_var(--ghana-gold)]'
                                )}
                            >
                                {tier.highlighted && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full shadow-lg whitespace-nowrap bg-[var(--ghana-gold)] text-black">
                                        Most Popular
                                    </div>
                                )}
                                {isCurrent && (
                                    <div className="absolute top-0 right-0 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest rounded-bl-xl bg-card text-[var(--ghana-green)] border-l border-b border-border">
                                        Current
                                    </div>
                                )}

                                <div className="flex items-center gap-2 mb-1.5" style={{ color: tier.accent }}>
                                    {tier.icon}
                                    <h3 className="text-lg font-bold">{tier.name}</h3>
                                </div>

                                <div className="flex items-baseline gap-1 mb-4 min-h-[44px]">
                                    {pricingLoading ? (
                                        <span className="h-9 w-20 rounded-lg inline-block animate-pulse bg-muted" />
                                    ) : tier.id === 'free' ? (
                                        <span className="text-3xl font-bold">Free</span>
                                    ) : (
                                        <>
                                            <span className="text-xs font-medium text-muted-foreground">GHS</span>
                                            <span className="text-3xl font-bold text-foreground">
                                                {price.toLocaleString()}
                                            </span>
                                            <span className="text-xs text-muted-foreground">
                                                /{cycle === 'monthly' ? 'mo' : 'yr'}
                                            </span>
                                        </>
                                    )}
                                </div>

                                <p className="text-xs mb-5 flex-shrink-0 min-h-[32px] text-muted-foreground">
                                    {tier.description}
                                </p>

                                <ul className="space-y-2 mb-6 flex-1">
                                    {tier.features(pricing).map((f) => (
                                        <li key={f} className="flex gap-2 text-xs leading-relaxed text-foreground">
                                            <Check
                                                size={14}
                                                className="flex-shrink-0 mt-0.5"
                                                style={{ color: tier.accent }}
                                            />
                                            <span>{f}</span>
                                        </li>
                                    ))}
                                </ul>

                                <Button
                                    type="button"
                                    onClick={cta.onClick}
                                    disabled={cta.disabled}
                                    size="sm"
                                    variant={
                                        cta.disabled
                                            ? 'outline'
                                            : tier.highlighted
                                                ? 'gold'
                                                : 'default'
                                    }
                                    className={cn(
                                        'w-full text-xs',
                                        !cta.disabled && !tier.highlighted && 'shadow-sm'
                                    )}
                                    style={
                                        !cta.disabled && !tier.highlighted
                                            ? { background: tier.accent, color: 'white' }
                                            : undefined
                                    }
                                >
                                    {cta.label}
                                    {!cta.disabled && <ArrowRight size={13} />}
                                </Button>
                            </div>
                        );
                    })}
                </div>

                {/* Status footers */}
                {verifying && (
                    <div className="px-6 py-3 flex items-center justify-center gap-2 text-sm bg-muted text-[var(--ghana-gold)] border-t border-border">
                        <Loader2 size={16} className="animate-spin" />
                        Confirming your payment — please don&apos;t close this window…
                    </div>
                )}
                {verifyError && !verifying && (
                    <div className="px-6 py-3 text-sm text-center bg-[color:color-mix(in_oklch,var(--destructive)_10%,transparent)] text-destructive border-t border-border">
                        {verifyError}
                    </div>
                )}

                <div className="p-3.5 text-center text-xs bg-card text-muted-foreground border-t border-border">
                    <Zap size={11} className="inline mr-1 text-[var(--ghana-gold)]" />
                    Card payments auto-renew. Mobile Money / Bank / USSD require manual renewal each cycle. Securely processed by Paystack.
                </div>
            </DialogContent>
        </Dialog>
    );
}
