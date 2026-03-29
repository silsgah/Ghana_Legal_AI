'use client';

import React from 'react';
import { Scale } from 'lucide-react';

interface TypingIndicatorProps {
    expertName?: string;
    accentColor?: string;
}

export function TypingIndicator({ expertName, accentColor = '#5b6af0' }: TypingIndicatorProps) {
    return (
        <div className="animate-fade-in" style={{ background: 'transparent' }}>
            <div className="max-w-3xl mx-auto px-5 py-5">
                <div className="flex gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm"
                             style={{
                                 background: `linear-gradient(135deg, ${accentColor}33, ${accentColor}88)`,
                                 border: `1.5px solid ${accentColor}44`,
                             }}>
                            {expertName?.charAt(0) || <Scale size={14} />}
                        </div>
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-semibold" style={{ color: accentColor }}>
                                {expertName || 'Legal Expert'}
                            </span>
                        </div>
                        <div className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl rounded-tl-md"
                             style={{
                                 background: 'var(--surface-1)',
                                 border: '1px solid var(--border)',
                             }}>
                            <div className="flex items-center gap-1">
                                {[0, 1, 2].map((i) => (
                                    <div
                                        key={i}
                                        className="w-2 h-2 rounded-full"
                                        style={{
                                            background: accentColor,
                                            opacity: 0.6,
                                            animation: 'pulse-dot 1.4s ease-in-out infinite',
                                            animationDelay: `${i * 0.2}s`,
                                        }}
                                    />
                                ))}
                            </div>
                            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                Researching...
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
