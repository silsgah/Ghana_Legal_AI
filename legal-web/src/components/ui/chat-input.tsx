'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp, CornerDownLeft, Scale, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
            if (textareaRef.current) textareaRef.current.style.height = 'auto';
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const canSend = input.trim().length > 0 && !disabled;

    return (
        <div className="relative border-t border-border bg-background/95 px-4 pb-4 pt-3 sm:px-6 sm:pb-5 sm:pt-4 flex-shrink-0">
            <div aria-hidden className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/35 to-transparent" />
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between px-1 pb-2.5">
                    <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                        <Scale className="h-3.5 w-3.5 text-[var(--ghana-gold)]" />
                        Legal research query
                    </div>
                    <div className="hidden sm:flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <ShieldCheck className="h-3.5 w-3.5 text-[var(--ghana-green)]" />
                        Grounded sources where available
                    </div>
                </div>
                <div
                    className={cn(
                        'relative flex items-end gap-3 rounded-[1.25rem] border bg-card px-4 py-3 shadow-[0_10px_30px_rgba(2,6,23,0.16)] transition-all duration-200 sm:px-5',
                        isFocused
                            ? 'border-primary shadow-[0_0_0_3px_color-mix(in_oklch,var(--primary)_18%,transparent),0_16px_38px_rgba(2,6,23,0.20)]'
                            : 'border-border hover:border-primary/40'
                    )}
                >
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={`Ask ${expertName || 'the legal expert'} about Ghanaian law…`}
                        disabled={disabled}
                        rows={1}
                        className="flex-1 resize-none bg-transparent py-1 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground/80 focus:outline-none disabled:opacity-50 min-h-[28px] max-h-[200px]"
                    />

                    <Button
                        type="button"
                        size="icon"
                        variant={canSend ? 'gradient' : 'secondary'}
                        disabled={!canSend}
                        onClick={handleSend}
                        aria-label="Send message"
                        className="self-end shrink-0 rounded-xl shadow-sm"
                    >
                        <ArrowUp className="h-4 w-4" />
                    </Button>
                </div>

                <div className="flex items-center justify-between mt-2.5 px-1 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1.5">
                        <kbd className="px-1.5 py-0.5 rounded-md border border-border bg-muted font-mono text-[10px] inline-flex items-center gap-1">
                            <CornerDownLeft size={10} />
                            Enter
                        </kbd>
                        to send
                        <span className="mx-1.5 opacity-40">·</span>
                        <kbd className="px-1.5 py-0.5 rounded-md border border-border bg-muted font-mono text-[10px]">
                            Shift+Enter
                        </kbd>
                        for new line
                    </span>
                    <span className="hidden sm:inline text-muted-foreground/75">
                        AI research assistance — verify before relying on an answer
                    </span>
                </div>
            </div>
        </div>
    );
}
