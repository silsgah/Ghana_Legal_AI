'use client';

import React from 'react';
import { User } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';

interface MessageBubbleProps {
    role: 'user' | 'assistant';
    content: string;
    expert?: LegalExpert;
    timestamp?: Date;
}

export function MessageBubble({ role, content, expert, timestamp }: MessageBubbleProps) {
    const isUser = role === 'user';

    const formatTime = (date?: Date) => {
        if (!date) return '';
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div
            className="animate-fade-in"
            style={{
                padding: '1.5rem 1.75rem',
                background: isUser ? 'var(--surface-0)' : 'var(--surface-1)',
                borderBottom: '1px solid var(--border)',
            }}
        >
            <div className="max-w-3xl mx-auto flex gap-4 w-full">
                {/* Avatar */}
                <div className="flex-shrink-0 pt-0.5">
                    {isUser ? (
                        <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                             style={{ background: 'var(--surface-3)' }}>
                            <User size={16} style={{ color: 'var(--muted-foreground)' }} />
                        </div>
                    ) : (
                        <div
                            className="w-8 h-8 rounded-lg flex items-center justify-center text-sm shadow-sm"
                            style={{
                                background: expert
                                    ? `linear-gradient(135deg, ${expert.accentColor}66, ${expert.accentColor})`
                                    : 'linear-gradient(135deg, var(--primary), #8b5cf6)',
                            }}
                        >
                            {expert?.icon || '⚖️'}
                        </div>
                    )}
                </div>

                {/* Message Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 mb-1">
                        <span className="font-semibold text-[13px]"
                              style={{ color: isUser ? 'var(--foreground)' : expert?.accentColor || 'var(--primary)' }}>
                            {isUser ? 'You' : expert?.name || 'Legal Expert'}
                        </span>
                        {timestamp && (
                            <span className="text-[11px]" style={{ color: 'var(--muted-foreground)' }}>
                                {formatTime(timestamp)}
                            </span>
                        )}
                    </div>
                    <div className="prose-chat whitespace-pre-wrap leading-relaxed"
                         style={{ color: 'var(--foreground)', opacity: isUser ? 0.9 : 1 }}>
                        {content}
                    </div>
                </div>
            </div>
        </div>
    );
}
