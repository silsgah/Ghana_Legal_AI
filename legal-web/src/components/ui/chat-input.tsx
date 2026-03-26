'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp, Scale } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    expertName?: string;
}

export function ChatInput({ onSend, disabled, expertName }: ChatInputProps) {
    const [input, setInput] = useState('');
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Auto-resize textarea
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

    return (
        <div className="p-4 pb-5"
             style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-1)' }}>
            <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end gap-2">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={
                                disabled
                                    ? 'Connecting to server...'
                                    : `Ask ${expertName || 'the legal expert'} a question...`
                            }
                            disabled={disabled}
                            rows={1}
                            className={cn(
                                'w-full px-5 py-4 pr-14 resize-none',
                                'text-[15px] leading-relaxed',
                                'focus:outline-none',
                                'disabled:opacity-40 disabled:cursor-not-allowed',
                                'transition-all duration-200'
                            )}
                            style={{
                                background: 'var(--surface-2)',
                                color: 'var(--foreground)',
                                border: '1px solid var(--border)',
                                borderRadius: 'var(--radius-lg)',
                                caretColor: 'var(--primary)',
                            }}
                            onFocus={(e) => {
                                e.currentTarget.style.borderColor = 'var(--primary)';
                                e.currentTarget.style.boxShadow = '0 0 0 3px var(--primary-muted)';
                            }}
                            onBlur={(e) => {
                                e.currentTarget.style.borderColor = 'var(--border)';
                                e.currentTarget.style.boxShadow = 'none';
                            }}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || disabled}
                            className="absolute right-2.5 bottom-2.5 p-2.5 rounded-xl transition-all duration-200"
                            style={{
                                background: input.trim() && !disabled ? 'var(--primary)' : 'var(--surface-3)',
                                color: input.trim() && !disabled ? '#fff' : 'var(--muted-foreground)',
                                cursor: !input.trim() || disabled ? 'not-allowed' : 'pointer',
                                opacity: !input.trim() || disabled ? 0.5 : 1,
                            }}
                        >
                            <ArrowUp size={18} />
                        </button>
                    </div>
                </div>
                <div className="flex items-center justify-between mt-3 text-[11px] px-1"
                     style={{ color: 'var(--muted-foreground)' }}>
                    <div className="flex items-center gap-1.5">
                        <Scale size={11} />
                        <span>Ghana Legal AI &bull; Powered by EED Soft Consult</span>
                    </div>
                    <span>Enter to send &bull; Shift+Enter for new line</span>
                </div>
            </div>
        </div>
    );
}
