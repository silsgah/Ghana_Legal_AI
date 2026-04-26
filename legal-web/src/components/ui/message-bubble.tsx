'use client';

import React, { useMemo } from 'react';
import { Scale, FileText, CheckCircle2, AlertTriangle, Ban, BookOpen } from 'lucide-react';
import { LegalExpert } from '@/lib/legal-experts';
import { Source, LegalAnswer, Claim, Citation, ConfidenceTier } from '@/hooks/use-chat';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    expert?: LegalExpert;
    timestamp?: Date;
    sources?: Source[];
    envelope?: LegalAnswer;
}

function formatMarkdown(text: string): React.ReactNode[] {
    const lines = text.split('\n');
    const elements: React.ReactNode[] = [];
    let inList = false;
    let listItems: React.ReactNode[] = [];
    let key = 0;

    const flushList = () => {
        if (listItems.length > 0) {
            elements.push(<ul key={`ul-${key++}`} className="space-y-1.5 my-3 ml-1">{listItems}</ul>);
            listItems = [];
            inList = false;
        }
    };

    const formatInline = (str: string): React.ReactNode => {
        const parts: React.ReactNode[] = [];
        const regex = /(\*\*(.+?)\*\*|`(.+?)`|_(.+?)_)/g;
        let lastIndex = 0;
        let match;

        while ((match = regex.exec(str)) !== null) {
            if (match.index > lastIndex) {
                parts.push(str.slice(lastIndex, match.index));
            }
            if (match[2]) {
                parts.push(<strong key={`b-${match.index}`} className="font-semibold" style={{ color: 'var(--foreground)' }}>{match[2]}</strong>);
            } else if (match[3]) {
                parts.push(
                    <code key={`c-${match.index}`}
                          className="text-[0.85em] px-1.5 py-0.5 rounded-md font-mono"
                          style={{ background: 'var(--surface-3)', color: 'var(--ghana-gold)' }}>
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

        // Headings
        if (trimmed.startsWith('### ')) {
            flushList();
            elements.push(
                <h4 key={key++} className="text-sm font-bold mt-4 mb-1.5 tracking-tight"
                    style={{ color: 'var(--foreground)' }}>
                    {trimmed.slice(4)}
                </h4>
            );
        } else if (trimmed.startsWith('## ')) {
            flushList();
            elements.push(
                <h3 key={key++} className="text-[15px] font-bold mt-5 mb-2 tracking-tight"
                    style={{ color: 'var(--foreground)' }}>
                    {trimmed.slice(3)}
                </h3>
            );
        }
        // Bullet list
        else if (/^[-*]\s/.test(trimmed)) {
            inList = true;
            listItems.push(
                <li key={`li-${key++}`} className="flex gap-2 text-sm leading-relaxed">
                    <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0"
                          style={{ background: 'var(--primary)', opacity: 0.6 }} />
                    <span style={{ color: 'var(--foreground)', opacity: 0.92 }}>
                        {formatInline(trimmed.replace(/^[-*]\s/, ''))}
                    </span>
                </li>
            );
        }
        // Numbered list
        else if (/^\d+\.\s/.test(trimmed)) {
            inList = true;
            const num = trimmed.match(/^(\d+)\./)?.[1];
            listItems.push(
                <li key={`li-${key++}`} className="flex gap-2.5 text-sm leading-relaxed">
                    <span className="text-xs font-bold mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0"
                          style={{ background: 'var(--primary-muted)', color: 'var(--primary)' }}>
                        {num}
                    </span>
                    <span style={{ color: 'var(--foreground)', opacity: 0.92 }}>
                        {formatInline(trimmed.replace(/^\d+\.\s/, ''))}
                    </span>
                </li>
            );
        }
        // Empty line
        else if (trimmed === '') {
            flushList();
            elements.push(<div key={key++} className="h-2" />);
        }
        // Regular paragraph
        else {
            flushList();
            elements.push(
                <p key={key++} className="text-sm leading-[1.75] mb-1"
                   style={{ color: 'var(--foreground)', opacity: 0.92 }}>
                    {formatInline(trimmed)}
                </p>
            );
        }
    }
    flushList();
    return elements;
}

// ─── Confidence + Claims rendering (PR 5: grounded-citation UI) ─────────────
//
// A lawyer reading legal-AI output needs three things at a glance:
//   (1) how grounded is this answer (confidence badge)
//   (2) which retrieved source backs each individual claim (numbered chips)
//   (3) a clear refusal when the model couldn't ground anything (refusal card)
//
// All three derive from the LegalAnswer envelope produced by the server-side
// validator. When the envelope is absent (cached pre-PR2 answers, or the
// no-retrieval branch), we fall back to plain markdown rendering.

const TIER_STYLE: Record<ConfidenceTier, { bg: string; fg: string; label: string }> = {
    high:         { bg: '#16a34a22', fg: '#16a34a', label: 'High confidence' },
    medium:       { bg: '#2563eb22', fg: '#2563eb', label: 'Synthesis' },
    low:          { bg: '#f59e0b22', fg: '#b45309', label: 'Low confidence' },
    insufficient: { bg: '#dc262622', fg: '#dc2626', label: 'Insufficient' },
};

const KIND_LABEL: Record<Claim['kind'], string> = {
    direct: 'Direct',
    synthesis: 'Synthesis',
    constitutional: 'Constitutional',
};

function ConfidenceBadge({ tier }: { tier: ConfidenceTier }) {
    const s = TIER_STYLE[tier];
    const Icon = tier === 'high' ? CheckCircle2 : tier === 'low' ? AlertTriangle : tier === 'insufficient' ? Ban : BookOpen;
    return (
        <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider"
            style={{ background: s.bg, color: s.fg }}
            title={`Validator confidence: ${tier}`}
        >
            <Icon size={11} />
            {s.label}
        </span>
    );
}

function CitationChip({ index, citation }: { index: number | string; citation: Citation }) {
    const tooltip = [
        citation.case_title || citation.case_id,
        citation.court,
        citation.year,
        `¶ ${citation.paragraph_id}`,
    ].filter(Boolean).join(' · ');
    return (
        <span
            className="inline-flex items-center justify-center w-5 h-5 rounded-md text-[10px] font-bold cursor-help"
            style={{ background: 'var(--primary-muted)', color: 'var(--primary)' }}
            title={tooltip}
        >
            {index}
        </span>
    );
}

function ClaimsVerification({ envelope, sources }: { envelope: LegalAnswer; sources?: Source[] }) {
    // Map (case_id, paragraph_id) → 1-based source index so each citation
    // chip lines up with the numbered Sources list at the bottom.
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
    const bound = envelope.claims.filter(c => c.citations.length > 0).length;

    return (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="flex items-center gap-1.5 mb-2">
                <CheckCircle2 size={11} style={{ color: 'var(--muted-foreground)' }} />
                <span className="text-[10px] font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--muted-foreground)' }}>
                    Verified claims ({bound} / {total} bound)
                </span>
            </div>
            <ul className="space-y-1.5">
                {envelope.claims.map((claim, i) => (
                    <li key={i} className="flex items-start gap-2 text-[12px] leading-relaxed">
                        <CheckCircle2 size={12} className="mt-1 flex-shrink-0"
                                      style={{ color: claim.citations.length > 0 ? '#16a34a' : 'var(--muted-foreground)' }} />
                        <div className="flex-1 min-w-0">
                            <span style={{ color: 'var(--foreground)', opacity: 0.85 }}>
                                {claim.text}
                            </span>
                            <span className="ml-1.5 inline-flex items-center gap-1 align-middle">
                                {claim.citations.map((c, j) => (
                                    <CitationChip
                                        key={j}
                                        index={sourceIndex.get(`${c.case_id}|${c.paragraph_id}`) ?? '?'}
                                        citation={c}
                                    />
                                ))}
                                <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded"
                                      style={{ background: 'var(--surface-3)', color: 'var(--muted-foreground)' }}>
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
        <div className="mb-3 px-3 py-2 rounded-lg flex items-start gap-2 text-[11px]"
             style={{ background: '#f59e0b15', border: '1px solid #f59e0b40', color: '#92400e' }}>
            <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />
            <span>
                Some claims couldn&apos;t be fully bound to the retrieved sources.
                Verify before relying on this answer.
            </span>
        </div>
    );
}

function RefusalCard({ envelope, expert, timestamp }: {
    envelope: LegalAnswer;
    expert?: LegalExpert;
    timestamp?: Date;
}) {
    const formatTime = (d?: Date) => d?.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) || '';
    return (
        <div className="animate-fade-in group">
            <div className="max-w-3xl mx-auto px-5 py-5">
                <div className="flex gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                             style={{ background: '#dc262622', border: '1.5px solid #dc262644' }}>
                            <Ban size={14} style={{ color: '#dc2626' }} />
                        </div>
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold" style={{ color: '#dc2626' }}>
                                {expert?.name || 'Legal Expert'}
                            </span>
                            <ConfidenceBadge tier="insufficient" />
                            {timestamp && (
                                <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                    {formatTime(timestamp)}
                                </span>
                            )}
                        </div>
                        <div className="rounded-2xl rounded-tl-md px-4 py-3.5"
                             style={{ background: '#dc26260a', border: '1px solid #dc262640' }}>
                            <div className="text-[11px] font-semibold uppercase tracking-wider mb-2"
                                 style={{ color: '#dc2626' }}>
                                No grounded answer available
                            </div>
                            <p className="text-sm leading-relaxed" style={{ color: 'var(--foreground)', opacity: 0.92 }}>
                                {envelope.human_text}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}


function SourcesBadge({ sources }: { sources: Source[] }) {
    // Dedup key: (case_id, paragraph_id) when present (post-PR1), else title.
    // This keeps the badge index in lockstep with the CitationChip lookup so a
    // chip showing [2] always points to the same item the lawyer sees as #2 below.
    const unique = sources.filter((s, i, arr) => {
        const key = (x: Source) => x.case_id && x.paragraph_id ? `${x.case_id}|${x.paragraph_id}` : x.title;
        return arr.findIndex((x) => key(x) === key(s)) === i;
    });

    if (unique.length === 0) return null;

    return (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border)' }}>
            <div className="flex items-center gap-1.5 mb-2">
                <FileText size={11} style={{ color: 'var(--muted-foreground)' }} />
                <span className="text-[10px] font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--muted-foreground)' }}>
                    Sources
                </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
                {unique.map((src, i) => {
                    const label = src.title || 'Legal Document';
                    const details = [src.court, src.year].filter(Boolean).join(', ');
                    return (
                        <div key={i}
                             className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px]"
                             style={{
                                 background: 'var(--surface-2)',
                                 border: '1px solid var(--border)',
                             }}>
                            <span className="w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                                  style={{ background: 'var(--primary-muted)', color: 'var(--primary)' }}>
                                {i + 1}
                            </span>
                            <div className="min-w-0">
                                <div className="font-medium truncate max-w-[200px]"
                                     style={{ color: 'var(--foreground)' }}>
                                    {label}
                                </div>
                                {details && (
                                    <div className="text-[10px] truncate"
                                         style={{ color: 'var(--muted-foreground)' }}>
                                        {details}
                                    </div>
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
    const formatted = useMemo(() => isUser ? null : formatMarkdown(content), [content, isUser]);

    const formatTime = (date?: Date) => {
        if (!date) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    // Insufficient-confidence answers swap out the entire bubble for a refusal
    // card so a lawyer cannot mistake a fallback for a normal grounded reply.
    if (!isUser && envelope?.confidence === 'insufficient') {
        return <RefusalCard envelope={envelope} expert={expert} timestamp={timestamp} />;
    }

    const tier = envelope?.confidence ?? null;

    return (
        <div className="animate-fade-in group" style={{ background: 'transparent' }}>
            <div className="max-w-3xl mx-auto px-5 py-5">
                {isUser ? (
                    /* User message — right-aligned bubble */
                    <div className="flex justify-end">
                        <div className="max-w-[85%]">
                            <div className="px-4 py-3 rounded-2xl rounded-br-md"
                                 style={{
                                     background: 'var(--primary)',
                                     color: '#fff',
                                 }}>
                                <p className="text-sm leading-relaxed whitespace-pre-wrap">{content}</p>
                            </div>
                            {timestamp && (
                                <div className="flex justify-end mt-1.5 pr-1">
                                    <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                        {formatTime(timestamp)}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                ) : (
                    /* Assistant message — left-aligned with avatar */
                    <div className="flex gap-3">
                        <div className="flex-shrink-0 mt-0.5">
                            <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                                 style={{
                                     background: expert
                                         ? `linear-gradient(135deg, ${expert.accentColor}33, ${expert.accentColor}88)`
                                         : 'var(--primary-muted)',
                                     border: `1.5px solid ${expert?.accentColor || 'var(--primary)'}44`,
                                 }}>
                                {expert?.icon || <Scale size={14} />}
                            </div>
                        </div>
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-2 flex-wrap">
                                <span className="text-xs font-semibold"
                                      style={{ color: expert?.accentColor || 'var(--primary)' }}>
                                    {expert?.name || 'Legal Expert'}
                                </span>
                                {timestamp && (
                                    <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                        {formatTime(timestamp)}
                                    </span>
                                )}
                                {tier && tier !== 'insufficient' && <ConfidenceBadge tier={tier} />}
                            </div>
                            <div className="rounded-2xl rounded-tl-md px-4 py-3.5"
                                 style={{
                                     background: 'var(--surface-1)',
                                     border: '1px solid var(--border)',
                                 }}>
                                {tier === 'low' && <LowConfidenceBanner />}
                                {formatted}
                                {envelope && envelope.claims.length > 0 && (
                                    <ClaimsVerification envelope={envelope} sources={sources} />
                                )}
                                {sources && sources.length > 0 && (
                                    <SourcesBadge sources={sources} />
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
