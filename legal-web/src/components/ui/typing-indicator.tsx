'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface TypingIndicatorProps {
    expertName?: string;
    accentColor?: string;
}

export function TypingIndicator({ expertName, accentColor = '#6366f1' }: TypingIndicatorProps) {
    return (
        <div className="flex w-full p-6 bg-zinc-50 dark:bg-zinc-800/50 animate-fade-in">
            <div className="max-w-3xl mx-auto flex gap-5 w-full">
                {/* Avatar */}
                <div className="flex-shrink-0">
                    <div
                        className="w-9 h-9 rounded-full flex items-center justify-center text-white font-semibold text-sm shadow-md"
                        style={{
                            background: `linear-gradient(135deg, ${accentColor}88, ${accentColor})`,
                        }}
                    >
                        {expertName?.charAt(0) || 'E'}
                    </div>
                </div>

                {/* Typing dots */}
                <div className="flex items-center gap-1 pt-3">
                    {[0, 1, 2].map((i) => (
                        <div
                            key={i}
                            className={cn(
                                'w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-500',
                            )}
                            style={{
                                animation: 'pulse-dot 1.4s ease-in-out infinite',
                                animationDelay: `${i * 0.2}s`,
                            }}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}
