'use client';

import React from 'react';
import { MessageSquare, Plus, Trash2, Wifi, WifiOff, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';
import { ConnectionStatus } from '@/hooks/use-chat';

interface SidebarProps {
    experts: LegalExpert[];
    selectedExpertId: string;
    onSelectExpert: (id: string) => void;
    onReset: () => void;
    connectionStatus: ConnectionStatus;
    onReconnect: () => void;
}

export function Sidebar({
    experts,
    selectedExpertId,
    onSelectExpert,
    onReset,
    connectionStatus,
    onReconnect,
}: SidebarProps) {
    const selectedExpert = experts.find((p) => p.id === selectedExpertId);

    return (
        <div className="w-[280px] bg-zinc-900 text-zinc-100 flex flex-col h-screen border-r border-zinc-800">
            {/* Header */}
            <div className="p-4 border-b border-zinc-800">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                        <MessageSquare size={16} className="text-white" />
                    </div>
                    <span className="font-semibold text-lg">Ghana Legal AI</span>
                </div>
                <button
                    onClick={onReset}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-lg border border-zinc-700 hover:bg-zinc-800 transition-all duration-200 text-sm text-left group"
                >
                    <Plus size={16} className="text-zinc-400 group-hover:text-white transition-colors" />
                    <span>New Chat</span>
                </button>
            </div>

            {/* Connection Status */}
            <div className="px-4 py-2 border-b border-zinc-800">
                <div className="flex items-center gap-2 text-xs">
                    {connectionStatus === 'connected' && (
                        <>
                            <Wifi size={12} className="text-emerald-400" />
                            <span className="text-emerald-400">Connected</span>
                        </>
                    )}
                    {connectionStatus === 'connecting' && (
                        <>
                            <Loader2 size={12} className="text-amber-400 animate-spin" />
                            <span className="text-amber-400">Connecting...</span>
                        </>
                    )}
                    {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                        <>
                            <WifiOff size={12} className="text-red-400" />
                            <span className="text-red-400">Disconnected</span>
                            <button
                                onClick={onReconnect}
                                className="ml-auto text-zinc-400 hover:text-white transition-colors"
                            >
                                Reconnect
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Experts List */}
            <div className="flex-1 overflow-y-auto px-3 py-4">
                <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-3 px-3">
                    Choose an Expert
                </div>
                <div className="space-y-1">
                    {experts.map((expert) => {
                        const isSelected = selectedExpertId === expert.id;
                        return (
                            <button
                                key={expert.id}
                                onClick={() => onSelectExpert(expert.id)}
                                className={cn(
                                    'w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm text-left transition-all duration-200',
                                    isSelected
                                        ? 'bg-zinc-800 text-white shadow-lg'
                                        : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-white'
                                )}
                            >
                                {/* Avatar */}
                                <div
                                    className={cn(
                                        'w-9 h-9 rounded-full flex items-center justify-center text-white font-medium text-sm flex-shrink-0 transition-transform',
                                        isSelected && 'scale-110'
                                    )}
                                    style={{
                                        background: `linear-gradient(135deg, ${expert.accentColor}88, ${expert.accentColor})`,
                                    }}
                                >
                                    {expert.icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="font-medium truncate">{expert.name}</div>
                                    <div className="text-xs text-zinc-500 truncate">{expert.field}</div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Selected Expert Info */}
            {selectedExpert && (
                <div className="p-4 border-t border-zinc-800 bg-zinc-800/50">
                    <div className="text-xs text-zinc-500 mb-1">Selected</div>
                    <div className="font-medium text-sm">{selectedExpert.name}</div>
                    <div className="text-xs text-zinc-400 italic mt-1">
                        &ldquo;{selectedExpert.tagline}&rdquo;
                    </div>
                </div>
            )}

            {/* Footer */}
            <div className="p-3 border-t border-zinc-800">
                <button
                    onClick={onReset}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-zinc-800 transition-colors text-sm text-zinc-400 hover:text-red-400"
                >
                    <Trash2 size={14} />
                    <span>Clear Conversations</span>
                </button>
            </div>
        </div>
    );
}
