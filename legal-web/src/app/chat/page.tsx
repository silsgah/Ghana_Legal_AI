'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { UserButton } from '@clerk/nextjs';
import { Sidebar } from '@/components/ui/sidebar';
import { MessageBubble } from '@/components/ui/message-bubble';
import { ChatInput } from '@/components/ui/chat-input';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { UpgradeModal } from '@/components/ui/upgrade-modal';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ThemeToggle } from '@/components/theme-toggle';
import {
    Menu, Scale, BookOpen, Gavel, ScrollText, Sparkles, Zap, Crown, ArrowUpRight,
} from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { useUsage } from '@/hooks/use-usage';
import { LEGAL_EXPERTS, getLegalExpert } from '@/lib/legal-experts';
import { cn } from '@/lib/utils';

const SUGGESTED_PROMPTS = [
    {
        icon: <BookOpen size={16} />,
        label: 'Constitutional Rights',
        prompt: 'What does the 1992 Constitution say about fundamental human rights and freedoms?',
    },
    {
        icon: <Gavel size={16} />,
        label: 'Landmark Case',
        prompt: 'Summarize the Tuffuor v Attorney General case and its significance',
    },
    {
        icon: <ScrollText size={16} />,
        label: 'Court Hierarchy',
        prompt: 'Explain the hierarchy of courts in Ghana and their jurisdictions',
    },
    {
        icon: <Scale size={16} />,
        label: 'Chief Justice',
        prompt: 'How is the Chief Justice appointed and what are the qualifications?',
    },
];

const PLAN_LABELS: Record<string, string> = {
    student: 'Student',
    professional: 'Pro',
    firm: 'Firm',
    institution: 'Institution',
};

export default function ChatPage() {
    const [selectedExpertId, setSelectedExpertId] = useState('constitutional');
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);

    const selectedExpert = getLegalExpert(selectedExpertId);
    const { usage, fetchUsage } = useUsage();

    const handleStreamComplete = useCallback(() => {
        fetchUsage();
    }, [fetchUsage]);

    const {
        messages,
        sendMessage,
        resetChat,
        isStreaming,
        connectionStatus,
        reconnect,
    } = useChat({ expertId: selectedExpertId, onStreamComplete: handleStreamComplete });

    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isStreaming]);

    const handleSelectExpert = (id: string) => {
        setSelectedExpertId(id);
        setIsSidebarOpen(false);
    };

    return (
        <div className="flex h-screen bg-background text-foreground">
            <UpgradeModal isOpen={isUpgradeModalOpen} onClose={() => setIsUpgradeModalOpen(false)} />

            {/* Mobile sidebar toggle */}
            <Button
                variant="outline"
                size="icon"
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label="Toggle sidebar"
                className="lg:hidden fixed top-3 left-3 z-50 shadow-md"
            >
                <Menu className="h-4 w-4" />
            </Button>

            {/* Sidebar */}
            <div
                className={cn(
                    'fixed lg:relative z-40 h-full transition-transform duration-300 ease-out',
                    isSidebarOpen ? 'translate-x-0' : '-translate-x-full',
                    'lg:translate-x-0'
                )}
            >
                <Sidebar
                    experts={LEGAL_EXPERTS}
                    selectedExpertId={selectedExpertId}
                    onSelectExpert={handleSelectExpert}
                    onReset={resetChat}
                    connectionStatus={connectionStatus}
                    onReconnect={reconnect}
                    onUpgradeClick={() => setIsUpgradeModalOpen(true)}
                    collapsed={isSidebarCollapsed}
                    onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                />
            </div>

            {/* Mobile overlay */}
            {isSidebarOpen && (
                <div
                    className="lg:hidden fixed inset-0 z-30 bg-black/65 backdrop-blur-[6px]"
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Main chat area */}
            <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden">
                {/* Header */}
                <header className="h-16 flex items-center justify-between px-5 lg:px-6 flex-shrink-0 bg-card/80 backdrop-blur-md border-b border-border">
                    <div className="lg:pl-0 pl-12 flex items-center gap-3.5 min-w-0">
                        <div
                            className="w-9 h-9 rounded-full flex items-center justify-center border-[1.5px] shrink-0"
                            style={{
                                background: `linear-gradient(135deg, ${selectedExpert?.accentColor}30, ${selectedExpert?.accentColor}70)`,
                                borderColor: `${selectedExpert?.accentColor}44`,
                            }}
                        >
                            {selectedExpert?.icon}
                        </div>
                        <div className="min-w-0">
                            <h1 className="font-semibold text-[15px] leading-tight truncate">
                                {selectedExpert?.name}
                            </h1>
                            <span className="text-[12px] text-muted-foreground truncate block">
                                {selectedExpert?.field}
                            </span>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 sm:gap-3">
                        {/* Plan & usage */}
                        {usage && (
                            <div className="hidden sm:flex items-center gap-2">
                                {usage.plan === 'free' ? (
                                    <>
                                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted border border-border">
                                            <Zap className="h-3.5 w-3.5 text-[var(--ghana-gold)]" />
                                            <span
                                                className={cn(
                                                    'text-[13px] font-semibold tabular-nums',
                                                    usage.remaining > 0 ? 'text-foreground' : 'text-destructive'
                                                )}
                                            >
                                                {usage.used_today}/{usage.daily_limit}
                                            </span>
                                            <span className="text-[12px] text-muted-foreground">today</span>
                                        </div>
                                        <Button
                                            variant="gradient"
                                            size="sm"
                                            onClick={() => setIsUpgradeModalOpen(true)}
                                            className="rounded-full"
                                        >
                                            <Crown className="h-3.5 w-3.5" />
                                            Upgrade
                                        </Button>
                                    </>
                                ) : (
                                    <Badge
                                        variant="default"
                                        className="px-3 py-1.5 bg-[color:color-mix(in_oklch,var(--primary)_15%,transparent)] text-primary border border-[color:color-mix(in_oklch,var(--primary)_30%,transparent)] normal-case tracking-normal text-[12px]"
                                    >
                                        <Crown className="h-3 w-3" />
                                        {PLAN_LABELS[usage.plan] || usage.plan}
                                    </Badge>
                                )}
                            </div>
                        )}

                        {/* Connection */}
                        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted border border-border">
                            <div
                                className={cn(
                                    'w-2 h-2 rounded-full animate-pulse',
                                    connectionStatus === 'connected' && 'bg-[var(--ghana-green)]',
                                    connectionStatus === 'connecting' && 'bg-[var(--ghana-gold)]',
                                    (connectionStatus === 'disconnected' || connectionStatus === 'error') &&
                                        'bg-destructive'
                                )}
                            />
                            <span className="text-[12px] font-medium text-muted-foreground hidden md:inline">
                                {connectionStatus === 'connected'
                                    ? 'Online'
                                    : connectionStatus === 'connecting'
                                        ? 'Connecting…'
                                        : 'Offline'}
                            </span>
                            {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                                <Button
                                    variant="link"
                                    size="sm"
                                    onClick={reconnect}
                                    className="h-auto p-0 ml-1 text-[12px] font-semibold"
                                >
                                    Retry
                                </Button>
                            )}
                        </div>

                        <ThemeToggle />
                        <UserButton />
                    </div>
                </header>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto">
                    {messages.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center p-8 animate-float-in">
                            <div className="relative mb-7">
                                <div
                                    aria-hidden
                                    className="absolute inset-0 rounded-3xl blur-3xl opacity-40"
                                    style={{
                                        background: `radial-gradient(circle, ${selectedExpert?.accentColor || 'var(--primary)'}55, transparent 70%)`,
                                    }}
                                />
                                <div
                                    className="relative w-20 h-20 rounded-2xl flex items-center justify-center border"
                                    style={{
                                        background: `linear-gradient(135deg, ${selectedExpert?.accentColor || 'var(--primary)'}20, ${selectedExpert?.accentColor || 'var(--primary)'}50)`,
                                        borderColor: `${selectedExpert?.accentColor || 'var(--primary)'}44`,
                                        boxShadow: `0 12px 36px ${selectedExpert?.accentColor || 'var(--primary)'}25`,
                                    }}
                                >
                                    <Scale className="h-8 w-8" style={{ color: selectedExpert?.accentColor || 'var(--primary)' }} />
                                </div>
                            </div>

                            <h2 className="text-3xl sm:text-4xl font-bold mb-2 tracking-tight text-center">
                                {selectedExpert?.name}
                            </h2>
                            <p className="text-base sm:text-lg max-w-lg text-center mb-3 leading-relaxed text-muted-foreground">
                                {selectedExpert?.tagline}
                            </p>
                            <Badge variant="outline" className="mb-10 gap-1.5 normal-case tracking-normal">
                                <Sparkles className="h-3 w-3 text-[var(--ghana-gold)]" />
                                {selectedExpert?.era}
                            </Badge>

                            <div className="w-full max-w-2xl">
                                <div className="flex items-center justify-center mb-4">
                                    <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                                        Try asking
                                    </span>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    {SUGGESTED_PROMPTS.map(({ icon, label, prompt }) => (
                                        <button
                                            key={prompt}
                                            onClick={() => sendMessage(prompt)}
                                            type="button"
                                            className="group relative px-5 py-4 text-left rounded-xl bg-card border border-border hover:border-primary hover:bg-[color:color-mix(in_oklch,var(--primary)_8%,transparent)] hover:-translate-y-0.5 hover:shadow-[0_8px_28px_color-mix(in_oklch,var(--primary)_18%,transparent)] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2 mb-1.5 text-primary">
                                                        {icon}
                                                        <span className="text-[13px] font-semibold tracking-wide">{label}</span>
                                                    </div>
                                                    <p className="text-[13.5px] leading-relaxed text-muted-foreground">
                                                        {prompt}
                                                    </p>
                                                </div>
                                                <ArrowUpRight className="h-4 w-4 shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity text-primary" />
                                            </div>
                                        </button>
                                    ))}
                                </div>

                                <p className="text-[12px] text-center mt-8 text-muted-foreground/70">
                                    Responses are grounded in Ghanaian statutes and case law. Verify before relying on them in legal practice.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            {messages.map((msg) => (
                                <MessageBubble
                                    key={msg.id}
                                    role={msg.role}
                                    content={msg.content}
                                    expert={selectedExpert}
                                    timestamp={msg.timestamp}
                                    sources={msg.sources}
                                    envelope={msg.envelope}
                                />
                            ))}
                            {isStreaming && messages[messages.length - 1]?.role === 'user' && (
                                <TypingIndicator
                                    expertName={selectedExpert?.name}
                                    accentColor={selectedExpert?.accentColor}
                                />
                            )}
                            <div ref={messagesEndRef} className="h-6" />
                        </div>
                    )}
                </div>

                {/* Input */}
                <ChatInput
                    onSend={sendMessage}
                    disabled={isStreaming || connectionStatus !== 'connected'}
                    expertName={selectedExpert?.name}
                />
            </div>
        </div>
    );
}
