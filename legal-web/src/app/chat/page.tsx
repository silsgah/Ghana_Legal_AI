'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { UserButton } from '@clerk/nextjs';
import { Sidebar } from '@/components/ui/sidebar';
import { MessageBubble } from '@/components/ui/message-bubble';
import { ChatInput } from '@/components/ui/chat-input';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { UpgradeModal } from '@/components/ui/upgrade-modal';
import { Menu, Scale, BookOpen, Gavel, ScrollText, Sparkles, Zap, Crown } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { useUsage } from '@/hooks/use-usage';
import { LEGAL_EXPERTS, getLegalExpert } from '@/lib/legal-experts';

const SUGGESTED_PROMPTS = [
    {
        icon: <BookOpen size={14} />,
        label: 'Constitutional Rights',
        prompt: 'What does the 1992 Constitution say about fundamental human rights and freedoms?',
    },
    {
        icon: <Gavel size={14} />,
        label: 'Landmark Case',
        prompt: 'Summarize the Tuffuor v Attorney General case and its significance',
    },
    {
        icon: <ScrollText size={14} />,
        label: 'Court Hierarchy',
        prompt: 'Explain the hierarchy of courts in Ghana and their jurisdictions',
    },
    {
        icon: <Scale size={14} />,
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
                className="lg:hidden fixed top-3 left-3 z-50 p-2.5 rounded-xl"
                style={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    boxShadow: 'var(--shadow-md)',
                }}
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label="Toggle sidebar"
            >
                <Menu size={18} style={{ color: 'var(--foreground)' }} />
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
                    style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)' }}
                    onClick={() => setIsSidebarOpen(false)}
                />
            )}

            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden">
                {/* Header */}
                <header className="h-13 flex items-center justify-between px-4 lg:px-6 flex-shrink-0"
                        style={{
                            background: 'var(--surface-1)',
                            borderBottom: '1px solid var(--border)',
                        }}>
                    <div className="lg:pl-0 pl-12 flex items-center gap-3">
                        <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs"
                             style={{
                                 background: `linear-gradient(135deg, ${selectedExpert?.accentColor}33, ${selectedExpert?.accentColor}88)`,
                                 border: `1.5px solid ${selectedExpert?.accentColor}44`,
                             }}>
                            {selectedExpert?.icon}
                        </div>
                        <div>
                            <h1 className="font-semibold text-[13px] leading-tight"
                                style={{ color: 'var(--foreground)' }}>
                                {selectedExpert?.name}
                            </h1>
                            <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                {selectedExpert?.field}
                            </span>
                        </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                        {/* Plan & Usage Badge */}
                        {usage && (
                            <div className="hidden sm:flex items-center gap-2">
                                {usage.plan === 'free' ? (
                                    <>
                                        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
                                             style={{ background: 'var(--surface-2)' }}>
                                            <Zap size={10} style={{ color: 'var(--ghana-gold)' }} />
                                            <span className="text-[10px] font-semibold"
                                                  style={{ color: usage.remaining > 0 ? 'var(--foreground)' : 'var(--error)' }}>
                                                {usage.used_today}/{usage.daily_limit} used
                                            </span>
                                        </div>
                                        <button onClick={() => setIsUpgradeModalOpen(true)}
                                                className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-semibold"
                                                style={{
                                                    background: 'linear-gradient(135deg, var(--primary), #8b5cf6)',
                                                    color: '#fff',
                                                    transition: 'opacity 0.2s',
                                                }}>
                                            <Crown size={10} />
                                            Upgrade
                                        </button>
                                    </>
                                ) : (
                                    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full"
                                         style={{ background: 'rgba(91,106,240,0.1)' }}>
                                        <Crown size={10} style={{ color: 'var(--primary)' }} />
                                        <span className="text-[10px] font-semibold" style={{ color: 'var(--primary)' }}>
                                            {usage.plan === 'professional' ? 'Pro' : 'Enterprise'}
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                        {/* Connection Status */}
                        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full"
                             style={{ background: 'var(--surface-2)' }}>
                            <div className="w-1.5 h-1.5 rounded-full animate-pulse"
                                 style={{
                                     background: connectionStatus === 'connected' ? 'var(--success)'
                                         : connectionStatus === 'connecting' ? 'var(--warning)'
                                         : 'var(--error)',
                                 }} />
                            <span className="text-[10px] font-medium"
                                  style={{ color: 'var(--muted-foreground)' }}>
                                {connectionStatus === 'connected' ? 'Online'
                                    : connectionStatus === 'connecting' ? 'Connecting...'
                                    : 'Offline'}
                            </span>
                            {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                                <button onClick={reconnect}
                                        className="text-[10px] font-semibold ml-0.5"
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
                        <div className="h-full flex flex-col items-center justify-center p-6 animate-float-in">
                            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
                                 style={{
                                     background: `linear-gradient(135deg, ${selectedExpert?.accentColor || 'var(--primary)'}22, ${selectedExpert?.accentColor || 'var(--primary)'}55)`,
                                     border: `1px solid ${selectedExpert?.accentColor || 'var(--primary)'}33`,
                                 }}>
                                <Scale size={28} style={{ color: selectedExpert?.accentColor || 'var(--primary)' }} />
                            </div>

                            <h2 className="text-xl font-bold mb-1.5" style={{ color: 'var(--foreground)' }}>
                                {selectedExpert?.name}
                            </h2>
                            <p className="text-sm max-w-sm text-center mb-1"
                               style={{ color: 'var(--muted-foreground)' }}>
                                {selectedExpert?.tagline}
                            </p>
                            <div className="flex items-center gap-1.5 mb-8">
                                <Sparkles size={11} style={{ color: 'var(--ghana-gold)' }} />
                                <span className="text-[11px] font-medium" style={{ color: 'var(--muted-foreground)', opacity: 0.7 }}>
                                    {selectedExpert?.era}
                                </span>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-lg w-full">
                                {SUGGESTED_PROMPTS.map(({ icon, label, prompt }) => (
                                    <button
                                        key={prompt}
                                        onClick={() => sendMessage(prompt)}
                                        className="px-3.5 py-3 text-left rounded-xl group"
                                        style={{
                                            background: 'var(--surface-1)',
                                            border: '1px solid var(--border)',
                                            transition: 'all 0.2s ease',
                                        }}
                                        onMouseEnter={(e) => {
                                            e.currentTarget.style.borderColor = 'var(--primary)';
                                            e.currentTarget.style.background = 'var(--primary-muted)';
                                            e.currentTarget.style.transform = 'translateY(-1px)';
                                        }}
                                        onMouseLeave={(e) => {
                                            e.currentTarget.style.borderColor = 'var(--border)';
                                            e.currentTarget.style.background = 'var(--surface-1)';
                                            e.currentTarget.style.transform = 'translateY(0)';
                                        }}
                                    >
                                        <div className="flex items-center gap-1.5 mb-1"
                                             style={{ color: 'var(--primary)' }}>
                                            {icon}
                                            <span className="text-[11px] font-semibold">{label}</span>
                                        </div>
                                        <p className="text-[12px] leading-snug"
                                           style={{ color: 'var(--muted-foreground)' }}>
                                            {prompt}
                                        </p>
                                    </button>
                                ))}
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
                            <div ref={messagesEndRef} className="h-4" />
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
