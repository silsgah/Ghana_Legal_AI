'use client';

import React from 'react';
import { Scale, Plus, Trash2, Wifi, WifiOff, Loader2, Shield } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';
import { ConnectionStatus } from '@/hooks/use-chat';
import { useUsage } from '@/hooks/use-usage';

interface SidebarProps {
    experts: LegalExpert[];
    selectedExpertId: string;
    onSelectExpert: (id: string) => void;
    onReset: () => void;
    connectionStatus: ConnectionStatus;
    onReconnect: () => void;
    onUpgradeClick: () => void;
}

export function Sidebar({
    experts,
    selectedExpertId,
    onSelectExpert,
    onReset,
    connectionStatus,
    onReconnect,
    onUpgradeClick,
}: SidebarProps) {
    const selectedExpert = experts.find((p) => p.id === selectedExpertId);
    const { usage, loading } = useUsage();

    return (
        <div className="w-[280px] flex flex-col h-screen"
             style={{ background: 'var(--surface-1)', borderRight: '1px solid var(--border)' }}>
            {/* Brand Header */}
            <div className="p-5 pb-4" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-3 mb-5">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                         style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817)' }}>
                        <Scale size={18} className="text-black" />
                    </div>
                    <div>
                        <h1 className="font-bold text-[15px]" style={{ color: 'var(--foreground)' }}>
                            Ghana Legal AI
                        </h1>
                        <span className="text-[11px] font-medium tracking-wide uppercase"
                              style={{ color: 'var(--muted-foreground)' }}>
                            SaaS Platform
                        </span>
                    </div>
                </div>
                <button
                    onClick={onReset}
                    className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm text-left group"
                    style={{
                        border: '1px solid var(--border)',
                        color: 'var(--foreground)',
                        transition: 'all 0.2s ease',
                    }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'var(--primary)';
                        e.currentTarget.style.background = 'var(--primary-muted)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border)';
                        e.currentTarget.style.background = 'transparent';
                    }}
                >
                    <Plus size={16} style={{ color: 'var(--primary)' }} />
                    <span>New Consultation</span>
                </button>
            </div>

            {/* Connection Status */}
            <div className="px-5 py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className="flex items-center gap-2 text-xs">
                    {connectionStatus === 'connected' && (
                        <>
                            <div className="w-2 h-2 rounded-full" style={{ background: 'var(--success)' }} />
                            <span style={{ color: 'var(--success)' }}>System Online</span>
                        </>
                    )}
                    {connectionStatus === 'connecting' && (
                        <>
                            <Loader2 size={12} className="animate-spin" style={{ color: 'var(--warning)' }} />
                            <span style={{ color: 'var(--warning)' }}>Connecting...</span>
                        </>
                    )}
                    {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                        <>
                            <WifiOff size={12} style={{ color: 'var(--error)' }} />
                            <span style={{ color: 'var(--error)' }}>Offline</span>
                            <button
                                onClick={onReconnect}
                                className="ml-auto text-xs font-medium px-2 py-0.5 rounded"
                                style={{
                                    color: 'var(--primary)',
                                    background: 'var(--primary-muted)',
                                    transition: 'opacity 0.2s',
                                }}
                            >
                                Retry
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Experts List */}
            <div className="flex-1 overflow-y-auto px-3 py-4">
                <div className="text-[11px] font-semibold uppercase tracking-widest mb-3 px-3"
                     style={{ color: 'var(--muted-foreground)' }}>
                    Legal Experts
                </div>
                <div className="space-y-1">
                    {experts.map((expert) => {
                        const isSelected = selectedExpertId === expert.id;
                        return (
                            <button
                                key={expert.id}
                                onClick={() => onSelectExpert(expert.id)}
                                className={cn(
                                    'w-full flex items-center gap-3 px-3 py-3.5 rounded-xl text-sm text-left',
                                    'transition-all duration-200'
                                )}
                                style={{
                                    background: isSelected ? 'var(--primary-muted)' : 'transparent',
                                    color: isSelected ? 'var(--foreground)' : 'var(--muted-foreground)',
                                    border: isSelected ? '1px solid rgba(91,106,240,0.2)' : '1px solid transparent',
                                }}
                                onMouseEnter={(e) => {
                                    if (!isSelected) {
                                        e.currentTarget.style.background = 'var(--surface-2)';
                                        e.currentTarget.style.color = 'var(--foreground)';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isSelected) {
                                        e.currentTarget.style.background = 'transparent';
                                        e.currentTarget.style.color = 'var(--muted-foreground)';
                                    }
                                }}
                            >
                                {/* Avatar with accent ring */}
                                <div
                                    className="w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0"
                                    style={{
                                        background: `linear-gradient(135deg, ${expert.accentColor}22, ${expert.accentColor}44)`,
                                        border: isSelected
                                            ? `2px solid ${expert.accentColor}`
                                            : `2px solid ${expert.accentColor}33`,
                                        transition: 'all 0.2s ease',
                                    }}
                                >
                                    {expert.icon}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="font-semibold text-[13px] truncate">{expert.name}</div>
                                    <div className="text-[11px] truncate" style={{ color: 'var(--muted-foreground)' }}>
                                        {expert.field}
                                    </div>
                                </div>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Selected Expert Info Card */}
            {selectedExpert && (
                <div className="mx-3 mb-3 p-4 rounded-xl"
                     style={{
                         background: 'var(--surface-2)',
                         border: '1px solid var(--border)',
                     }}>
                    <div className="flex items-center gap-2 mb-2">
                        <Shield size={12} style={{ color: 'var(--ghana-gold)' }} />
                        <span className="text-[11px] font-semibold uppercase tracking-wider"
                              style={{ color: 'var(--ghana-gold)' }}>
                            Active Expert
                        </span>
                    </div>
                    <div className="font-semibold text-sm" style={{ color: 'var(--foreground)' }}>
                        {selectedExpert.name}
                    </div>
                    <div className="text-xs mt-1 italic leading-relaxed"
                         style={{ color: 'var(--muted-foreground)' }}>
                        &ldquo;{selectedExpert.tagline}&rdquo;
                    </div>
                </div>
            )}

            {/* Usage Quota Card */}
            <div className="mx-3 mb-3 p-4 rounded-xl"
                 style={{
                     background: 'var(--surface-2)',
                     border: '1px solid var(--border)',
                 }}>
                {loading || !usage ? (
                    <div className="flex flex-col items-center justify-center space-y-2 py-2">
                        <Loader2 size={16} className="animate-spin text-primary" />
                        <span className="text-[11px] text-muted-foreground">Loading Quota...</span>
                    </div>
                ) : (
                    <>
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[11px] font-semibold uppercase tracking-wider"
                                  style={{ color: 'var(--primary)' }}>
                                {usage.plan === 'professional' ? 'Pro Plan' : 
                                 usage.plan === 'enterprise' ? 'Enterprise' : 'Free Plan'}
                            </span>
                            {usage.plan === 'free' && (
                                <span className="text-[10px] font-medium px-2 py-0.5 rounded-full"
                                      style={{
                                          background: usage.remaining > 0 ? 'rgba(91,106,240,0.1)' : 'rgba(229,72,72,0.1)',
                                          color: usage.remaining > 0 ? 'var(--primary)' : 'var(--error)'
                                      }}>
                                    {usage.used_today}/{usage.daily_limit} Used
                                </span>
                            )}
                        </div>
                        
                        {usage.plan === 'free' && (
                            <div className="w-full rounded-full h-1.5 mt-2 mb-3" style={{ background: 'var(--surface-1)' }}>
                                <div className="h-1.5 rounded-full transition-all duration-500"
                                     style={{ 
                                         width: `${Math.min(100, (usage.used_today / usage.daily_limit) * 100)}%`,
                                         background: usage.remaining > 0 ? 'var(--primary)' : 'var(--error)'
                                     }} 
                                />
                            </div>
                        )}
                        
                        {usage.plan === 'free' && usage.remaining === 0 && (
                            <div className="text-[11px] mt-2 mb-2 leading-relaxed" style={{ color: 'var(--error)' }}>
                                Daily limit reached. Upgrade to Pro for unlimited queries.
                            </div>
                        )}
                        {usage.plan === 'free' && (
                             <button 
                                 onClick={onUpgradeClick} 
                                 className="w-full mt-1 py-2 rounded-lg text-[12px] font-semibold transition-all duration-200 hover:scale-[1.02]" 
                                 style={{ 
                                     background: 'var(--primary)', 
                                     color: 'white',
                                     boxShadow: '0 4px 14px rgba(91,106,240,0.25)'
                                 }}
                             >
                                 Upgrade to Pro
                             </button>
                        )}
                    </>
                )}
            </div>

            {/* Footer */}
            <div className="p-3" style={{ borderTop: '1px solid var(--border)' }}>
                <button
                    onClick={onReset}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm"
                    style={{ color: 'var(--muted-foreground)', transition: 'all 0.2s ease' }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'var(--error)';
                        e.currentTarget.style.background = 'rgba(229,72,72,0.08)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--muted-foreground)';
                        e.currentTarget.style.background = 'transparent';
                    }}
                >
                    <Trash2 size={14} />
                    <span>Clear History</span>
                </button>
            </div>
        </div>
    );
}
