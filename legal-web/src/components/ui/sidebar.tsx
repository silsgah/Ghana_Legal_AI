'use client';

import React from 'react';
import Link from 'next/link';
import { Scale, Plus, Trash2, WifiOff, Loader2, Settings, PanelLeftClose, PanelLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';
import { ConnectionStatus } from '@/hooks/use-chat';
import { useUser } from '@clerk/nextjs';

interface SidebarProps {
    experts: LegalExpert[];
    selectedExpertId: string;
    onSelectExpert: (id: string) => void;
    onReset: () => void;
    connectionStatus: ConnectionStatus;
    onReconnect: () => void;
    onUpgradeClick: () => void;
    collapsed: boolean;
    onToggleCollapse: () => void;
}

export function Sidebar({
    experts,
    selectedExpertId,
    onSelectExpert,
    onReset,
    connectionStatus,
    onReconnect,
    collapsed,
    onToggleCollapse,
}: SidebarProps) {
    const { user } = useUser();
    const isAdmin = user?.publicMetadata?.role === 'admin' || user?.publicMetadata?.role === 'ADMIN';

    return (
        <div
            className="flex flex-col h-screen transition-all duration-300 ease-out"
            style={{
                width: collapsed ? '64px' : '280px',
                background: 'var(--surface-1)',
                borderRight: '1px solid var(--border)',
            }}
        >
            {/* Brand Header */}
            <div className="p-4 flex-shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className={cn(
                    'flex items-center mb-4',
                    collapsed ? 'justify-center' : 'gap-3'
                )}>
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                         style={{
                             background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)',
                             boxShadow: '0 4px 12px rgba(240,192,64,0.25)',
                         }}>
                        <Scale size={16} className="text-black" />
                    </div>
                    {!collapsed && (
                        <div>
                            <span className="font-bold text-[16px] block leading-tight" style={{ color: 'var(--foreground)' }}>
                                LexGH
                            </span>
                            <span className="text-[11px] font-medium" style={{ color: 'var(--ghana-gold)', opacity: 0.8 }}>
                                Legal Research
                            </span>
                        </div>
                    )}
                </div>
                {!collapsed ? (
                    <button
                        onClick={onReset}
                        className="w-full flex items-center gap-2.5 px-3.5 py-3 rounded-xl text-[14px] text-left font-medium"
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
                ) : (
                    <button
                        onClick={onReset}
                        className="w-full flex items-center justify-center p-2.5 rounded-xl"
                        style={{
                            border: '1px solid var(--border)',
                            color: 'var(--primary)',
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
                        title="New Consultation"
                    >
                        <Plus size={18} />
                    </button>
                )}
            </div>

            {/* Connection Status — always visible */}
            {!collapsed ? (
                <div className="px-4 py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2 text-[13px]">
                        {connectionStatus === 'connected' && (
                            <>
                                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--success)' }} />
                                <span style={{ color: 'var(--success)' }}>Connected</span>
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
                                <button onClick={onReconnect}
                                        className="ml-auto text-[12px] font-semibold px-2.5 py-1 rounded-lg"
                                        style={{ color: 'var(--primary)', background: 'var(--primary-muted)' }}>
                                    Retry
                                </button>
                            </>
                        )}
                    </div>
                </div>
            ) : (
                <div className="flex justify-center py-2.5" style={{ borderBottom: '1px solid var(--border)' }}>
                    {connectionStatus === 'connected' ? (
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: 'var(--success)' }} title="Connected" />
                    ) : connectionStatus === 'connecting' ? (
                        <Loader2 size={13} className="animate-spin" style={{ color: 'var(--warning)' }} />
                    ) : (
                        <button onClick={onReconnect} title="Offline — click to retry">
                            <WifiOff size={13} style={{ color: 'var(--error)' }} />
                        </button>
                    )}
                </div>
            )}

            {/* Experts List */}
            <div className="flex-1 overflow-y-auto px-2.5 py-4">
                {!collapsed && (
                    <div className="text-[11px] font-semibold uppercase tracking-widest mb-3 px-3"
                         style={{ color: 'var(--muted-foreground)' }}>
                        Legal Experts
                    </div>
                )}
                <div className="space-y-1">
                    {experts.map((expert) => {
                        const isSelected = selectedExpertId === expert.id;
                        return (
                            <button
                                key={expert.id}
                                onClick={() => onSelectExpert(expert.id)}
                                className={cn(
                                    'w-full flex items-center rounded-xl text-left',
                                    'transition-all duration-150',
                                    collapsed ? 'justify-center p-2.5' : 'gap-3 px-3 py-3',
                                )}
                                style={{
                                    background: isSelected ? 'var(--primary-muted)' : 'transparent',
                                    color: isSelected ? 'var(--foreground)' : 'var(--muted-foreground)',
                                    border: isSelected ? '1px solid rgba(98,114,240,0.15)' : '1px solid transparent',
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
                                title={collapsed ? expert.name : undefined}
                            >
                                <div className={cn(
                                    'rounded-full flex items-center justify-center text-base flex-shrink-0',
                                    collapsed ? 'w-10 h-10' : 'w-9 h-9',
                                )}
                                     style={{
                                         background: `linear-gradient(135deg, ${expert.accentColor}22, ${expert.accentColor}44)`,
                                         border: isSelected
                                             ? `2px solid ${expert.accentColor}`
                                             : `2px solid ${expert.accentColor}22`,
                                     }}>
                                    {expert.icon}
                                </div>
                                {!collapsed && (
                                    <div className="flex-1 min-w-0">
                                        <div className="font-semibold text-[14px] truncate">{expert.name}</div>
                                        <div className="text-[12px] truncate" style={{ color: 'var(--muted-foreground)' }}>
                                            {expert.field}
                                        </div>
                                    </div>
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Footer */}
            <div className="p-2.5 space-y-1 flex-shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
                {!collapsed ? (
                    <>
                        {isAdmin && (
                            <Link href="/admin"
                                  className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[13px] font-medium"
                                  style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                                  onMouseEnter={(e) => {
                                      e.currentTarget.style.color = 'var(--primary)';
                                      e.currentTarget.style.background = 'var(--primary-muted)';
                                  }}
                                  onMouseLeave={(e) => {
                                      e.currentTarget.style.color = 'var(--muted-foreground)';
                                      e.currentTarget.style.background = 'transparent';
                                  }}>
                                <Settings size={15} />
                                <span>Admin</span>
                            </Link>
                        )}
                        <button onClick={onReset}
                                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-[13px] font-medium"
                                style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.color = 'var(--error)';
                                    e.currentTarget.style.background = 'rgba(229,72,72,0.06)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.color = 'var(--muted-foreground)';
                                    e.currentTarget.style.background = 'transparent';
                                }}>
                            <Trash2 size={15} />
                            <span>Clear History</span>
                        </button>
                    </>
                ) : (
                    <>
                        {isAdmin && (
                            <Link href="/admin"
                                  className="w-full flex items-center justify-center p-2.5 rounded-xl"
                                  style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                                  onMouseEnter={(e) => {
                                      e.currentTarget.style.color = 'var(--primary)';
                                      e.currentTarget.style.background = 'var(--primary-muted)';
                                  }}
                                  onMouseLeave={(e) => {
                                      e.currentTarget.style.color = 'var(--muted-foreground)';
                                      e.currentTarget.style.background = 'transparent';
                                  }}
                                  title="Admin">
                                <Settings size={16} />
                            </Link>
                        )}
                        <button onClick={onReset}
                                className="w-full flex items-center justify-center p-2.5 rounded-xl"
                                style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.color = 'var(--error)';
                                    e.currentTarget.style.background = 'rgba(229,72,72,0.06)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.color = 'var(--muted-foreground)';
                                    e.currentTarget.style.background = 'transparent';
                                }}
                                title="Clear History">
                            <Trash2 size={16} />
                        </button>
                    </>
                )}
                {/* Collapse toggle */}
                <button
                    onClick={onToggleCollapse}
                    className="w-full flex items-center justify-center p-2.5 rounded-xl mt-1"
                    style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                    onMouseEnter={(e) => {
                        e.currentTarget.style.color = 'var(--foreground)';
                        e.currentTarget.style.background = 'var(--surface-2)';
                    }}
                    onMouseLeave={(e) => {
                        e.currentTarget.style.color = 'var(--muted-foreground)';
                        e.currentTarget.style.background = 'transparent';
                    }}
                    title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                    {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
                </button>
            </div>
        </div>
    );
}
