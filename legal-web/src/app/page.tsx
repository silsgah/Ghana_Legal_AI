'use client';

import React, { useEffect, useState } from 'react';
import { config } from '@/lib/config';
import Link from 'next/link';
import { useAuth } from '@clerk/nextjs';
import {
    Scale, Shield, Zap, BookOpen, Users, ArrowRight,
    Check, ChevronRight, Gavel, ScrollText, Database, Loader2
} from 'lucide-react';
import { usePricing } from '@/hooks/use-pricing';

const FEATURES = [
    {
        icon: <BookOpen size={24} />,
        title: 'Constitutional Analysis',
        description: 'Deep analysis of the 1992 Constitution, amendments, and their real-world implications for practice.',
    },
    {
        icon: <Gavel size={24} />,
        title: 'Case Law Research',
        description: 'Instantly search and summarize Supreme Court and Court of Appeal judgments with citations.',
    },
    {
        icon: <ScrollText size={24} />,
        title: 'Legal History',
        description: 'Trace the evolution of Ghanaian law from customary traditions to modern statutes.',
    },
    {
        icon: <Zap size={24} />,
        title: 'Instant Answers',
        description: 'AI-powered responses grounded in real case law, delivered in seconds — not hours.',
    },
    {
        icon: <Shield size={24} />,
        title: 'Verified Sources',
        description: 'Every answer is linked to retrieved case law and constitutional provisions with citation chips.',
    },
    {
        icon: <Users size={24} />,
        title: 'Built for Professionals',
        description: 'Designed for lawyers, judges, law students, and corporate legal teams across Ghana.',
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
        .map(([id, count]) => ({ id, label: COURT_NAMES[id] || id, value: count }))
        .sort((a, b) => b.value - a.value);

    const total = filteredCourts.reduce((sum, c) => sum + c.value, 0);
    const max = Math.max(...filteredCourts.map(c => c.value), 1);

    return (
        <section className="px-6 max-w-4xl mx-auto -mt-8 mb-24 relative z-10 animate-fade-in">
            <div className="rounded-3xl p-8 lg:p-10"
                 style={{
                     background: 'rgba(12, 15, 22, 0.75)',
                     backdropFilter: 'blur(24px)',
                     border: '1px solid rgba(240, 192, 64, 0.1)',
                     boxShadow: '0 12px 48px rgba(0,0,0,0.4), 0 0 40px rgba(240,192,64,0.04)',
                 }}>

                {/* Header: icon + total */}
                <div className="flex items-center justify-between gap-4 mb-8 pb-6" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
                    <div className="flex items-center gap-4 min-w-0">
                        <div className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0"
                             style={{ background: 'rgba(240,192,64,0.08)', border: '1px solid rgba(240,192,64,0.12)' }}>
                            <Database size={24} style={{ color: 'var(--ghana-gold)' }} />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[12px] font-bold uppercase tracking-widest mb-1" style={{ color: 'var(--ghana-gold)', opacity: 0.8 }}>
                                Live Database
                            </div>
                            <div className="text-[15px]" style={{ color: 'var(--muted-foreground)' }}>
                                Judgments indexed across Ghanaian courts
                            </div>
                        </div>
                    </div>
                    <div className="text-right shrink-0">
                        <div className="text-4xl sm:text-5xl font-extrabold tabular-nums bg-clip-text text-transparent leading-none"
                             style={{ backgroundImage: 'linear-gradient(135deg, var(--ghana-gold), #fff)' }}>
                            {stats.total_cases.toLocaleString()}
                        </div>
                        <div className="text-[12px] font-semibold uppercase tracking-wider mt-1.5"
                             style={{ color: 'var(--muted-foreground)' }}>
                            Total Cases
                        </div>
                    </div>
                </div>

                {/* Court breakdown — bar chart */}
                <div className="space-y-4">
                    {filteredCourts.map(({ id, label, value }) => {
                        const pct = total > 0 ? (value / total) * 100 : 0;
                        const barWidth = (value / max) * 100;
                        return (
                            <div key={id} className="min-w-0">
                                <div className="flex items-baseline justify-between gap-3 mb-2 min-w-0">
                                    <span className="text-[15px] font-medium truncate text-white" title={label}>
                                        {label}
                                    </span>
                                    <div className="flex items-baseline gap-2.5 shrink-0">
                                        <span className="text-[12px] font-mono tabular-nums"
                                              style={{ color: 'var(--muted-foreground)' }}>
                                            {pct.toFixed(1)}%
                                        </span>
                                        <span className="text-[15px] font-mono font-bold tabular-nums"
                                              style={{ color: 'var(--ghana-gold)' }}>
                                            {value.toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                                <div className="h-2.5 rounded-full overflow-hidden"
                                     style={{ background: 'rgba(255,255,255,0.06)' }}>
                                    <div className="h-full rounded-full transition-all duration-700"
                                         style={{
                                             width: `${barWidth}%`,
                                             background: 'linear-gradient(90deg, var(--ghana-gold), #d4a017)',
                                             boxShadow: '0 0 12px rgba(240,192,64,0.3)',
                                         }} />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}

interface Feedback {
    id: number;
    name: string;
    content: string;
    created_at: string;
}

function Testimonials({ isSignedIn, getToken }: { isSignedIn: boolean; getToken: () => Promise<string | null> }) {
    const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
    const [showForm, setShowForm] = useState(false);
    const [name, setName] = useState('');
    const [content, setContent] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [feedbackMessage, setFeedbackMessage] = useState('');

    const fetchFeedbacks = () => {
        fetch(`${config.apiUrl}/api/public/feedback`)
            .then(res => res.json())
            .then(data => {
                if (Array.isArray(data)) setFeedbacks(data);
            })
            .catch(() => {});
    };

    useEffect(() => {
        fetchFeedbacks();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);
        setFeedbackMessage('');
        try {
            const token = await getToken();
            const res = await fetch(`${config.apiUrl}/api/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${token}`
                },
                body: JSON.stringify({ name, content })
            });
            if (res.ok) {
                setFeedbackMessage('Thank you for your feedback!');
                setShowForm(false);
                setName('');
                setContent('');
                fetchFeedbacks(); // Refresh list
            } else {
                setFeedbackMessage('Failed to submit feedback.');
            }
        } catch (err) {
            setFeedbackMessage('An error occurred.');
        } finally {
            setSubmitting(false);
            setTimeout(() => setFeedbackMessage(''), 5000);
        }
    };

    return (
        <section className="py-28 px-6">
            <div className="max-w-7xl mx-auto">
                <div className="text-center mb-16">
                    <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block" style={{ color: 'var(--ghana-green)' }}>Testimonials</span>
                    <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">What Our Users Say</h2>
                    <p className="text-[17px] max-w-xl mx-auto leading-relaxed" style={{ color: 'var(--muted-foreground)' }}>
                        Feedback from legal professionals using LexGH.
                    </p>
                </div>

                {feedbacks.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                        {feedbacks.map(f => (
                            <div key={f.id} className="p-7 rounded-2xl flex flex-col relative overflow-hidden"
                                 style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', transition: 'transform 0.2s, border-color 0.2s' }}
                                 onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.borderColor = 'rgba(240,192,64,0.2)'; }}
                                 onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.borderColor = 'var(--border)'; }}>
                                {/* Quote mark */}
                                <div className="absolute top-4 right-6 text-[48px] font-serif leading-none pointer-events-none" style={{ color: 'var(--ghana-gold)', opacity: 0.1 }}>”</div>
                                <div className="flex items-center gap-3.5 mb-5">
                                    <div className="w-11 h-11 rounded-full flex items-center justify-center font-bold text-[15px]"
                                         style={{ background: 'rgba(240,192,64,0.1)', color: 'var(--ghana-gold)', border: '1px solid rgba(240,192,64,0.15)' }}>
                                        {f.name.charAt(0).toUpperCase()}
                                    </div>
                                    <div>
                                        <div className="font-semibold text-[15px]">{f.name}</div>
                                        <div className="text-[12px]" style={{ color: 'var(--muted-foreground)' }}>
                                            {new Date(f.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                </div>
                                <p className="text-[15px] italic leading-relaxed flex-1" style={{ color: 'var(--muted-foreground)' }}>
                                    &ldquo;{f.content}&rdquo;
                                </p>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="text-center mb-12 text-[15px]" style={{ color: 'var(--muted-foreground)' }}>
                        No feedback yet. Be the first!
                    </div>
                )}

                {isSignedIn && (
                    <div className="max-w-lg mx-auto text-center">
                        {!showForm ? (
                            <button onClick={() => setShowForm(true)}
                                    className="px-6 py-3 rounded-xl text-sm font-semibold transition-transform hover:scale-105"
                                    style={{ background: 'var(--surface-2)', color: 'var(--foreground)', border: '1px solid var(--border)' }}>
                                Leave Feedback
                            </button>
                        ) : (
                            <form onSubmit={handleSubmit} className="text-left p-6 rounded-2xl animate-fade-in" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                                <h3 className="font-bold mb-4">Submit Feedback</h3>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Display Name</label>
                                    <input required type="text" value={name} onChange={e => setName(e.target.value)}
                                           className="w-full px-4 py-2 rounded-lg text-sm"
                                           style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                                </div>
                                <div className="mb-4">
                                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--muted-foreground)' }}>Feedback</label>
                                    <textarea required rows={4} value={content} onChange={e => setContent(e.target.value)}
                                              className="w-full px-4 py-2 rounded-lg text-sm resize-none"
                                              style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }} />
                                </div>
                                <div className="flex items-center justify-between">
                                    <button type="button" onClick={() => setShowForm(false)}
                                            className="text-sm px-4 py-2 transition-colors hover:text-white" style={{ color: 'var(--muted-foreground)' }}>Cancel</button>
                                    <button type="submit" disabled={submitting}
                                            className="px-6 py-2 rounded-lg text-sm font-semibold transition-opacity"
                                            style={{ background: 'var(--primary)', color: '#fff', opacity: submitting ? 0.7 : 1 }}>
                                        {submitting ? 'Submitting...' : 'Submit'}
                                    </button>
                                </div>
                            </form>
                        )}
                        {feedbackMessage && <p className="mt-4 text-sm font-medium animate-fade-in" style={{ color: 'var(--ghana-green)' }}>{feedbackMessage}</p>}
                    </div>
                )}
            </div>
        </section>
    );
}

export default function LandingPage() {
    const { isSignedIn, getToken } = useAuth();
    const { pricing, loading: pricingLoading } = usePricing();
    const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

    const isYearly = billingCycle === 'yearly';
    const period = isYearly ? '/year' : '/month';

    const PRICING_TIERS = [
        {
            name: 'Free',
            price: '0',
            currency: '',
            period: '',
            description: 'Try it out with limited access',
            features: [
                `${pricing.free_tier_daily_limit} queries per day`,
                'Basic case law search',
                'Web access',
                'No credit card required',
            ],
            cta: 'Get Started Free',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--muted-foreground)',
            priceDisplay: 'Free',
            priceLoading: false,
        },
        {
            name: 'Student',
            price: (isYearly ? pricing.student_yearly_price_ghs : pricing.student_monthly_price_ghs).toFixed(0),
            currency: 'GHS',
            period,
            description: 'For law students and academics',
            features: [
                `${pricing.student_daily_limit} queries per day`,
                'All three expert modes',
                'Citation export',
                'Chat history',
                'Web and mobile access',
            ],
            cta: 'Start Student Plan',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--info)',
            priceLoading: pricingLoading,
        },
        {
            name: 'Professional',
            price: (isYearly ? pricing.pro_yearly_price_ghs : pricing.pro_monthly_price_ghs).toFixed(0),
            currency: 'GHS',
            period,
            description: 'For practising lawyers',
            features: [
                'Unlimited queries',
                'All three expert modes',
                'Full citation export',
                'Chat history saved',
                'Priority response speed',
                '1 user seat',
            ],
            cta: 'Start Professional Plan',
            href: '/sign-up',
            highlighted: true,
            accentColor: 'var(--ghana-gold)',
            priceLoading: pricingLoading,
        },
        {
            name: 'Firm',
            price: (isYearly ? pricing.firm_yearly_price_ghs : pricing.firm_monthly_price_ghs).toFixed(0),
            currency: 'GHS',
            period,
            description: 'For law firms up to 5 lawyers',
            features: [
                'Everything in Professional',
                'Up to 5 user seats',
                'Firm admin dashboard',
                'Usage analytics per user',
                'Team management',
            ],
            cta: 'Start Firm Plan',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--ghana-green)',
            priceLoading: pricingLoading,
        },
        {
            name: 'Institution',
            price: (isYearly ? pricing.institution_yearly_price_ghs : pricing.institution_monthly_price_ghs).toFixed(0),
            currency: 'GHS',
            period,
            description: 'For universities and large organisations',
            features: [
                'Everything in Firm',
                'Unlimited user seats',
                'Custom branding option',
                'API access included',
                'Student management dashboard',
                'Bulk user management',
                'Dedicated account manager',
            ],
            cta: 'Contact Us',
            href: '/sign-up',
            highlighted: false,
            accentColor: 'var(--primary)',
            priceLoading: pricingLoading,
        },
    ];

    return (
        <div style={{ background: 'var(--background)', color: 'var(--foreground)' }}
             className="min-h-screen">

            {/* ===== Navigation ===== */}
            <nav className="fixed top-0 w-full z-50"
                 style={{
                     background: 'rgba(10,13,19,0.8)',
                     backdropFilter: 'blur(24px)',
                     borderBottom: '1px solid rgba(255,255,255,0.06)',
                 }}>
                <div className="max-w-7xl mx-auto px-6 h-[72px] flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                             style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)', boxShadow: '0 4px 12px rgba(240,192,64,0.3)' }}>
                            <Scale size={18} className="text-black" />
                        </div>
                        <div>
                            <span className="font-bold text-[17px] block leading-tight">LexGH</span>
                            <span className="text-[11px] font-medium" style={{ color: 'var(--ghana-gold)', opacity: 0.7 }}>Legal Research</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        {isSignedIn ? (
                            <Link href="/chat"
                                  className="px-6 py-2.5 text-[14px] font-semibold rounded-xl"
                                  style={{
                                      background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
                                      color: '#fff',
                                      boxShadow: '0 4px 16px rgba(98,114,240,0.35)',
                                  }}>
                                Go to Dashboard
                            </Link>
                        ) : (
                            <>
                                <Link href="/sign-in"
                                      className="px-5 py-2.5 text-[14px] font-medium rounded-xl hidden sm:block"
                                      style={{ color: 'var(--muted-foreground)' }}>
                                    Sign In
                                </Link>
                                <Link href="/sign-up"
                                      className="px-6 py-2.5 text-[14px] font-semibold rounded-xl"
                                      style={{
                                          background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
                                          color: '#fff',
                                          boxShadow: '0 4px 16px rgba(98,114,240,0.35)',
                                      }}>
                                    Get Started Free
                                </Link>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            {/* ===== Hero Section ===== */}
            <section className="relative pt-36 pb-24 px-6 text-center overflow-hidden">
                {/* Animated background gradient */}
                <div className="absolute inset-0 pointer-events-none" aria-hidden>
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px] rounded-full opacity-20"
                         style={{ background: 'radial-gradient(ellipse, rgba(98,114,240,0.4) 0%, rgba(240,192,64,0.15) 40%, transparent 70%)', filter: 'blur(80px)' }} />
                    <div className="absolute top-20 right-[10%] w-[300px] h-[300px] rounded-full opacity-15"
                         style={{ background: 'radial-gradient(circle, var(--ghana-gold), transparent 70%)', filter: 'blur(60px)', animation: 'subtle-glow 4s ease-in-out infinite' }} />
                    <div className="absolute top-40 left-[5%] w-[200px] h-[200px] rounded-full opacity-10"
                         style={{ background: 'radial-gradient(circle, var(--ghana-green), transparent 70%)', filter: 'blur(50px)', animation: 'subtle-glow 6s ease-in-out infinite 1s' }} />
                </div>

                <div className="max-w-5xl mx-auto animate-float-in relative z-10">
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2.5 px-5 py-2 rounded-full text-[13px] font-semibold mb-10"
                         style={{
                             background: 'rgba(240,192,64,0.08)',
                             color: 'var(--ghana-gold)',
                             border: '1px solid rgba(240,192,64,0.15)',
                             boxShadow: '0 0 20px rgba(240,192,64,0.08)',
                         }}>
                        <Scale size={14} />
                        <span>Ghana&apos;s Premier AI Legal Research Platform</span>
                    </div>

                    <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-[1.1] mb-8 tracking-tight">
                        Legal Research,{' '}
                        <br className="hidden sm:block" />
                        <span style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817, #f0c040)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Reimagined</span>
                    </h1>

                    <p className="text-lg sm:text-xl lg:text-[22px] max-w-2xl mx-auto mb-12 leading-relaxed"
                       style={{ color: 'var(--muted-foreground)' }}>
                        AI-powered research across thousands of Ghanaian judgments, constitutional provisions, and legal precedents — in seconds, not hours.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href={isSignedIn ? '/chat' : '/sign-up'}
                              className="group px-10 py-4.5 text-[16px] font-semibold rounded-2xl flex items-center gap-2.5"
                              style={{
                                  background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)',
                                  color: '#000',
                                  boxShadow: '0 6px 30px rgba(240,192,64,0.3), 0 2px 8px rgba(240,192,64,0.2)',
                                  transition: 'transform 0.2s, box-shadow 0.2s',
                              }}>
                            {isSignedIn ? 'Open Dashboard' : 'Start Researching — Free'} <ArrowRight size={20} />
                        </Link>
                        <Link href="#pricing"
                              className="px-10 py-4.5 text-[16px] font-medium rounded-2xl flex items-center gap-2.5"
                              style={{
                                  border: '1px solid rgba(255,255,255,0.12)',
                                  color: 'var(--foreground)',
                                  background: 'rgba(255,255,255,0.03)',
                              }}>
                            View Pricing <ChevronRight size={20} />
                        </Link>
                    </div>

                    {/* Trust badges */}
                    <div className="mt-14 flex items-center justify-center gap-6 flex-wrap">
                        {['Supreme Court Cases', 'Court of Appeal', 'High Court Rulings', 'Constitution Analysis'].map(t => (
                            <span key={t} className="text-[12px] font-medium px-3 py-1.5 rounded-full"
                                  style={{ color: 'var(--muted-foreground)', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
                                {t}
                            </span>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Database Stats ===== */}
            <DatabaseStats />

            {/* ===== Features Grid ===== */}
            <section className="py-28 px-6 relative">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-16">
                        <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block" style={{ color: 'var(--ghana-gold)' }}>Capabilities</span>
                        <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">
                            Everything You Need for Legal Research
                        </h2>
                        <p className="text-[17px] max-w-xl mx-auto leading-relaxed"
                           style={{ color: 'var(--muted-foreground)' }}>
                            Three specialized AI experts trained on the full corpus of Ghanaian law.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {FEATURES.map((feature, idx) => {
                            const colors = ['#6272f0', '#f0c040', '#22a05b', '#f06292', '#5b9cf0', '#e54848'];
                            const c = colors[idx % colors.length];
                            return (
                            <div key={feature.title}
                                 className="group p-7 rounded-2xl relative overflow-hidden"
                                 style={{
                                     background: 'var(--surface-1)',
                                     border: '1px solid var(--border)',
                                     transition: 'border-color 0.3s, transform 0.3s, box-shadow 0.3s',
                                 }}
                                 onMouseEnter={(e) => {
                                     e.currentTarget.style.borderColor = `${c}44`;
                                     e.currentTarget.style.transform = 'translateY(-4px)';
                                     e.currentTarget.style.boxShadow = `0 12px 40px ${c}15`;
                                 }}
                                 onMouseLeave={(e) => {
                                     e.currentTarget.style.borderColor = 'var(--border)';
                                     e.currentTarget.style.transform = 'translateY(0)';
                                     e.currentTarget.style.boxShadow = 'none';
                                 }}
                            >
                                <div className="absolute top-0 right-0 w-32 h-32 rounded-full opacity-[0.04] pointer-events-none"
                                     style={{ background: `radial-gradient(circle, ${c}, transparent 70%)`, transform: 'translate(30%, -30%)' }} />
                                <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                                     style={{
                                         background: `${c}15`,
                                         color: c,
                                     }}>
                                    {feature.icon}
                                </div>
                                <h3 className="font-bold text-[17px] mb-2.5">{feature.title}</h3>
                                <p className="text-[15px] leading-relaxed"
                                   style={{ color: 'var(--muted-foreground)' }}>
                                    {feature.description}
                                </p>
                            </div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* ===== Pricing Section ===== */}
            <section id="pricing" className="py-28 px-6 relative">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block" style={{ color: 'var(--primary)' }}>Pricing</span>
                        <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">
                            Simple, Transparent Pricing
                        </h2>
                        <p className="text-[17px] max-w-xl mx-auto leading-relaxed"
                           style={{ color: 'var(--muted-foreground)' }}>
                            Start free, upgrade when you need more. No hidden fees.
                        </p>

                        {/* Billing-cycle toggle */}
                        <div className="inline-flex items-center gap-1 p-1 rounded-full mt-8"
                             style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                            <button
                                onClick={() => setBillingCycle('monthly')}
                                className="px-5 py-2 text-[13px] font-semibold rounded-full transition-colors"
                                style={{
                                    background: billingCycle === 'monthly' ? 'var(--ghana-gold)' : 'transparent',
                                    color: billingCycle === 'monthly' ? '#000' : 'var(--muted-foreground)',
                                }}>
                                Monthly
                            </button>
                            <button
                                onClick={() => setBillingCycle('yearly')}
                                className="px-5 py-2 text-[13px] font-semibold rounded-full flex items-center gap-2 transition-colors"
                                style={{
                                    background: billingCycle === 'yearly' ? 'var(--ghana-gold)' : 'transparent',
                                    color: billingCycle === 'yearly' ? '#000' : 'var(--muted-foreground)',
                                }}>
                                Yearly
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                                      style={{
                                          background: billingCycle === 'yearly' ? 'rgba(0,0,0,0.15)' : 'var(--ghana-green)',
                                          color: billingCycle === 'yearly' ? '#000' : '#fff',
                                      }}>
                                    Save up to 20%
                                </span>
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 max-w-7xl mx-auto">
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
                                        <div className="flex items-center h-[40px]">
                                            <Loader2 size={24} className="animate-spin text-muted-foreground" />
                                        </div>
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

            {/* ===== Testimonials Section ===== */}
            <Testimonials isSignedIn={!!isSignedIn} getToken={getToken} />

            {/* ===== Footer ===== */}
            <footer className="py-14 px-6 relative"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl flex items-center justify-center"
                                 style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)', boxShadow: '0 3px 10px rgba(240,192,64,0.2)' }}>
                                <Scale size={14} className="text-black" />
                            </div>
                            <div>
                                <span className="text-[15px] font-bold block">LexGH</span>
                                <span className="text-[11px]" style={{ color: 'var(--muted-foreground)' }}>AI Legal Research</span>
                            </div>
                        </div>
                        <div className="flex items-center gap-6">
                            <Link href="/chat" className="text-[13px] font-medium" style={{ color: 'var(--muted-foreground)' }}>Research</Link>
                            <Link href="#pricing" className="text-[13px] font-medium" style={{ color: 'var(--muted-foreground)' }}>Pricing</Link>
                            <Link href="/sign-in" className="text-[13px] font-medium" style={{ color: 'var(--muted-foreground)' }}>Sign In</Link>
                        </div>
                        <span className="text-[13px]" style={{ color: 'var(--muted-foreground)', opacity: 0.6 }}>
                            © 2026 EED Soft Consult. All rights reserved.
                        </span>
                    </div>
                </div>
            </footer>
        </div>
    );
}
