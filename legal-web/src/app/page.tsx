'use client';

import React, { useEffect, useState } from 'react';
import { config } from '@/lib/config';
import Link from 'next/link';
import { useAuth } from '@clerk/nextjs';
import {
    Scale, Shield, Zap, BookOpen, Users, ArrowRight,
    Check, Star, ChevronRight, Gavel, ScrollText, Database
} from 'lucide-react';
import { usePricing } from '@/hooks/use-pricing';

const FEATURES = [
    {
        icon: <BookOpen size={22} />,
        title: 'Constitutional Analysis',
        description: 'Deep analysis of the 1992 Constitution, amendments, and their real-world implications.',
    },
    {
        icon: <Gavel size={22} />,
        title: 'Case Law Research',
        description: 'Instantly search and summarize Supreme Court and Court of Appeal judgments.',
    },
    {
        icon: <ScrollText size={22} />,
        title: 'Legal History',
        description: 'Trace the evolution of Ghanaian law from customary traditions to modern statutes.',
    },
    {
        icon: <Zap size={22} />,
        title: 'Instant Answers',
        description: 'AI-powered responses in seconds, not hours of manual research.',
    },
    {
        icon: <Shield size={22} />,
        title: 'Verified Sources',
        description: 'Every answer references real case law and constitutional provisions.',
    },
    {
        icon: <Users size={22} />,
        title: 'Built for Professionals',
        description: 'Designed for lawyers, judges, law students, and corporate legal teams.',
    },
];

const COURT_NAMES: Record<string, string> = {
    GHASC: 'Supreme Court',
    GHACA: 'Court of Appeal',
    GHAHC: 'High Court',
    GHACC: 'Commercial Court',
    GHADC: 'District Court',
};

interface PublicStats {
    total_cases: number;
    by_court: Record<string, number>;
}

function DatabaseStats() {
    const [stats, setStats] = useState<PublicStats | null>(null);

    useEffect(() => {
        let mounted = true;
        fetch(`${config.apiUrl}/api/public/stats`)
            .then(res => res.json())
            .then(data => {
                if (mounted) setStats(data);
            })
            .catch(() => {});
        return () => { mounted = false; };
    }, []);

    if (!stats || stats.total_cases === 0) return null;

    const filteredCourts = Object.entries(stats.by_court)
        .filter(([id, count]) => id !== 'UNKNOWN' && count > 0)
        .sort((a, b) => b[1] - a[1]);

    return (
        <section className="px-6 max-w-6xl mx-auto -mt-8 mb-20 relative z-10 animate-fade-in flex justify-center">
            <div className="rounded-2xl p-6 lg:p-8 lg:px-10 flex flex-col lg:flex-row items-center justify-center gap-8 lg:gap-12 overflow-hidden w-fit max-w-full inline-flex"
                 style={{
                     background: 'rgba(12, 14, 20, 0.7)',
                     backdropFilter: 'blur(20px)',
                     border: '1px solid rgba(255, 255, 255, 0.1)',
                     boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                 }}>
                
                {/* Global Total */}
                <div className="flex items-center gap-5 shrink-0 lg:pr-12 lg:border-r border-white/10">
                    <div className="w-14 h-14 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'rgba(255,255,255,0.05)' }}>
                        <Database size={24} style={{ color: 'var(--ghana-gold)' }} />
                    </div>
                    <div className="whitespace-nowrap">
                        <div className="text-[11px] font-bold uppercase tracking-widest text-[#a1a1aa] mb-1">Database Statistics</div>
                        <div className="text-4xl font-extrabold text-white flex items-baseline gap-2">
                            <span>{stats.total_cases.toLocaleString()}</span>
                            <span className="text-base font-medium" style={{ color: 'var(--muted-foreground)' }}>Indexed Cases</span>
                        </div>
                    </div>
                </div>
                
                {/* Court Breakdown */}
                <div className="flex items-center gap-10 lg:gap-12 overflow-x-auto pb-4 lg:pb-0 shrink-0 justify-start"
                     style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                    {filteredCourts.map(([id, count]) => (
                        <div key={id} className="text-left shrink-0 whitespace-nowrap">
                            <div className="text-[11px] font-bold uppercase tracking-wider mb-1" style={{ color: 'var(--muted-foreground)' }}>
                                {COURT_NAMES[id] || id}
                            </div>
                            <div className="text-3xl font-bold bg-clip-text text-transparent"
                                 style={{ backgroundImage: 'linear-gradient(135deg, var(--ghana-gold), #fff)' }}>
                                {count.toLocaleString()}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}

export default function LandingPage() {
    const { isSignedIn } = useAuth();
    const { pricing, loading: pricingLoading } = usePricing();

    const PRICING_TIERS = [
        {
            name: 'Free',
            price: '0',
            currency: '',
            period: '',
            description: 'Try it out with limited access',
            features: [
                `${pricing.free_tier_daily_limit} queries per day`,
                'Constitutional Expert',
                'Basic case law search',
                'Community support',
            ],
            cta: 'Get Started',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--muted-foreground)',
            priceDisplay: 'Free',
            priceLoading: false,
        },
        {
            name: 'Professional',
            price: pricing.pro_monthly_price_ghs.toFixed(0),
            currency: 'GHS',
            period: '/month',
            description: 'For lawyers and paralegals',
            features: [
                'Unlimited queries',
                'All 3 expert modes',
                'Case law deep analysis',
                'Priority response speed',
                'Chat history & export',
                'Email support',
            ],
            cta: 'Start Free Trial',
            href: '/sign-up',
            highlighted: true,
            accentColor: 'var(--ghana-gold)',
            priceLoading: pricingLoading,
        },
        {
            name: 'Enterprise',
            price: pricing.enterprise_monthly_price_ghs.toFixed(0),
            currency: 'GHS',
            period: '/month',
            description: 'For law firms and institutions',
            features: [
                'Everything in Professional',
                'Up to 10 user seats',
                'API access',
                'Custom integrations',
                'Dedicated account manager',
                'SLA guarantee',
            ],
            cta: 'Contact Sales',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--ghana-green)',
            priceLoading: pricingLoading,
        },
    ];

    return (
        <div style={{ background: 'var(--background)', color: 'var(--foreground)' }}
             className="min-h-screen">

            {/* ===== Navigation ===== */}
            <nav className="fixed top-0 w-full z-50"
                 style={{
                     background: 'rgba(12,14,20,0.85)',
                     backdropFilter: 'blur(16px)',
                     borderBottom: '1px solid var(--border)',
                 }}>
                <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                             style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817)' }}>
                            <Scale size={16} className="text-black" />
                        </div>
                        <span className="font-bold text-[15px]">LexGH Legal Research Assistant</span>
                    </div>
                    <div className="flex items-center gap-3">
                        {isSignedIn ? (
                            <Link href="/chat"
                                  className="px-5 py-2.5 text-sm font-semibold rounded-xl"
                                  style={{
                                      background: 'var(--primary)',
                                      color: '#fff',
                                      transition: 'opacity 0.2s',
                                  }}>
                                Go to Dashboard
                            </Link>
                        ) : (
                            <>
                                <Link href="/sign-in"
                                      className="px-4 py-2 text-sm font-medium rounded-lg"
                                      style={{ color: 'var(--muted-foreground)', transition: 'color 0.2s' }}>
                                    Sign In
                                </Link>
                                <Link href="/sign-up"
                                      className="px-5 py-2.5 text-sm font-semibold rounded-xl"
                                      style={{
                                          background: 'var(--primary)',
                                          color: '#fff',
                                          transition: 'opacity 0.2s',
                                      }}>
                                    Get Started
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            {/* ===== Hero Section ===== */}
            <section className="pt-32 pb-20 px-6 text-center">
                <div className="max-w-4xl mx-auto animate-float-in">
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-[12px] font-semibold mb-8"
                         style={{
                             background: 'var(--primary-muted)',
                             color: 'var(--primary)',
                             border: '1px solid rgba(91,106,240,0.2)',
                         }}>
                        <Star size={12} />
                        <span>Powered by Advanced AI</span>
                    </div>

                    <h1 className="text-5xl sm:text-6xl font-extrabold leading-tight mb-6 tracking-tight">
                        <span style={{ color: 'var(--ghana-gold)' }}>LexGH</span>{' '}
                        Legal Research Assistant
                    </h1>

                    <p className="text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed"
                       style={{ color: 'var(--muted-foreground)' }}>
                        AI-powered research for Ghanaian case law and legal precedents.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href={isSignedIn ? '/chat' : '/sign-up'}
                              className="px-8 py-4 text-base font-semibold rounded-xl flex items-center gap-2"
                              style={{
                                  background: 'var(--primary)',
                                  color: '#fff',
                                  boxShadow: '0 4px 24px rgba(91,106,240,0.3)',
                                  transition: 'transform 0.2s, box-shadow 0.2s',
                              }}>
                            {isSignedIn ? 'Go to Dashboard' : 'Start Free'} <ArrowRight size={18} />
                        </Link>
                        <Link href="#pricing"
                              className="px-8 py-4 text-base font-medium rounded-xl flex items-center gap-2"
                              style={{
                                  border: '1px solid var(--border)',
                                  color: 'var(--foreground)',
                                  transition: 'border-color 0.2s',
                              }}>
                            View Pricing <ChevronRight size={18} />
                        </Link>
                    </div>

                    {/* Trust badge */}
                    <p className="mt-10 text-[13px]" style={{ color: 'var(--muted-foreground)', opacity: 0.6 }}>
                        Trusted by legal professionals across Ghana
                    </p>
                </div>
            </section>

            {/* ===== Database Stats ===== */}
            <DatabaseStats />

            {/* ===== Features Grid ===== */}
            <section className="py-20 px-6"
                     style={{ borderTop: '1px solid var(--border)' }}>
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-14">
                        <h2 className="text-3xl font-bold mb-4">
                            Everything You Need for Legal Research
                        </h2>
                        <p className="text-base max-w-xl mx-auto"
                           style={{ color: 'var(--muted-foreground)' }}>
                            Three specialized AI experts trained on the full corpus of Ghanaian law.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                        {FEATURES.map((feature) => (
                            <div key={feature.title}
                                 className="p-6 rounded-2xl"
                                 style={{
                                     background: 'var(--surface-1)',
                                     border: '1px solid var(--border)',
                                     transition: 'border-color 0.2s, transform 0.2s',
                                 }}
                                 onMouseEnter={(e) => {
                                     e.currentTarget.style.borderColor = 'var(--border-hover)';
                                     e.currentTarget.style.transform = 'translateY(-2px)';
                                 }}
                                 onMouseLeave={(e) => {
                                     e.currentTarget.style.borderColor = 'var(--border)';
                                     e.currentTarget.style.transform = 'translateY(0)';
                                 }}
                            >
                                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                                     style={{
                                         background: 'var(--primary-muted)',
                                         color: 'var(--primary)',
                                     }}>
                                    {feature.icon}
                                </div>
                                <h3 className="font-semibold text-base mb-2">{feature.title}</h3>
                                <p className="text-sm leading-relaxed"
                                   style={{ color: 'var(--muted-foreground)' }}>
                                    {feature.description}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Pricing Section ===== */}
            <section id="pricing" className="py-20 px-6"
                     style={{ borderTop: '1px solid var(--border)' }}>
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-14">
                        <h2 className="text-3xl font-bold mb-4">
                            Simple, Transparent Pricing
                        </h2>
                        <p className="text-base max-w-xl mx-auto"
                           style={{ color: 'var(--muted-foreground)' }}>
                            Start free, upgrade when you need more. No hidden fees.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
                        {PRICING_TIERS.map((tier) => (
                            <div key={tier.name}
                                 className="relative p-7 rounded-2xl flex flex-col"
                                 style={{
                                     background: tier.highlighted ? 'var(--surface-2)' : 'var(--surface-1)',
                                     border: tier.highlighted
                                         ? '2px solid var(--ghana-gold)'
                                         : '1px solid var(--border)',
                                     boxShadow: tier.highlighted
                                         ? '0 8px 32px rgba(247,201,72,0.1)'
                                         : 'none',
                                 }}>
                                {/* Popular badge */}
                                {tier.highlighted && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider"
                                         style={{
                                             background: 'var(--ghana-gold)',
                                             color: '#000',
                                         }}>
                                        Most Popular
                                    </div>
                                )}

                                <h3 className="text-lg font-bold mb-1">{tier.name}</h3>
                                <p className="text-sm mb-5" style={{ color: 'var(--muted-foreground)' }}>
                                    {tier.description}
                                </p>

                                <div className="flex items-baseline gap-1 mb-6">
                                    {tier.currency && (
                                        <span className="text-sm font-medium" style={{ color: 'var(--muted-foreground)' }}>
                                            {tier.currency}
                                        </span>
                                    )}
                                    {tier.priceLoading ? (
                                        <span className="h-10 w-16 rounded-lg inline-block animate-pulse"
                                              style={{ background: 'var(--surface-2)' }} />
                                    ) : (
                                        <span className="text-4xl font-extrabold">{tier.price}</span>
                                    )}
                                    {tier.period && !tier.priceLoading && (
                                        <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
                                            {tier.period}
                                        </span>
                                    )}
                                </div>

                                <ul className="space-y-3 mb-8 flex-1">
                                    {tier.features.map((feature) => (
                                        <li key={feature} className="flex items-start gap-3 text-sm">
                                            <Check size={16} className="flex-shrink-0 mt-0.5"
                                                   style={{ color: tier.accentColor }} />
                                            <span>{feature}</span>
                                        </li>
                                    ))}
                                </ul>

                                <Link href={tier.href}
                                      className="w-full py-3 rounded-xl text-sm font-semibold text-center block"
                                      style={{
                                          background: tier.highlighted ? 'var(--ghana-gold)' : 'var(--surface-3)',
                                          color: tier.highlighted ? '#000' : 'var(--foreground)',
                                          transition: 'opacity 0.2s',
                                      }}>
                                    {tier.cta}
                                </Link>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Footer ===== */}
            <footer className="py-10 px-6"
                    style={{ borderTop: '1px solid var(--border)' }}>
                <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                             style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817)' }}>
                            <Scale size={12} className="text-black" />
                        </div>
                        <span className="text-sm font-semibold">LexGH Legal Research Assistant</span>
                    </div>
                    <span className="text-[12px]" style={{ color: 'var(--muted-foreground)' }}>
                        © 2026 EED Soft Consult. All rights reserved.
                    </span>
                </div>
            </footer>
        </div>
    );
}
