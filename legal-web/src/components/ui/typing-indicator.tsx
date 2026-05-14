'use client';

import React from 'react';
import { Scale } from 'lucide-react';

interface TypingIndicatorProps {
    expertName?: string;
    accentColor?: string;
}

export function TypingIndicator({ expertName, accentColor = '#6272f0' }: TypingIndicatorProps) {
    return (
        <div className="animate-fade-in" style={{ background: 'transparent' }}>
            <div className="max-w-4xl mx-auto px-5 py-5">
                <div className="flex gap-4">
                    <div className="flex-shrink-0 mt-0.5">
                        <div className="w-10 h-10 rounded-full flex items-center justify-center text-sm"
                             style={{
                                 background: `linear-gradient(135deg, ${accentColor}30, ${accentColor}70)`,
                                 border: `1.5px solid ${accentColor}44`,
                                 boxShadow: `0 2px 8px ${accentColor}20`,
                             }}>
                            {expertName?.charAt(0) || <Scale size={16} />}
                        </div>
                    </div>
                    <div className="flex-1">
                        <div className="flex items-center gap-2.5 mb-2.5">
                            <span className="text-[14px] font-semibold" style={{ color: accentColor }}>
                                {expertName || 'Legal Expert'}
                            </span>
                        </div>
                        <div className="inline-flex items-center gap-2.5 px-5 py-3.5 rounded-2xl rounded-tl-lg"
                             style={{
                                 background: 'var(--surface-1)',
                                 border: '1px solid var(--border)',
                             }}>
                            <div className="flex items-center gap-1.5">
                                {[0, 1, 2].map((i) => (
                                    <div
                                        key={i}
                                        className="w-2.5 h-2.5 rounded-full"
                                        style={{
                                            background: accentColor,
                                            opacity: 0.6,
                                            animation: 'pulse-dot 1.4s ease-in-out infinite',
                                            animationDelay: `${i * 0.2}s`,
                                        }}
                                    />
                                ))}
                            </div>
                            <span className="text-[13px] font-medium" style={{ color: 'var(--muted-foreground)' }}>
                                Researching...
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
