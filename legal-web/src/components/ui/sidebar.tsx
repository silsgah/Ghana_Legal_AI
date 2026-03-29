'use client';

import React from 'react';
import Link from 'next/link';
import { Scale, Plus, Trash2, WifiOff, Loader2, Settings, PanelLeftClose, PanelLeft } from 'lucide-react';
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
    return (
        <div
            className="flex flex-col h-screen transition-all duration-300 ease-out"
            style={{
                width: collapsed ? '60px' : '260px',
                background: 'var(--surface-1)',
                borderRight: '1px solid var(--border)',
            }}
        >
            {/* Brand Header */}
            <div className="p-3 flex-shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
                <div className={cn(
                    'flex items-center mb-3',
                    collapsed ? 'justify-center' : 'gap-2.5'
                )}>
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                         style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817)' }}>
                        <Scale size={14} className="text-black" />
                    </div>
                    {!collapsed && (
                        <span className="font-bold text-[14px]" style={{ color: 'var(--foreground)' }}>
                            Ghana Legal AI
                        </span>
                    )}
                </div>
                {!collapsed ? (
                    <button
                        onClick={onReset}
                        className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] text-left"
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
                        <Plus size={14} style={{ color: 'var(--primary)' }} />
                        <span>New Consultation</span>
                    </button>
                ) : (
                    <button
                        onClick={onReset}
                        className="w-full flex items-center justify-center p-2 rounded-lg"
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
                        <Plus size={16} />
                    </button>
                )}
            </div>

            {/* Connection Status — always visible */}
            {!collapsed ? (
                <div className="px-4 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                    <div className="flex items-center gap-2 text-xs">
                        {connectionStatus === 'connected' && (
                            <>
                                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--success)' }} />
                                <span style={{ color: 'var(--success)' }}>Connected</span>
                            </>
                        )}
                        {connectionStatus === 'connecting' && (
                            <>
                                <Loader2 size={11} className="animate-spin" style={{ color: 'var(--warning)' }} />
                                <span style={{ color: 'var(--warning)' }}>Connecting...</span>
                            </>
                        )}
                        {(connectionStatus === 'disconnected' || connectionStatus === 'error') && (
                            <>
                                <WifiOff size={11} style={{ color: 'var(--error)' }} />
                                <span style={{ color: 'var(--error)' }}>Offline</span>
                                <button onClick={onReconnect}
                                        className="ml-auto text-[11px] font-medium px-2 py-0.5 rounded"
                                        style={{ color: 'var(--primary)', background: 'var(--primary-muted)' }}>
                                    Retry
                                </button>
                            </>
                        )}
                    </div>
                </div>
            ) : (
                <div className="flex justify-center py-2" style={{ borderBottom: '1px solid var(--border)' }}>
                    {connectionStatus === 'connected' ? (
                        <div className="w-2.5 h-2.5 rounded-full" style={{ background: 'var(--success)' }} title="Connected" />
                    ) : connectionStatus === 'connecting' ? (
                        <Loader2 size={12} className="animate-spin" style={{ color: 'var(--warning)' }} />
                    ) : (
                        <button onClick={onReconnect} title="Offline — click to retry">
                            <WifiOff size={12} style={{ color: 'var(--error)' }} />
                        </button>
                    )}
                </div>
            )}

            {/* Experts List */}
            <div className="flex-1 overflow-y-auto px-2 py-3">
                {!collapsed && (
                    <div className="text-[10px] font-semibold uppercase tracking-widest mb-2 px-2.5"
                         style={{ color: 'var(--muted-foreground)' }}>
                        Legal Experts
                    </div>
                )}
                <div className="space-y-0.5">
                    {experts.map((expert) => {
                        const isSelected = selectedExpertId === expert.id;
                        return (
                            <button
                                key={expert.id}
                                onClick={() => onSelectExpert(expert.id)}
                                className={cn(
                                    'w-full flex items-center rounded-lg text-sm text-left',
                                    'transition-all duration-150',
                                    collapsed ? 'justify-center p-2' : 'gap-2.5 px-2.5 py-2.5',
                                )}
                                style={{
                                    background: isSelected ? 'var(--primary-muted)' : 'transparent',
                                    color: isSelected ? 'var(--foreground)' : 'var(--muted-foreground)',
                                    border: isSelected ? '1px solid rgba(91,106,240,0.15)' : '1px solid transparent',
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
                                    collapsed ? 'w-9 h-9' : 'w-8 h-8',
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
                                        <div className="font-semibold text-[12px] truncate">{expert.name}</div>
                                        <div className="text-[10px] truncate" style={{ color: 'var(--muted-foreground)' }}>
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
            <div className="p-2 space-y-0.5 flex-shrink-0" style={{ borderTop: '1px solid var(--border)' }}>
                {!collapsed ? (
                    <>
                        <Link href="/admin"
                              className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[12px]"
                              style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                              onMouseEnter={(e) => {
                                  e.currentTarget.style.color = 'var(--primary)';
                                  e.currentTarget.style.background = 'var(--primary-muted)';
                              }}
                              onMouseLeave={(e) => {
                                  e.currentTarget.style.color = 'var(--muted-foreground)';
                                  e.currentTarget.style.background = 'transparent';
                              }}>
                            <Settings size={13} />
                            <span>Admin</span>
                        </Link>
                        <button onClick={onReset}
                                className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[12px]"
                                style={{ color: 'var(--muted-foreground)', transition: 'all 0.15s ease' }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.color = 'var(--error)';
                                    e.currentTarget.style.background = 'rgba(229,72,72,0.06)';
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.color = 'var(--muted-foreground)';
                                    e.currentTarget.style.background = 'transparent';
                                }}>
                            <Trash2 size={13} />
                            <span>Clear History</span>
                        </button>
                    </>
                ) : (
                    <>
                        <Link href="/admin"
                              className="w-full flex items-center justify-center p-2 rounded-lg"
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
                            <Settings size={15} />
                        </Link>
                        <button onClick={onReset}
                                className="w-full flex items-center justify-center p-2 rounded-lg"
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
                            <Trash2 size={15} />
                        </button>
                    </>
                )}
                {/* Collapse toggle */}
                <button
                    onClick={onToggleCollapse}
                    className="w-full flex items-center justify-center p-2 rounded-lg mt-1"
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
                    {collapsed ? <PanelLeft size={15} /> : <PanelLeftClose size={15} />}
                </button>
            </div>
        </div>
    );
}
