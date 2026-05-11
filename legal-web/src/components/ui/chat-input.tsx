'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp, CornerDownLeft } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    expertName?: string;
}

export function ChatInput({ onSend, disabled, expertName }: ChatInputProps) {
    const [input, setInput] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
        }
    }, [input]);

    const handleSend = () => {
        if (input.trim() && !disabled) {
            onSend(input.trim());
            setInput('');
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const hasInput = input.trim().length > 0;
    const canSend = hasInput && !disabled;
    const charCount = input.length;
    const showCharHint = charCount > 600;

    const containerStyle: React.CSSProperties = {
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
        boxShadow: isFocused
            ? '0 -2px 24px rgba(0,0,0,0.18), 0 0 0 2px rgba(91,106,240,0.35)'
            : '0 -2px 20px rgba(0,0,0,0.15)',
        borderColor: isFocused ? 'var(--primary)' : 'var(--border)',
        transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
    };

    return (
        <div className="px-4 pt-3 pb-4"
             style={{ background: 'linear-gradient(to top, var(--background) 60%, transparent)' }}>
            <div className="max-w-3xl mx-auto">
                <div className="rounded-2xl overflow-hidden" style={containerStyle}>
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={
                            disabled
                                ? 'Connecting...'
                                : `Message ${expertName || 'Legal Expert'}...`
                        }
                        disabled={disabled}
                        rows={1}
                        aria-label="Message input"
                        className={cn(
                            'w-full px-4 pt-4 pb-1.5 resize-none',
                            'text-[15px] leading-relaxed',
                            'focus:outline-none',
                            'disabled:opacity-40 disabled:cursor-not-allowed',
                            'placeholder:text-[var(--muted-foreground)]',
                        )}
                        style={{
                            background: 'transparent',
                            color: 'var(--foreground)',
                            caretColor: 'var(--primary)',
                            border: 'none',
                        }}
                    />
                    {/* Bottom toolbar */}
                    <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pt-1">
                        <div className="flex items-center gap-2 min-w-0">
                            <KeyHint label="Enter" description="to send" />
                            <span className="hidden sm:inline-block" style={{ color: 'var(--muted-foreground)', opacity: 0.4 }}>·</span>
                            <KeyHint label="Shift+Enter" description="for new line" className="hidden sm:inline-flex" />
                        </div>
                        <div className="flex items-center gap-2">
                            {showCharHint && (
                                <span className="text-[11px] tabular-nums font-mono"
                                      style={{ color: charCount > 2000 ? 'var(--warning)' : 'var(--muted-foreground)' }}>
                                    {charCount.toLocaleString()}
                                </span>
                            )}
                            <button
                                onClick={handleSend}
                                disabled={!canSend}
                                type="button"
                                aria-label="Send message"
                                className="group flex items-center justify-center w-9 h-9 rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-1)]"
                                style={{
                                    background: canSend
                                        ? 'linear-gradient(135deg, var(--primary), #8b5cf6)'
                                        : 'var(--surface-3)',
                                    color: canSend ? '#fff' : 'var(--muted-foreground)',
                                    cursor: canSend ? 'pointer' : 'not-allowed',
                                    opacity: canSend ? 1 : 0.45,
                                    boxShadow: canSend ? '0 4px 14px rgba(91,106,240,0.4)' : 'none',
                                    transform: canSend ? 'scale(1)' : 'scale(0.92)',
                                    transition: 'transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease, background 0.2s ease',
                                }}
                                onMouseEnter={(e) => {
                                    if (!canSend) return;
                                    e.currentTarget.style.transform = 'scale(1.06)';
                                    e.currentTarget.style.filter = 'brightness(1.08)';
                                    e.currentTarget.style.boxShadow = '0 6px 20px rgba(91,106,240,0.55)';
                                }}
                                onMouseLeave={(e) => {
                                    if (!canSend) return;
                                    e.currentTarget.style.transform = 'scale(1)';
                                    e.currentTarget.style.filter = 'brightness(1)';
                                    e.currentTarget.style.boxShadow = '0 4px 14px rgba(91,106,240,0.4)';
                                }}
                            >
                                <ArrowUp size={16} strokeWidth={2.5} />
                            </button>
                        </div>
                    </div>
                </div>
                <p className="text-center mt-3 text-[11px] leading-relaxed px-4"
                   style={{ color: 'var(--muted-foreground)', opacity: 0.7 }}>
                    LexGH may produce inaccurate information.{' '}
                    <span className="hidden sm:inline">Always verify with official statutes and case law before relying on it in practice.</span>
                    <span className="sm:hidden">Verify with official sources.</span>
                </p>
            </div>
        </div>
    );
}

function KeyHint({
    label,
    description,
    className,
}: {
    label: string;
    description: string;
    className?: string;
}) {
    const isEnter = label === 'Enter';
    return (
        <span className={cn('inline-flex items-center gap-1.5 text-[11px] whitespace-nowrap', className)}
              style={{ color: 'var(--muted-foreground)' }}>
            <kbd className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md font-mono text-[10px] font-semibold"
                 style={{
                     background: 'var(--surface-2)',
                     border: '1px solid var(--border)',
                     color: 'var(--foreground)',
                 }}>
                {isEnter ? (
                    <>
                        <CornerDownLeft size={9} strokeWidth={2.5} />
                        <span>Enter</span>
                    </>
                ) : (
                    <span>{label}</span>
                )}
            </kbd>
            <span>{description}</span>
        </span>
    );
}
