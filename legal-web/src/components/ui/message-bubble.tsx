'use client';

import React, { useMemo } from 'react';
import { Scale, FileText } from 'lucide-react';
import { LegalExpert } from '@/lib/legal-experts';
import { Source } from '@/hooks/use-chat';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    expert?: LegalExpert;
    timestamp?: Date;
    sources?: Source[];
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

function SourcesBadge({ sources }: { sources: Source[] }) {
    // Deduplicate by title
    const unique = sources.filter(
        (s, i, arr) => arr.findIndex((x) => x.title === s.title) === i
    );

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

export function MessageBubble({ role, content, expert, timestamp, sources }: MessageBubbleProps) {
    const isUser = role === 'user';
    const formatted = useMemo(() => isUser ? null : formatMarkdown(content), [content, isUser]);

    const formatTime = (date?: Date) => {
        if (!date) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

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
                            <div className="flex items-center gap-2 mb-2">
                                <span className="text-xs font-semibold"
                                      style={{ color: expert?.accentColor || 'var(--primary)' }}>
                                    {expert?.name || 'Legal Expert'}
                                </span>
                                {timestamp && (
                                    <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                        {formatTime(timestamp)}
                                    </span>
                                )}
                            </div>
                            <div className="rounded-2xl rounded-tl-md px-4 py-3.5"
                                 style={{
                                     background: 'var(--surface-1)',
                                     border: '1px solid var(--border)',
                                 }}>
                                {formatted}
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
