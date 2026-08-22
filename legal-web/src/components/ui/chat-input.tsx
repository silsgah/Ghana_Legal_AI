'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { ArrowUp } from 'lucide-react';
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
        <div className="bg-background/90 px-4 pb-4 pt-2 sm:px-6 sm:pb-5 flex-shrink-0">
            <div className="max-w-3xl mx-auto">
                <div
                    className={cn(
                        'relative flex items-end gap-2 rounded-[1.6rem] border bg-muted/55 px-4 py-3 shadow-[0_2px_12px_rgba(2,6,23,0.12)] transition-all duration-200 sm:px-4',
                        isFocused
                            ? 'border-foreground/25 bg-card shadow-[0_0_0_1px_color-mix(in_oklch,var(--foreground)_12%,transparent),0_6px_22px_rgba(2,6,23,0.14)]'
                            : 'border-border hover:border-foreground/20 hover:bg-card'
                    )}
                >
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        onFocus={() => setIsFocused(true)}
                        onBlur={() => setIsFocused(false)}
                        placeholder={`Message ${expertName || 'LexGH'}…`}
                        disabled={disabled}
                        rows={1}
                        className="flex-1 resize-none bg-transparent px-1 py-1.5 text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground/75 focus:outline-none disabled:opacity-50 min-h-[28px] max-h-[200px]"
                    />

                    <Button
                        type="button"
                        size="icon"
                        variant={canSend ? 'gradient' : 'secondary'}
                        disabled={!canSend}
                        onClick={handleSend}
                        aria-label="Send message"
                        className="self-end shrink-0 rounded-full shadow-none"
                    >
                        <ArrowUp className="h-4 w-4" />
                    </Button>
                </div>

                <div className="mt-2 text-center text-[11px] text-muted-foreground/70">
                    LexGH can make mistakes. Verify legal authorities before relying on an answer.
                </div>
            </div>
        </div>
    );
}
