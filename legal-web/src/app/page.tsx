'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Sidebar } from '@/components/ui/sidebar';
import { MessageBubble } from '@/components/ui/message-bubble';
import { ChatInput } from '@/components/ui/chat-input';
import { TypingIndicator } from '@/components/ui/typing-indicator';
import { Menu, Sparkles, Variable } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { LEGAL_EXPERTS, getLegalExpert } from '@/lib/legal-experts';

export default function Home() {
  const [selectedExpertId, setSelectedExpertId] = useState('constitutional');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

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

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming]);

  const handleSelectExpert = (id: string) => {
    setSelectedExpertId(id);
    setIsSidebarOpen(false); // Close on mobile
  };

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* Mobile Sidebar Toggle */}
      <button
        className="lg:hidden fixed top-4 left-4 z-50 p-2.5 bg-white dark:bg-zinc-800 rounded-xl shadow-lg border border-zinc-200 dark:border-zinc-700"
        onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        aria-label="Toggle sidebar"
      >
        <Menu size={20} className="text-zinc-600 dark:text-zinc-300" />
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
        />
      </div>

      {/* Mobile Overlay */}
      {isSidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col h-full w-full relative overflow-hidden">
        {/* Header */}
        <header className="h-16 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-center lg:justify-between px-4 lg:px-8 bg-white/90 dark:bg-zinc-900/90 backdrop-blur-sm sticky top-0 z-10">
          <div className="lg:pl-0 pl-12">
            <h1 className="font-semibold text-lg text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: selectedExpert?.accentColor }}
              />
              {selectedExpert?.name}
            </h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 hidden sm:block">
              {selectedExpert?.field} • {selectedExpert?.era}
            </p>
          </div>
          <div className="hidden lg:flex items-center gap-2 text-xs text-zinc-400">
            <Variable size={14} />
            <span>Ghana Legal AI Assistant</span>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center p-8 text-center">
              <div
                className="w-20 h-20 rounded-2xl flex items-center justify-center mb-6 shadow-lg"
                style={{
                  background: selectedExpert
                    ? `linear-gradient(135deg, ${selectedExpert.accentColor}44, ${selectedExpert.accentColor})`
                    : 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                }}
              >
                <Sparkles size={36} className="text-white" />
              </div>
              <h2 className="text-2xl font-bold text-zinc-800 dark:text-zinc-100 mb-3">
                Chat with {selectedExpert?.name}
              </h2>
              <p className="text-zinc-500 dark:text-zinc-400 max-w-md mb-8">
                {selectedExpert?.tagline}. Ask about the constitution, case law, or legal history of Ghana.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
                {[
                  'What does the Constitution say about free speech?',
                  'Explain the hierarchy of courts in Ghana',
                  'Summarize the Tuffuor v Attorney General case',
                  'How is the Chief Justice appointed?',
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => sendMessage(prompt)}
                    className="px-4 py-3 text-sm text-left bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-xl hover:border-indigo-300 dark:hover:border-indigo-600 hover:shadow-md transition-all duration-200 text-zinc-600 dark:text-zinc-300"
                  >
                    {prompt}
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
