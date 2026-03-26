'use client';

import React, { useState, useEffect, useRef } from 'react';
import { UserButton } from '@clerk/nextjs';
import { Sidebar } from '@/components/ui/sidebar';
import { MessageBubble } from '@/components/ui/message-bubble';
import { ChatInput } from '@/components/ui/chat-input';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { UpgradeModal } from '@/components/ui/upgrade-modal';
import { Menu, Scale, BookOpen, Gavel, ScrollText } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { LEGAL_EXPERTS, getLegalExpert } from '@/lib/legal-experts';

const SUGGESTED_PROMPTS = [
    {
        icon: <BookOpen size={15} />,
        label: 'Constitutional Rights',
        prompt: 'What does the 1992 Constitution say about fundamental human rights and freedoms?',
    },
    {
        icon: <Gavel size={15} />,
        label: 'Landmark Case',
        prompt: 'Summarize the Tuffuor v Attorney General case and its significance',
    },
    {
        icon: <ScrollText size={15} />,
        label: 'Court Hierarchy',
        prompt: 'Explain the hierarchy of courts in Ghana and their jurisdictions',
    },
    {
        icon: <Scale size={15} />,
        label: 'Chief Justice',
        prompt: 'How is the Chief Justice appointed and what are the qualifications?',
    },
];

export default function ChatPage() {
    const [selectedExpertId, setSelectedExpertId] = useState('constitutional');
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isUpgradeModalOpen, setIsUpgradeModalOpen] = useState(false);

    const selectedExpert = getLegalExpert(selectedExpertId);

    const {
        messages,
        sendMessage,
        resetChat,
        isStreaming,
        connectionStatus,
        reconnect,
    } = useChat({ expertId: selectedExpertId });

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
                className="lg:hidden fixed top-4 left-4 z-50 p-2.5 rounded-xl shadow-lg"
                style={{
                    background: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                }}
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                aria-label="Toggle sidebar"
            >
                <Menu size={20} style={{ color: 'var(--foreground)' }} />
            </button>

            {/* Sidebar */}
            <div
                className={`${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
                    } lg:translate-x-0 fixed lg:relative z-40 h-full transition-transform duration-300 ease-out`}
            >
                <Sidebar
                    experts={LEGAL_EXPERTS}
                    selectedExpertId={selectedExpertId}
                    onSelectExpert={handleSelectExpert}
                    onReset={resetChat}
                    connectionStatus={connectionStatus}
                    onReconnect={reconnect}
                    onUpgradeClick={() => setIsUpgradeModalOpen(true)}
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
                <header
                    className="h-14 flex items-center justify-between px-4 lg:px-6 sticky top-0 z-10"
                    style={{
                        background: 'var(--surface-1)',
                        borderBottom: '1px solid var(--border)',
                    }}
                >
                    <div className="lg:pl-0 pl-12 flex items-center gap-3">
                        <div
                            className="w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: selectedExpert?.accentColor }}
                        />
                        <h1 className="font-semibold text-[14px]"
                            style={{ color: 'var(--foreground)' }}>
                            {selectedExpert?.name}
                        </h1>
                    </div>
                    <div className="flex items-center gap-4">
                        <span className="hidden lg:inline text-[12px]"
                              style={{ color: 'var(--muted-foreground)' }}>
                            {selectedExpert?.field} &bull; {selectedExpert?.era}
                        </span>
                        <UserButton />
                    </div>
                </header>

                {/* Messages Area */}
                <div className="flex-1 overflow-y-auto">
                    {messages.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center p-8 text-center animate-float-in">
                            <div
                                className="w-20 h-20 rounded-2xl flex items-center justify-center mb-6"
                                style={{
                                    background: `linear-gradient(135deg, ${selectedExpert?.accentColor || 'var(--primary)'}33, ${selectedExpert?.accentColor || 'var(--primary)'}88)`,
                                    border: `1px solid ${selectedExpert?.accentColor || 'var(--primary)'}44`,
                                    boxShadow: `0 8px 32px ${selectedExpert?.accentColor || 'var(--primary)'}22`,
                                }}
                            >
                                <Scale size={36} style={{ color: selectedExpert?.accentColor || 'var(--primary)' }} />
                            </div>

                            <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--foreground)' }}>
                                {selectedExpert?.name}
                            </h2>
                            <p className="text-sm max-w-md mb-2" style={{ color: 'var(--muted-foreground)' }}>
                                {selectedExpert?.tagline}
                            </p>
                            <p className="text-xs mb-10" style={{ color: 'var(--muted-foreground)', opacity: 0.6 }}>
                                {selectedExpert?.era}
                            </p>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
                                {SUGGESTED_PROMPTS.map(({ icon, label, prompt }) => (
                                    <button
                                        key={prompt}
                                        onClick={() => sendMessage(prompt)}
                                        className="px-4 py-3.5 text-sm text-left rounded-xl group"
                                        style={{
                                            background: 'var(--surface-1)',
                                            border: '1px solid var(--border)',
                                            color: 'var(--foreground)',
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
                                        <div className="flex items-center gap-2 mb-1" style={{ color: 'var(--primary)' }}>
                                            {icon}
                                            <span className="font-semibold text-[12px]">{label}</span>
                                        </div>
                                        <span className="text-[13px] leading-snug" style={{ color: 'var(--muted-foreground)' }}>
                                            {prompt}
                                        </span>
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
                                />
                            ))}
                            {isStreaming && messages[messages.length - 1]?.role === 'user' && (
                                <TypingIndicator
                                    expertName={selectedExpert?.name}
                                    accentColor={selectedExpert?.accentColor}
                                />
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <ChatInput
                    onSend={sendMessage}
                    disabled={isStreaming || connectionStatus !== 'connected'}
                    expertName={selectedExpert?.name}
                />
            </div>
        </div>
    );
}
