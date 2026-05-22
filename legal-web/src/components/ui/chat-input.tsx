'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp, CornerDownLeft } from 'lucide-react';
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
        <div className="border-t border-border bg-card/60 backdrop-blur-md p-4 sm:p-5 flex-shrink-0">
            <div className="max-w-4xl mx-auto">
                <div
                    className={cn(
                        'relative flex items-end gap-3 rounded-2xl border bg-background px-4 py-3 transition-all duration-200',
                        isFocused
                            ? 'border-primary shadow-[0_0_0_3px_color-mix(in_oklch,var(--primary)_18%,transparent)]'
                            : 'border-border hover:border-border'
                    )}
                >
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={`Ask ${expertName || 'the legal expert'} anything about Ghanaian law…`}
                        disabled={disabled}
                        rows={1}
                        className="flex-1 resize-none bg-transparent text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 min-h-[24px] max-h-[200px]"
                    />

                    <Button
                        type="button"
                        size="icon"
                        variant={canSend ? 'gradient' : 'secondary'}
                        disabled={!canSend}
                        onClick={handleSend}
                        aria-label="Send message"
                        className="self-end shrink-0 rounded-xl"
                    >
                        <ArrowUp className="h-4 w-4" />
                    </Button>
                </div>

                <div className="flex items-center justify-between mt-3 px-1 text-[11px] text-muted-foreground">
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
                    <span className="hidden sm:inline">
                        Grounded in Ghanaian statutes &amp; case law
                    </span>
                </div>
            </div>
        </div>
    );
}
