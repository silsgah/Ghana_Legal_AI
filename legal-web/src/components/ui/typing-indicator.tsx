'use client';

import React from 'react';

interface TypingIndicatorProps {
    expertName?: string;
    accentColor?: string;
}

export function TypingIndicator({ expertName, accentColor = '#5b6af0' }: TypingIndicatorProps) {
    return (
        <div className="animate-fade-in"
             style={{
                 padding: '1.5rem 1.75rem',
                 background: 'var(--surface-1)',
                 borderBottom: '1px solid var(--border)',
             }}>
            <div className="max-w-3xl mx-auto flex gap-4 w-full">
                {/* Avatar */}
                <div className="flex-shrink-0 pt-0.5">
                    <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center text-sm shadow-sm"
                        style={{
                            background: `linear-gradient(135deg, ${accentColor}66, ${accentColor})`,
                        }}
                    >
                        {expertName?.charAt(0) || '⚖️'}
                    </div>
                </div>

                {/* Typing animation */}
                <div className="flex flex-col gap-1.5 pt-1">
                    <span className="text-[13px] font-semibold" style={{ color: accentColor }}>
                        {expertName || 'Legal Expert'}
                    </span>
                    <div className="flex items-center gap-1.5">
                        {[0, 1, 2].map((i) => (
                            <div
                                key={i}
                                className="w-1.5 h-1.5 rounded-full"
                                style={{
                                    background: 'var(--muted-foreground)',
                                    animation: 'pulse-dot 1.4s ease-in-out infinite',
                                    animationDelay: `${i * 0.2}s`,
                                }}
                            />
                        ))}
                        <span className="text-[12px] ml-1" style={{ color: 'var(--muted-foreground)' }}>
                            is researching...
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}
