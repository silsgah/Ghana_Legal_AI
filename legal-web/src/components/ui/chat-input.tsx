'use client';

import React, { useState, KeyboardEvent, useRef, useEffect } from 'react';
import { Send, Sparkles } from 'lucide-react';
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
            // Reset height
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
        <div className="border-t border-zinc-200 dark:border-zinc-800 p-4 bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm">
            <div className="max-w-3xl mx-auto">
                <div className="relative flex items-end gap-2">
                    <div className="flex-1 relative">
                        <textarea
                            ref={textareaRef}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder={`Message ${expertName || 'the legal expert'}...`}
                            disabled={disabled}
                            rows={1}
                            className={cn(
                                'w-full px-4 py-3.5 pr-12 rounded-2xl resize-none',
                                'bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700',
                                'text-zinc-900 dark:text-zinc-100 placeholder-zinc-400',
                                'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
                                'disabled:opacity-50 disabled:cursor-not-allowed',
                                'transition-all duration-200'
                            )}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!input.trim() || disabled}
                            className={cn(
                                'absolute right-2 bottom-2 p-2 rounded-xl',
                                'bg-indigo-600 text-white shadow-md',
                                'hover:bg-indigo-700 active:scale-95',
                                'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-indigo-600',
                                'transition-all duration-200'
                            )}
                        >
                            <Send size={18} />
                        </button>
                    </div>
                </div>
                <div className="flex items-center justify-between mt-3 text-xs text-zinc-400">
                    <div className="flex items-center gap-1.5">
                        <Sparkles size={12} />
                        <span>Powered by Groq LLM</span>
                    </div>
                    <span>Press Enter to send, Shift+Enter for new line</span>
                </div>
            </div>
        </div>
    );
}
