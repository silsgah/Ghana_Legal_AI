'use client';

import React, { useEffect, useState } from 'react';
import { config } from '@/lib/config';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@clerk/nextjs';
import {
    Scale, Shield, Zap, BookOpen, Users, ArrowRight,
    Check, ChevronRight, Gavel, ScrollText, Database, Loader2
} from 'lucide-react';
import { usePricing } from '@/hooks/use-pricing';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

const FEATURES = [
    {
        icon: <BookOpen size={24} />,
        title: 'Constitutional Analysis',
        description: 'Deep analysis of the 1992 Constitution, amendments, and their real-world implications for practice.',
        accent: 'var(--ghana-gold)',
    },
    {
        icon: <Gavel size={24} />,
        title: 'Case Law Research',
        description: 'Instantly search and summarize Supreme Court and Court of Appeal judgments with citations.',
        accent: 'var(--ghana-green)',
    },
    {
        icon: <ScrollText size={24} />,
        title: 'Legal History',
        description: 'Trace the evolution of Ghanaian law from customary traditions to modern statutes.',
        accent: 'var(--ghana-gold)',
    },
    {
        icon: <Zap size={24} />,
        title: 'Instant Answers',
        description: 'AI-powered responses grounded in real case law, delivered in seconds — not hours.',
        accent: 'var(--primary)',
    },
    {
        icon: <Shield size={24} />,
        title: 'Verified Sources',
        description: 'Every answer is linked to retrieved case law and constitutional provisions with citation chips.',
        accent: 'var(--ghana-green)',
    },
    {
        icon: <Users size={24} />,
        title: 'Built for Professionals',
        description: 'Designed for lawyers, judges, law students, and corporate legal teams across Ghana.',
        accent: 'var(--ghana-gold)',
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
            <Card className="glass p-8 lg:p-10 border-[color:color-mix(in_oklch,var(--ghana-gold)_15%,var(--border))]">
                <div className="flex items-center justify-between gap-4 mb-8 pb-6 border-b border-border/60">
                    <div className="flex items-center gap-4 min-w-0">
                        <div className="w-14 h-14 rounded-2xl flex items-center justify-center shrink-0 bg-[color:color-mix(in_oklch,var(--ghana-gold)_10%,transparent)] border border-[color:color-mix(in_oklch,var(--ghana-gold)_18%,transparent)]">
                            <Database size={24} className="text-[var(--ghana-gold)]" />
                        </div>
                        <div className="min-w-0">
                            <div className="text-[12px] font-bold uppercase tracking-widest mb-1 text-[var(--ghana-gold)]/80">
                                Live Database
                            </div>
                            <div className="text-[15px] text-muted-foreground">
                                Judgments indexed across Ghanaian courts
                            </div>
                        </div>
                    </div>
                    <div className="text-right shrink-0">
                        <div className="text-4xl sm:text-5xl font-extrabold tabular-nums text-gradient-gold leading-none">
                            {stats.total_cases.toLocaleString()}
                        </div>
                        <div className="text-[12px] font-semibold uppercase tracking-wider mt-1.5 text-muted-foreground">
                            Total Cases
                        </div>
                    </div>
                </div>

                <div className="space-y-4">
                    {filteredCourts.map(({ id, label, value }) => {
                        const pct = total > 0 ? (value / total) * 100 : 0;
                        const barWidth = (value / max) * 100;
                        return (
                            <div key={id} className="min-w-0">
                                <div className="flex items-baseline justify-between gap-3 mb-2 min-w-0">
                                    <span className="text-[15px] font-medium truncate text-foreground" title={label}>
                                        {label}
                                    </span>
                                    <div className="flex items-baseline gap-2.5 shrink-0">
                                        <span className="text-[12px] font-mono tabular-nums text-muted-foreground">
                                            {pct.toFixed(1)}%
                                        </span>
                                        <span className="text-[15px] font-mono font-bold tabular-nums text-[var(--ghana-gold)]">
                                            {value.toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                                <div className="h-2.5 rounded-full overflow-hidden bg-muted">
                                    <div
                                        className="h-full rounded-full transition-all duration-700"
                                        style={{
                                            width: `${barWidth}%`,
                                            background: 'linear-gradient(90deg, var(--ghana-gold), #d4a017)',
                                            boxShadow: '0 0 12px rgba(240,192,64,0.3)',
                                        }}
                                    />
                                </div>
                            </div>
                        );
                    })}
                </div>
            </Card>
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
                fetchFeedbacks();
            } else {
                setFeedbackMessage('Failed to submit feedback.');
            }
        } catch {
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
                    <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block text-[var(--ghana-green)]">
                        Testimonials
                    </span>
                    <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">What Our Users Say</h2>
                    <p className="text-[17px] max-w-xl mx-auto leading-relaxed text-muted-foreground">
                        Feedback from legal professionals using LexGH.
                    </p>
                </div>

                {feedbacks.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-12">
                        {feedbacks.map(f => (
                            <Card
                                key={f.id}
                                className="p-7 flex flex-col relative overflow-hidden transition-all hover:-translate-y-0.5 hover:border-[color:color-mix(in_oklch,var(--ghana-gold)_30%,var(--border))]"
                            >
                                <div
                                    className="absolute top-4 right-6 text-[48px] font-serif leading-none pointer-events-none text-[var(--ghana-gold)]/10"
                                    aria-hidden
                                >
                                    ”
                                </div>
                                <div className="flex items-center gap-3.5 mb-5">
                                    <div className="w-11 h-11 rounded-full flex items-center justify-center font-bold text-[15px] bg-[color:color-mix(in_oklch,var(--ghana-gold)_12%,transparent)] text-[var(--ghana-gold)] border border-[color:color-mix(in_oklch,var(--ghana-gold)_20%,transparent)]">
                                        {f.name.charAt(0).toUpperCase()}
                                    </div>
                                    <div>
                                        <div className="font-semibold text-[15px]">{f.name}</div>
                                        <div className="text-[12px] text-muted-foreground">
                                            {new Date(f.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                </div>
                                <p className="text-[15px] italic leading-relaxed flex-1 text-muted-foreground">
                                    &ldquo;{f.content}&rdquo;
                                </p>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <div className="text-center mb-12 text-[15px] text-muted-foreground">
                        No feedback yet. Be the first!
                    </div>
                )}

                {isSignedIn && (
                    <div className="max-w-lg mx-auto text-center">
                        {!showForm ? (
                            <Button variant="outline" size="lg" onClick={() => setShowForm(true)}>
                                Leave Feedback
                            </Button>
                        ) : (
                            <Card className="text-left p-6 animate-fade-in">
                                <h3 className="font-bold mb-4">Submit Feedback</h3>
                                <form onSubmit={handleSubmit}>
                                    <div className="mb-4 space-y-1.5">
                                        <Label htmlFor="feedback-name">Display Name</Label>
                                        <Input
                                            id="feedback-name"
                                            required
                                            type="text"
                                            value={name}
                                            onChange={e => setName(e.target.value)}
                                        />
                                    </div>
                                    <div className="mb-4 space-y-1.5">
                                        <Label htmlFor="feedback-content">Feedback</Label>
                                        <Textarea
                                            id="feedback-content"
                                            required
                                            rows={4}
                                            value={content}
                                            onChange={e => setContent(e.target.value)}
                                            className="resize-none"
                                        />
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                                            Cancel
                                        </Button>
                                        <Button type="submit" variant="gold" disabled={submitting}>
                                            {submitting ? 'Submitting...' : 'Submit'}
                                        </Button>
                                    </div>
                                </form>
                            </Card>
                        )}
                        {feedbackMessage && (
                            <p className="mt-4 text-sm font-medium animate-fade-in text-[var(--ghana-green)]">
                                {feedbackMessage}
                            </p>
                        )}
                    </div>
                )}
            </div>
        </section>
    );
}

export default function LandingPage() {
    const router = useRouter();
    const { isSignedIn, getToken } = useAuth();
    const { pricing, loading: pricingLoading } = usePricing();
    const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly');

    // Signed-in users should enter their research workspace immediately.
    useEffect(() => {
        if (isSignedIn) router.replace('/chat');
    }, [isSignedIn, router]);

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
        <div className="min-h-screen bg-background text-foreground">

            {/* ===== Navigation ===== */}
            <nav className="fixed top-0 w-full z-50 glass border-b border-border/60">
                <div className="max-w-7xl mx-auto px-6 h-[72px] flex items-center justify-between">
                    <Link href="/" className="flex items-center gap-3 group">
                        <div
                            className="w-10 h-10 rounded-xl flex items-center justify-center transition-transform group-hover:scale-105"
                            style={{
                                background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)',
                                boxShadow: '0 4px 12px rgba(240,192,64,0.3)',
                            }}
                        >
                            <Scale size={18} className="text-black" />
                        </div>
                        <div>
                            <span className="font-bold text-[17px] block leading-tight">LexGH</span>
                            <span className="text-[11px] font-medium text-[var(--ghana-gold)]/80">Legal Research</span>
                        </div>
                    </Link>
                    <div className="flex items-center gap-3">
                        {isSignedIn ? (
                            <Button asChild variant="gold" size="lg">
                                <Link href="/chat">Go to Dashboard</Link>
                            </Button>
                        ) : (
                            <>
                                <Button asChild variant="ghost" size="lg" className="hidden sm:inline-flex">
                                    <Link href="/sign-in">Sign In</Link>
                                </Button>
                                <Button asChild variant="gold" size="lg">
                                    <Link href="/sign-up">Get Started Free</Link>
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            </nav>

            {/* ===== Hero ===== */}
            <section className="relative pt-36 pb-24 px-6 text-center overflow-hidden">
                <div className="absolute inset-0 pointer-events-none" aria-hidden>
                    <div
                        className="absolute top-0 left-1/2 -translate-x-1/2 w-[900px] h-[600px] rounded-full opacity-25"
                        style={{
                            background: 'radial-gradient(ellipse, rgba(240,192,64,0.35) 0%, rgba(34,160,91,0.15) 40%, transparent 70%)',
                            filter: 'blur(80px)',
                        }}
                    />
                    <div
                        className="absolute top-20 right-[10%] w-[300px] h-[300px] rounded-full opacity-20"
                        style={{
                            background: 'radial-gradient(circle, var(--ghana-gold), transparent 70%)',
                            filter: 'blur(60px)',
                        }}
                    />
                    <div
                        className="absolute top-40 left-[5%] w-[200px] h-[200px] rounded-full opacity-15"
                        style={{
                            background: 'radial-gradient(circle, var(--ghana-green), transparent 70%)',
                            filter: 'blur(50px)',
                        }}
                    />
                </div>

                <div className="max-w-5xl mx-auto animate-float-in relative z-10">
                    <Badge variant="gold" className="mb-10 px-5 py-2 text-[13px]">
                        <Scale size={14} />
                        <span>Ghana&apos;s Premier AI Legal Research Platform</span>
                    </Badge>

                    <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-[1.1] mb-8 tracking-tight">
                        Legal Research,{' '}
                        <br className="hidden sm:block" />
                        <span className="text-gradient-gold">Reimagined</span>
                    </h1>

                    <p className="text-lg sm:text-xl lg:text-[22px] max-w-2xl mx-auto mb-12 leading-relaxed text-muted-foreground">
                        AI-powered research across thousands of Ghanaian judgments, constitutional provisions, and legal precedents — in seconds, not hours.
                    </p>

                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Button asChild variant="gold" size="xl" className="px-10">
                            <Link href={isSignedIn ? '/chat' : '/sign-up'}>
                                {isSignedIn ? 'Open Dashboard' : 'Start Researching — Free'}
                                <ArrowRight size={20} />
                            </Link>
                        </Button>
                        <Button asChild variant="outline" size="xl" className="px-10">
                            <Link href="#pricing">
                                View Pricing <ChevronRight size={20} />
                            </Link>
                        </Button>
                    </div>

                    <div className="mt-14 flex items-center justify-center gap-2.5 flex-wrap">
                        {['Supreme Court Cases', 'Court of Appeal', 'High Court Rulings', 'Constitution Analysis'].map(t => (
                            <Badge key={t} variant="outline" className="text-muted-foreground normal-case tracking-normal font-medium">
                                {t}
                            </Badge>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Database Stats ===== */}
            <DatabaseStats />

            {/* ===== Features ===== */}
            <section className="py-28 px-6 relative">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-16">
                        <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block text-[var(--ghana-gold)]">
                            Capabilities
                        </span>
                        <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">
                            Everything You Need for Legal Research
                        </h2>
                        <p className="text-[17px] max-w-xl mx-auto leading-relaxed text-muted-foreground">
                            Three specialized AI experts trained on the full corpus of Ghanaian law.
                        </p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {FEATURES.map((feature) => (
                            <Card
                                key={feature.title}
                                className="group p-7 relative overflow-hidden transition-all hover:-translate-y-1 hover:shadow-lg"
                                style={{
                                    ['--feature-accent' as string]: feature.accent,
                                }}
                            >
                                <div
                                    className="absolute top-0 right-0 w-32 h-32 rounded-full opacity-[0.05] pointer-events-none"
                                    style={{
                                        background: `radial-gradient(circle, ${feature.accent}, transparent 70%)`,
                                        transform: 'translate(30%, -30%)',
                                    }}
                                />
                                <div
                                    className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                                    style={{
                                        background: `color-mix(in oklch, ${feature.accent} 14%, transparent)`,
                                        color: feature.accent,
                                    }}
                                >
                                    {feature.icon}
                                </div>
                                <h3 className="font-bold text-[17px] mb-2.5">{feature.title}</h3>
                                <p className="text-[15px] leading-relaxed text-muted-foreground">
                                    {feature.description}
                                </p>
                            </Card>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Pricing ===== */}
            <section id="pricing" className="py-28 px-6 relative scroll-mt-24">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-16">
                        <span className="text-[12px] font-bold uppercase tracking-[0.2em] mb-4 block text-[var(--ghana-green)]">
                            Pricing
                        </span>
                        <h2 className="text-3xl sm:text-4xl font-bold mb-5 tracking-tight">
                            Simple, Transparent Pricing
                        </h2>
                        <p className="text-[17px] max-w-xl mx-auto leading-relaxed text-muted-foreground">
                            Start free, upgrade when you need more. No hidden fees.
                        </p>

                        {/* Billing-cycle toggle */}
                        <div className="inline-flex items-center gap-1 p-1 rounded-full mt-8 bg-card border border-border">
                            <button
                                onClick={() => setBillingCycle('monthly')}
                                className={`px-5 py-2 text-[13px] font-semibold rounded-full transition-colors ${
                                    billingCycle === 'monthly'
                                        ? 'bg-[var(--ghana-gold)] text-black'
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                Monthly
                            </button>
                            <button
                                onClick={() => setBillingCycle('yearly')}
                                className={`px-5 py-2 text-[13px] font-semibold rounded-full flex items-center gap-2 transition-colors ${
                                    billingCycle === 'yearly'
                                        ? 'bg-[var(--ghana-gold)] text-black'
                                        : 'text-muted-foreground hover:text-foreground'
                                }`}
                            >
                                Yearly
                                <span
                                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                        billingCycle === 'yearly'
                                            ? 'bg-black/15 text-black'
                                            : 'bg-[var(--ghana-green)] text-white'
                                    }`}
                                >
                                    Save up to 20%
                                </span>
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6 max-w-7xl mx-auto">
                        {PRICING_TIERS.map((tier) => (
                            <Card
                                key={tier.name}
                                className={`relative p-7 flex flex-col transition-all ${
                                    tier.highlighted
                                        ? 'border-2 border-[var(--ghana-gold)] bg-muted shadow-[0_8px_32px_rgba(240,192,64,0.12)]'
                                        : 'hover:-translate-y-0.5 hover:border-border/80'
                                }`}
                            >
                                {tier.highlighted && (
                                    <Badge
                                        variant="default"
                                        className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[var(--ghana-gold)] text-black border-transparent"
                                    >
                                        Most Popular
                                    </Badge>
                                )}

                                <h3 className="text-lg font-bold mb-1">{tier.name}</h3>
                                <p className="text-sm mb-5 text-muted-foreground">
                                    {tier.description}
                                </p>

                                <div className="flex items-baseline gap-1 mb-6 min-h-[40px]">
                                    {tier.currency && (
                                        <span className="text-sm font-medium text-muted-foreground">
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
                                        <span className="text-sm text-muted-foreground">
                                            {tier.period}
                                        </span>
                                    )}
                                </div>

                                <ul className="space-y-3 mb-8 flex-1">
                                    {tier.features.map((feature) => (
                                        <li key={feature} className="flex items-start gap-3 text-sm">
                                            <Check
                                                size={16}
                                                className="flex-shrink-0 mt-0.5"
                                                style={{ color: tier.accentColor }}
                                            />
                                            <span>{feature}</span>
                                        </li>
                                    ))}
                                </ul>

                                <Button
                                    asChild
                                    variant={tier.highlighted ? 'gold' : 'secondary'}
                                    className="w-full"
                                    size="lg"
                                >
                                    <Link href={tier.href}>{tier.cta}</Link>
                                </Button>
                            </Card>
                        ))}
                    </div>
                </div>
            </section>

            {/* ===== Testimonials ===== */}
            <Testimonials isSignedIn={!!isSignedIn} getToken={getToken} />

            {/* ===== Footer ===== */}
            <footer className="py-14 px-6 relative border-t border-border/60">
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <div
                                className="w-9 h-9 rounded-xl flex items-center justify-center"
                                style={{
                                    background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)',
                                    boxShadow: '0 3px 10px rgba(240,192,64,0.2)',
                                }}
                            >
                                <Scale size={14} className="text-black" />
                            </div>
                            <div>
                                <span className="text-[15px] font-bold block">LexGH</span>
                                <span className="text-[11px] text-muted-foreground">AI Legal Research</span>
                            </div>
                        </div>
                        <div className="flex items-center gap-6">
                            <Link href="/chat" className="text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors">Research</Link>
                            <Link href="#pricing" className="text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors">Pricing</Link>
                            <Link href="/sign-in" className="text-[13px] font-medium text-muted-foreground hover:text-foreground transition-colors">Sign In</Link>
                        </div>
                        <span className="text-[13px] text-muted-foreground/70">
                            © 2026 EED Soft Consult. All rights reserved.
                        </span>
                    </div>
                </div>
            </footer>
        </div>
    );
}
