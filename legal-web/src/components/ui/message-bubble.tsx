'use client';

import React, { useMemo } from 'react';
import { Scale, FileText, CheckCircle2, AlertTriangle, Ban, BookOpen } from 'lucide-react';
import { LegalExpert } from '@/lib/legal-experts';
import { Source, LegalAnswer, Claim, Citation, ConfidenceTier } from '@/hooks/use-chat';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    expert?: LegalExpert;
    timestamp?: Date;
    sources?: Source[];
    envelope?: LegalAnswer;
}

/* ─── Markdown ────────────────────────────────────────────────────────────── */

function formatMarkdown(text: string): React.ReactNode[] {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let listItems: React.ReactNode[] = [];
    let key = 0;

    const flushList = () => {
        if (listItems.length > 0) {
            elements.push(
                <ul key={`ul-${key++}`} className="space-y-2 my-3 ml-1">
                    {listItems}
                </ul>
            );
            listItems = [];
        }
    };

    const formatInline = (str: string): React.ReactNode => {
        const parts: React.ReactNode[] = [];
        const regex = /(\*\*(.+?)\*\*|`(.+?)`|_(.+?)_)/g;
        let lastIndex = 0;
        let match;

        while ((match = regex.exec(str)) !== null) {
            if (match.index > lastIndex) parts.push(str.slice(lastIndex, match.index));
            if (match[2]) {
                parts.push(
                    <strong key={`b-${match.index}`} className="font-semibold text-foreground">
                        {match[2]}
                    </strong>
                );
            } else if (match[3]) {
                parts.push(
                    <code
                        key={`c-${match.index}`}
                        className="text-[0.85em] px-1.5 py-0.5 rounded-md font-mono bg-muted text-[var(--ghana-gold)]"
                    >
                        {match[3]}
                    </code>
                );
            } else if (match[4]) {
                parts.push(<em key={`i-${match.index}`}>{match[4]}</em>);
            }
            lastIndex = match.index + match[0].length;
        }
        if (lastIndex < str.length) parts.push(str.slice(lastIndex));
        return parts.length === 1 ? parts[0] : <>{parts}</>;
    };

    for (const line of lines) {
        const trimmed = line.trim();

        if (trimmed.startsWith('#### ')) {
            flushList();
            elements.push(
                <h5 key={key++} className="text-[14px] font-semibold mt-4 mb-1.5 tracking-tight text-foreground">
                    {trimmed.slice(5)}
                </h5>
            );
        } else if (trimmed.startsWith('### ')) {
            flushList();
            elements.push(
                <h4 key={key++} className="text-[15px] font-bold mt-5 mb-2 tracking-tight text-foreground">
                    {trimmed.slice(4)}
                </h4>
            );
        } else if (trimmed.startsWith('## ')) {
            flushList();
            elements.push(
                <h3 key={key++} className="text-base font-bold mt-6 mb-2.5 tracking-tight text-foreground">
                    {trimmed.slice(3)}
                </h3>
            );
        } else if (trimmed.startsWith('# ')) {
            flushList();
            elements.push(
                <h2 key={key++} className="text-lg font-bold mt-6 mb-3 tracking-tight text-foreground">
                    {trimmed.slice(2)}
                </h2>
            );
        } else if (/^[-*]\s/.test(trimmed)) {
            listItems.push(
                <li key={`li-${key++}`} className="flex gap-2.5 text-[15px] leading-relaxed">
                    <span className="mt-2 w-1.5 h-1.5 rounded-full flex-shrink-0 bg-primary/60" />
                    <span className="text-foreground/90">{formatInline(trimmed.replace(/^[-*]\s/, ''))}</span>
                </li>
            );
        } else if (/^\d+\.\s/.test(trimmed)) {
            const num = trimmed.match(/^(\d+)\./)?.[1];
            listItems.push(
                <li key={`li-${key++}`} className="flex gap-3 text-[15px] leading-relaxed">
                    <span className="text-[12px] font-bold mt-0.5 w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 bg-[color:color-mix(in_oklch,var(--primary)_15%,transparent)] text-primary">
                        {num}
                    </span>
                    <span className="text-foreground/90">{formatInline(trimmed.replace(/^\d+\.\s/, ''))}</span>
                </li>
            );
        } else if (trimmed === '') {
            flushList();
            elements.push(<div key={key++} className="h-3" />);
        } else {
            flushList();
            elements.push(
                <p key={key++} className="text-[15px] leading-[1.8] mb-1.5 text-foreground/90">
                    {formatInline(trimmed)}
                </p>
            );
        }
    }
    flushList();
    return elements;
}

/* ─── Confidence + Claims ─────────────────────────────────────────────────── */

const TIER_CONFIG: Record<
    ConfidenceTier,
    { variant: 'success' | 'info' | 'warning' | 'destructive'; label: string; Icon: typeof CheckCircle2 }
> = {
    high:         { variant: 'success',     label: 'High confidence', Icon: CheckCircle2 },
    medium:       { variant: 'info',        label: 'Good confidence', Icon: BookOpen },
    low:          { variant: 'warning',     label: 'Low confidence',  Icon: AlertTriangle },
    insufficient: { variant: 'destructive', label: 'Insufficient',    Icon: Ban },
};

const KIND_LABEL: Record<Claim['kind'], string> = {
    direct: 'Direct',
    synthesis: 'Synthesis',
    constitutional: 'Constitutional',
};

function ConfidenceBadge({ tier }: { tier: ConfidenceTier }) {
    const { variant, label, Icon } = TIER_CONFIG[tier];
    return (
        <Badge variant={variant}>
            <Icon className="h-3 w-3" />
            {label}
        </Badge>
    );
}

function CitationChip({ index, citation }: { index: number | string; citation: Citation }) {
    const tooltip = [
        citation.case_title || citation.case_id,
        citation.court,
        citation.year,
        `¶ ${citation.paragraph_id}`,
    ]
        .filter(Boolean)
        .join(' · ');
    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-md text-[11px] font-bold cursor-help bg-[color:color-mix(in_oklch,var(--primary)_15%,transparent)] text-primary">
                    {index}
                </span>
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
                {tooltip}
            </TooltipContent>
        </Tooltip>
    );
}

function ClaimsVerification({ envelope, sources }: { envelope: LegalAnswer; sources?: Source[] }) {
    const sourceIndex = useMemo(() => {
        const map = new Map<string, number>();
        sources?.forEach((s, i) => {
            if (s.case_id && s.paragraph_id) {
                map.set(`${s.case_id}|${s.paragraph_id}`, i + 1);
            }
        });
        return map;
    }, [sources]);

    if (!envelope.claims || envelope.claims.length === 0) return null;

    const total = envelope.claims.length;
    const bound = envelope.claims.filter((c) => c.citations.length > 0).length;

    return (
        <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Verified claims ({bound} / {total} bound)
                </span>
            </div>
            <ul className="space-y-2">
                {envelope.claims.map((claim, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-[13px] leading-relaxed">
                        <CheckCircle2
                            className={`h-3.5 w-3.5 mt-1 flex-shrink-0 ${
                                claim.citations.length > 0 ? 'text-[var(--ghana-green)]' : 'text-muted-foreground'
                            }`}
                        />
                        <div className="flex-1 min-w-0">
                            <span className="text-foreground/85">{claim.text}</span>
                            <span className="ml-2 inline-flex items-center gap-1.5 align-middle">
                                {claim.citations.map((c, j) => (
                                    <CitationChip
                                        key={j}
                                        index={sourceIndex.get(`${c.case_id}|${c.paragraph_id}`) ?? '?'}
                                        citation={c}
                                    />
                                ))}
                                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                                    {KIND_LABEL[claim.kind]}
                                </span>
                            </span>
                        </div>
                    </li>
                ))}
            </ul>
        </div>
    );
}

function LowConfidenceBanner() {
    return (
        <div className="mb-4 px-4 py-3 rounded-lg flex items-start gap-2.5 text-[13px] bg-[color:color-mix(in_oklch,var(--ghana-gold)_10%,transparent)] border border-[color:color-mix(in_oklch,var(--ghana-gold)_30%,transparent)] text-[var(--ghana-gold)]">
            <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <span>
                Some claims couldn&apos;t be fully bound to the retrieved sources. Verify before relying on this answer.
            </span>
        </div>
    );
}

function RefusalCard({
    envelope,
    expert,
    timestamp,
}: {
    envelope: LegalAnswer;
    expert?: LegalExpert;
    timestamp?: Date;
}) {
    const formatTime = (d?: Date) => d?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) || '';
    return (
        <div className="animate-fade-in group">
            <div className="max-w-4xl mx-auto px-5 py-6">
                <div className="flex gap-4">
                    <div className="flex-shrink-0 mt-0.5">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center bg-[color:color-mix(in_oklch,var(--destructive)_12%,transparent)] border-[1.5px] border-[color:color-mix(in_oklch,var(--destructive)_40%,transparent)]">
                            <Ban className="h-4 w-4 text-destructive" />
                        </div>
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2.5 mb-3 flex-wrap">
                            <span className="text-sm font-semibold text-destructive">
                                {expert?.name || 'Legal Expert'}
                            </span>
                            <ConfidenceBadge tier="insufficient" />
                            {timestamp && (
                                <span className="text-[12px] text-muted-foreground">{formatTime(timestamp)}</span>
                            )}
                        </div>
                        <div className="rounded-2xl rounded-tl-md px-5 py-4 bg-[color:color-mix(in_oklch,var(--destructive)_6%,transparent)] border border-[color:color-mix(in_oklch,var(--destructive)_30%,transparent)]">
                            <div className="text-[11px] font-semibold uppercase tracking-wider mb-2.5 text-destructive">
                                No grounded answer available
                            </div>
                            <p className="text-[15px] leading-relaxed text-foreground/90">{envelope.human_text}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function SourcesBadge({ sources }: { sources: Source[] }) {
    const unique = sources.filter((s, i, arr) => {
        const key = (x: Source) => (x.case_id && x.paragraph_id ? `${x.case_id}|${x.paragraph_id}` : x.title);
        return arr.findIndex((x) => key(x) === key(s)) === i;
    });

    if (unique.length === 0) return null;

    return (
        <div className="mt-4 pt-4 border-t border-border">
            <div className="flex items-center gap-2 mb-3">
                <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Sources
                </span>
            </div>
            <div className="flex flex-wrap gap-2">
                {unique.map((src, i) => {
                    const label = src.title || 'Legal Document';
                    const details = [src.court, src.year].filter(Boolean).join(', ');
                    return (
                        <div
                            key={i}
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg text-[12px] bg-muted border border-border hover:border-border/80 transition-colors"
                        >
                            <span className="w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold flex-shrink-0 bg-[color:color-mix(in_oklch,var(--primary)_15%,transparent)] text-primary">
                                {i + 1}
                            </span>
                            <div className="min-w-0">
                                <div className="font-medium truncate max-w-[220px] text-foreground">{label}</div>
                                {details && (
                                    <div className="text-[11px] truncate text-muted-foreground">{details}</div>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

export function MessageBubble({ role, content, expert, timestamp, sources, envelope }: MessageBubbleProps) {
    const isUser = role === 'user';
    const formatted = useMemo(() => (isUser ? null : formatMarkdown(content)), [content, isUser]);

    const formatTime = (date?: Date) => {
        if (!date) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    if (!isUser && envelope?.confidence === 'insufficient') {
        return <RefusalCard envelope={envelope} expert={expert} timestamp={timestamp} />;
    }

    const tier = envelope?.confidence ?? null;

    return (
        <div className="animate-fade-in group">
            <div className="max-w-4xl mx-auto px-5 py-4 sm:px-7">
                {isUser ? (
                    /* User — right-aligned gradient bubble */
                    <div className="flex justify-end">
                        <div className="max-w-[85%]">
                            <div
                                className="px-4 py-3 rounded-2xl rounded-br-md text-white shadow-sm"
                                style={{ background: 'linear-gradient(135deg, var(--primary), #7055d8)' }}
                            >
                                <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{content}</p>
                            </div>
                            {timestamp && (
                                <div className="flex justify-end mt-2 pr-1">
                                    <span className="text-[11px] text-muted-foreground">{formatTime(timestamp)}</span>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    /* Assistant — left-aligned with avatar */
                    <div className="flex gap-3.5">
                        <div className="flex-shrink-0 mt-0.5">
                            <div
                                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs border"
                                style={{
                                    background: expert
                                        ? `linear-gradient(135deg, ${expert.accentColor}30, ${expert.accentColor}70)`
                                        : 'color-mix(in oklch, var(--primary) 15%, transparent)',
                                    borderColor: `${expert?.accentColor || 'var(--primary)'}44`,
                                    boxShadow: `0 2px 8px ${expert?.accentColor || 'var(--primary)'}20`,
                                }}
                            >
                                {expert?.icon || <Scale className="h-4 w-4" />}
                            </div>
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                                <span
                                className="text-[13px] font-medium"
                                    style={{ color: expert?.accentColor || 'var(--primary)' }}
                                >
                                    {expert?.name || 'Legal Expert'}
                                </span>
                                {timestamp && (
                                    <span className="text-[12px] text-muted-foreground">{formatTime(timestamp)}</span>
                                )}
                                {tier && tier !== 'insufficient' && <ConfidenceBadge tier={tier} />}
                            </div>
                            <div className="py-1">
                                {tier === 'low' && <LowConfidenceBanner />}
                                {formatted}
                                {envelope && envelope.claims.length > 0 && (
                                    <ClaimsVerification envelope={envelope} sources={sources} />
                                )}
                                {sources && sources.length > 0 && <SourcesBadge sources={sources} />}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
