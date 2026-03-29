'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp, Paperclip } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    expertName?: string;
}

export function ChatInput({ onSend, disabled, expertName }: ChatInputProps) {
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto';
            textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
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

    return (
        <div className="px-4 py-3"
             style={{
                 background: 'linear-gradient(to top, var(--background) 60%, transparent)',
             }}>
            <div className="max-w-3xl mx-auto">
                <div className="rounded-2xl overflow-hidden"
                     style={{
                         background: 'var(--surface-1)',
                         border: '1px solid var(--border)',
                         boxShadow: '0 -2px 20px rgba(0,0,0,0.15)',
                         transition: 'border-color 0.2s, box-shadow 0.2s',
                     }}>
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={
                            disabled
                                ? 'Connecting...'
                                : `Message ${expertName || 'Legal Expert'}...`
                        }
                        disabled={disabled}
                        rows={1}
                        className={cn(
                            'w-full px-4 pt-3.5 pb-1 resize-none',
                            'text-sm leading-relaxed',
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
                        onFocus={(e) => {
                            const container = e.currentTarget.parentElement;
                            if (container) {
                                container.style.borderColor = 'var(--primary)';
                                container.style.boxShadow = '0 -2px 20px rgba(0,0,0,0.15), 0 0 0 1px var(--primary)';
                            }
                        }}
                        onBlur={(e) => {
                            const container = e.currentTarget.parentElement;
                            if (container) {
                                container.style.borderColor = 'var(--border)';
                                container.style.boxShadow = '0 -2px 20px rgba(0,0,0,0.15)';
                            }
                        }}
                    />
                    {/* Bottom toolbar */}
                    <div className="flex items-center justify-between px-3 py-2">
                        <div className="flex items-center gap-1">
                            <span className="text-[10px] px-2 py-0.5 rounded-md"
                                  style={{ color: 'var(--muted-foreground)', background: 'var(--surface-2)' }}>
                                Enter to send
                            </span>
                        </div>
                        <button
                            onClick={handleSend}
                            disabled={!hasInput || disabled}
                            className="p-2 rounded-xl transition-all duration-200"
                            style={{
                                background: hasInput && !disabled ? 'var(--primary)' : 'var(--surface-3)',
                                color: hasInput && !disabled ? '#fff' : 'var(--muted-foreground)',
                                cursor: !hasInput || disabled ? 'not-allowed' : 'pointer',
                                opacity: !hasInput || disabled ? 0.4 : 1,
                                transform: hasInput ? 'scale(1)' : 'scale(0.95)',
                            }}
                        >
                            <ArrowUp size={16} strokeWidth={2.5} />
                        </button>
                    </div>
                </div>
                <div className="text-center mt-2">
                    <span className="text-[10px]" style={{ color: 'var(--muted-foreground)', opacity: 0.5 }}>
                        Ghana Legal AI may produce inaccurate information. Verify with official sources.
                    </span>
                </div>
            </div>
        </div>
    );
}
