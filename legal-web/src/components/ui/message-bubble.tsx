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
            className={cn(
                'flex w-full p-6 animate-fade-in',
                isUser ? 'bg-white dark:bg-zinc-900' : 'bg-zinc-50 dark:bg-zinc-800/50'
            )}
        >
            <div className="max-w-3xl mx-auto flex gap-5 w-full">
                {/* Avatar */}
                <div className="flex-shrink-0">
                    {isUser ? (
                        <div className="w-9 h-9 rounded-full bg-zinc-200 dark:bg-zinc-700 flex items-center justify-center">
                            <User size={18} className="text-zinc-600 dark:text-zinc-300" />
                        </div>
                    ) : (
                        <div
                            className="w-9 h-9 rounded-full flex items-center justify-center text-white font-semibold text-sm shadow-md"
                            style={{
                                background: expert
                                    ? `linear-gradient(135deg, ${expert.accentColor}88, ${expert.accentColor})`
                                    : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            }}
                        >
                            {expert?.icon || expert?.name.charAt(0) || 'E'}
                        </div>
                    )}
                </div>

                {/* Message Content */}
                <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2 mb-1.5">
                        <span className="font-semibold text-zinc-900 dark:text-zinc-100">
                            {isUser ? 'You' : expert?.name || 'Legal Expert'}
                        </span>
                        {timestamp && (
                            <span className="text-xs text-zinc-400">{formatTime(timestamp)}</span>
                        )}
                    </div>
                    <div className="prose-chat text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap leading-relaxed">
                        {content}
                    </div>
                </div>
            </div>
        </div>
    );
}
