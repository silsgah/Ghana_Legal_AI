'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { UserButton } from '@clerk/nextjs';
import { Sidebar } from '@/components/ui/sidebar';
import { MessageBubble } from '@/components/ui/message-bubble';
import { ChatInput } from '@/components/ui/chat-input';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { UpgradeModal } from '@/components/ui/upgrade-modal';
import { Menu, Scale, BookOpen, Gavel, ScrollText, Sparkles, Zap, Crown, ArrowUpRight } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { useUsage } from '@/hooks/use-usage';
import { LEGAL_EXPERTS, getLegalExpert } from '@/lib/legal-experts';

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

export default function ChatPage() {
    const [selectedExpertId, setSelectedExpertId] = useState('constitutional');
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);

    const selectedExpert = getLegalExpert(selectedExpertId);

    const { usage, fetchUsage } = useUsage();

    const handleStreamComplete = useCallback(() => {
        // Refresh usage count after each response completes
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
        <div className="flex h-screen" style={{ background: 'var(--background)' }}>
            <UpgradeModal
                isOpen={isUpgradeModalOpen}
                onClose={() => setIsUpgradeModalOpen(false)}
            />

            {/* Mobile Sidebar Toggle */}
            <button
                className="lg:hidden fixed top-3.5 left-3.5 z-50 p-2.5 rounded-xl"
                style={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    boxShadow: 'var(--shadow-md)',
                }}
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label="Toggle sidebar"
            >
                <Menu size={20} style={{ color: 'var(--foreground)' }} />
            </button>

            {/* Sidebar — desktop: always visible, collapsible; mobile: slide in/out */}
            <div className={`${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
                } lg:translate-x-0 fixed lg:relative z-40 h-full transition-transform duration-300 ease-out`}>
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

            {/* Mobile Overlay */}
            {isSidebarOpen && (
                <div
                    className="lg:hidden fixed inset-0 z-30"
                    style={{ background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(6px)' }}
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden">
                {/* Header */}
                <header className="h-16 flex items-center justify-between px-5 lg:px-6 flex-shrink-0"
                        style={{
                            background: 'var(--surface-1)',
                            borderBottom: '1px solid var(--border)',
                        }}>
                    <div className="lg:pl-0 pl-12 flex items-center gap-3.5">
                        <div className="w-9 h-9 rounded-full flex items-center justify-center"
                             style={{
                                 background: `linear-gradient(135deg, ${selectedExpert?.accentColor}30, ${selectedExpert?.accentColor}70)`,
                                 border: `1.5px solid ${selectedExpert?.accentColor}44`,
                             }}>
                            {selectedExpert?.icon}
                        </div>
                        <div>
                            <h1 className="font-semibold text-[15px] leading-tight"
                                style={{ color: 'var(--foreground)' }}>
                                {selectedExpert?.name}
                            </h1>
                            <span className="text-[12px]" style={{ color: 'var(--muted-foreground)' }}>
                                {selectedExpert?.field}
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        {/* Plan & Usage Badge */}
                        {usage && (
                            <div className="hidden sm:flex items-center gap-2.5">
                                {usage.plan === 'free' ? (
                                    <>
                                        <div className="flex items-center gap-2 px-3.5 py-2 rounded-full"
                                             style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                            <Zap size={13} style={{ color: 'var(--ghana-gold)' }} />
                                            <span className="text-[13px] font-semibold tabular-nums"
                                                  style={{ color: usage.remaining > 0 ? 'var(--foreground)' : 'var(--error)' }}>
                                                {usage.used_today}/{usage.daily_limit}
                                            </span>
                                            <span className="text-[12px]" style={{ color: 'var(--muted-foreground)' }}>
                                                used today
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => setIsUpgradeModalOpen(true)}
                                            type="button"
                                            aria-label="Upgrade to Pro"
                                            className="group inline-flex items-center gap-2 px-4 py-2.5 rounded-full text-[13px] font-semibold cursor-pointer select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-1)] focus-visible:ring-[var(--primary)]"
                                            style={{
                                                background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
                                                color: '#fff',
                                                boxShadow: '0 4px 16px rgba(98,114,240,0.35)',
                                                transition: 'transform 0.15s ease, box-shadow 0.15s ease, filter 0.15s ease',
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.transform = 'translateY(-1px)';
                                                e.currentTarget.style.boxShadow = '0 6px 22px rgba(98,114,240,0.5)';
                                                e.currentTarget.style.filter = 'brightness(1.08)';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.transform = 'translateY(0)';
                                                e.currentTarget.style.boxShadow = '0 4px 16px rgba(98,114,240,0.35)';
                                                e.currentTarget.style.filter = 'brightness(1)';
                                            }}
                                            onMouseDown={(e) => {
                                                e.currentTarget.style.transform = 'translateY(0)';
                                            }}>
                                            <Crown size={14} className="drop-shadow-sm" />
                                            <span>Upgrade to Pro</span>
                                        </button>
                                    </>
                                ) : (
                                    <div className="flex items-center gap-2 px-3.5 py-2 rounded-full"
                                         style={{ background: 'rgba(98,114,240,0.10)', border: '1px solid rgba(98,114,240,0.20)' }}>
                                        <Crown size={13} style={{ color: 'var(--primary)' }} />
                                        <span className="text-[13px] font-semibold" style={{ color: 'var(--primary)' }}>
                                            {usage.plan === 'professional' ? 'Pro' : 'Enterprise'}
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                        {/* Connection Status */}
                        <div className="flex items-center gap-2 px-3 py-2 rounded-full"
                             style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                            <div className="w-2 h-2 rounded-full animate-pulse"
                                 style={{
                                     background: connectionStatus === 'connected' ? 'var(--success)'
                                         : connectionStatus === 'connecting' ? 'var(--warning)'
                                         : 'var(--error)',
                                 }} />
                            <span className="text-[12px] font-medium"
                                  style={{ color: 'var(--muted-foreground)' }}>
                                {connectionStatus === 'connected' ? 'Online'
                                    : connectionStatus === 'connecting' ? 'Connecting...'
                                    : 'Offline'}
                            </span>
                            {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                                <button onClick={reconnect}
                                        type="button"
                                        className="text-[12px] font-semibold ml-1 cursor-pointer hover:underline"
                                        style={{ color: 'var(--primary)' }}>
                                    Retry
                                </button>
                            )}
                        </div>
                        <UserButton />
                    </div>
                </header>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto">
                    {messages.length === 0 ? (
                        /* Empty state */
                        <div className="h-full flex flex-col items-center justify-center p-8 animate-float-in">
                            <div className="relative mb-8">
                                <div
                                    aria-hidden
                                    className="absolute inset-0 rounded-3xl blur-3xl opacity-40"
                                    style={{ background: `radial-gradient(circle, ${selectedExpert?.accentColor || 'var(--primary)'}55, transparent 70%)` }}
                                />
                                <div className="relative w-24 h-24 rounded-2xl flex items-center justify-center"
                                     style={{
                                         background: `linear-gradient(135deg, ${selectedExpert?.accentColor || 'var(--primary)'}20, ${selectedExpert?.accentColor || 'var(--primary)'}50)`,
                                         border: `1px solid ${selectedExpert?.accentColor || 'var(--primary)'}44`,
                                         boxShadow: `0 12px 36px ${selectedExpert?.accentColor || 'var(--primary)'}25`,
                                     }}>
                                    <Scale size={40} style={{ color: selectedExpert?.accentColor || 'var(--primary)' }} />
                                </div>
                            </div>

                            <h2 className="text-3xl sm:text-4xl font-bold mb-3 tracking-tight text-center" style={{ color: 'var(--foreground)' }}>
                                {selectedExpert?.name}
                            </h2>
                            <p className="text-base sm:text-lg max-w-lg text-center mb-3 leading-relaxed"
                               style={{ color: 'var(--muted-foreground)' }}>
                                {selectedExpert?.tagline}
                            </p>
                            <div className="flex items-center gap-2 mb-12 px-4 py-1.5 rounded-full"
                                 style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                <Sparkles size={13} style={{ color: 'var(--ghana-gold)' }} />
                                <span className="text-[12px] font-medium tracking-wide" style={{ color: 'var(--muted-foreground)' }}>
                                    {selectedExpert?.era}
                                </span>
                            </div>

                            <div className="w-full max-w-2xl">
                                <div className="flex items-center justify-center mb-5">
                                    <span className="text-[12px] font-semibold uppercase tracking-[0.18em]"
                                          style={{ color: 'var(--muted-foreground)' }}>
                                        Try asking
                                    </span>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                                    {SUGGESTED_PROMPTS.map(({ icon, label, prompt }) => (
                                        <button
                                            key={prompt}
                                            onClick={() => sendMessage(prompt)}
                                            type="button"
                                            className="group relative px-5 py-4 text-left rounded-xl cursor-pointer select-none focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]"
                                            style={{
                                                background: 'var(--surface-1)',
                                                border: '1px solid var(--border)',
                                                transition: 'transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease',
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.borderColor = 'var(--primary)';
                                                e.currentTarget.style.background = 'var(--primary-muted)';
                                                e.currentTarget.style.transform = 'translateY(-2px)';
                                                e.currentTarget.style.boxShadow = '0 8px 28px rgba(98,114,240,0.18)';
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.borderColor = 'var(--border)';
                                                e.currentTarget.style.background = 'var(--surface-1)';
                                                e.currentTarget.style.transform = 'translateY(0)';
                                                e.currentTarget.style.boxShadow = 'none';
                                            }}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0 flex-1">
                                                    <div className="flex items-center gap-2 mb-2"
                                                         style={{ color: 'var(--primary)' }}>
                                                        {icon}
                                                        <span className="text-[13px] font-semibold tracking-wide">{label}</span>
                                                    </div>
                                                    <p className="text-[14px] leading-relaxed"
                                                       style={{ color: 'var(--muted-foreground)' }}>
                                                        {prompt}
                                                    </p>
                                                </div>
                                                <ArrowUpRight
                                                    size={16}
                                                    className="shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                                    style={{ color: 'var(--primary)' }}
                                                />
                                            </div>
                                        </button>
                                    ))}
                                </div>

                                <p className="text-[12px] text-center mt-8"
                                   style={{ color: 'var(--muted-foreground)', opacity: 0.6 }}>
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
