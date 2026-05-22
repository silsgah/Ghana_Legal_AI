'use client';

import React from 'react';
import Link from 'next/link';
import {
    Scale, Plus, Trash2, WifiOff, Loader2, Settings,
    PanelLeftClose, PanelLeft,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';
import { ConnectionStatus } from '@/hooks/use-chat';
import { useUser } from '@clerk/nextjs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

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

function ConnectionPill({
    status,
    onReconnect,
    collapsed,
}: {
    status: ConnectionStatus;
    onReconnect: () => void;
    collapsed: boolean;
}) {
    if (collapsed) {
        return (
            <div className="flex justify-center py-2.5 border-b border-border">
                {status === 'connected' && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <div className="w-2.5 h-2.5 rounded-full bg-[var(--ghana-green)] shadow-[0_0_6px_var(--ghana-green)]" />
                        </TooltipTrigger>
                        <TooltipContent side="right">Connected</TooltipContent>
                    </Tooltip>
                )}
                {status === 'connecting' && (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--ghana-gold)]" />
                )}
                {(status === 'disconnected' || status === 'error') && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <button onClick={onReconnect} className="text-destructive">
                                <WifiOff className="h-3.5 w-3.5" />
                            </button>
                        </TooltipTrigger>
                        <TooltipContent side="right">Offline — click to retry</TooltipContent>
                    </Tooltip>
                )}
            </div>
        );
    }

    return (
        <div className="px-4 py-2.5 border-b border-border">
            <div className="flex items-center gap-2 text-[13px]">
                {status === 'connected' && (
                    <>
                        <div className="w-2 h-2 rounded-full bg-[var(--ghana-green)]" />
                        <span className="text-[var(--ghana-green)] font-medium">Connected</span>
                    </>
                )}
                {status === 'connecting' && (
                    <>
                        <Loader2 className="h-3 w-3 animate-spin text-[var(--ghana-gold)]" />
                        <span className="text-[var(--ghana-gold)] font-medium">Connecting…</span>
                    </>
                )}
                {(status === 'disconnected' || status === 'error') && (
                    <>
                        <WifiOff className="h-3 w-3 text-destructive" />
                        <span className="text-destructive font-medium">Offline</span>
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={onReconnect}
                            className="ml-auto h-7 px-2 text-[12px] text-primary hover:bg-[color:color-mix(in_oklch,var(--primary)_12%,transparent)]"
                        >
                            Retry
                        </Button>
                    </>
                )}
            </div>
        </div>
    );
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
            className={cn(
                'flex flex-col h-screen bg-card border-r border-border transition-[width] duration-300 ease-out',
                collapsed ? 'w-16' : 'w-72'
            )}
        >
            {/* Brand + New Consultation */}
            <div className="p-3 border-b border-border space-y-3">
                <div className={cn('flex items-center', collapsed ? 'justify-center' : 'gap-3 px-1')}>
                    <div
                        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-[0_4px_12px_rgba(240,192,64,0.25)]"
                        style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #d4a017)' }}
                    >
                        <Scale className="h-4 w-4 text-black" />
                    </div>
                    {!collapsed && (
                        <div className="min-w-0">
                            <div className="font-bold text-[15px] leading-tight">LexGH</div>
                            <div className="text-[11px] font-medium text-[var(--ghana-gold)]/80">
                                Legal Research
                            </div>
                        </div>
                    )}
                </div>

                {collapsed ? (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="outline"
                                size="icon"
                                onClick={onReset}
                                className="w-full rounded-xl text-primary border-border hover:border-primary hover:bg-[color:color-mix(in_oklch,var(--primary)_10%,transparent)]"
                            >
                                <Plus className="h-4 w-4" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="right">New Consultation</TooltipContent>
                    </Tooltip>
                ) : (
                    <Button
                        variant="outline"
                        onClick={onReset}
                        className="w-full justify-start gap-2 rounded-xl hover:border-primary hover:bg-[color:color-mix(in_oklch,var(--primary)_10%,transparent)]"
                    >
                        <Plus className="h-4 w-4 text-primary" />
                        <span className="font-medium">New Consultation</span>
                    </Button>
                )}
            </div>

            <ConnectionPill status={connectionStatus} onReconnect={onReconnect} collapsed={collapsed} />

            {/* Experts list */}
            <div className="flex-1 overflow-y-auto px-2 py-3">
                {!collapsed && (
                    <div className="text-[11px] font-semibold uppercase tracking-widest mb-2 px-2 text-muted-foreground">
                        Legal Experts
                    </div>
                )}
                <div className="space-y-1">
                    {experts.map((expert) => {
                        const isSelected = selectedExpertId === expert.id;
                        const button = (
                            <button
                                key={expert.id}
                                onClick={() => onSelectExpert(expert.id)}
                                className={cn(
                                    'group w-full flex items-center rounded-lg text-left transition-colors duration-150 border',
                                    collapsed ? 'justify-center p-2' : 'gap-3 px-2.5 py-2.5',
                                    isSelected
                                        ? 'bg-[color:color-mix(in_oklch,var(--primary)_12%,transparent)] border-[color:color-mix(in_oklch,var(--primary)_25%,transparent)] text-foreground'
                                        : 'border-transparent text-muted-foreground hover:bg-accent hover:text-foreground'
                                )}
                            >
                                <div
                                    className={cn(
                                        'rounded-full flex items-center justify-center text-base flex-shrink-0 transition-all',
                                        collapsed ? 'w-9 h-9' : 'w-9 h-9'
                                    )}
                                    style={{
                                        background: `linear-gradient(135deg, ${expert.accentColor}22, ${expert.accentColor}44)`,
                                        border: isSelected
                                            ? `2px solid ${expert.accentColor}`
                                            : `2px solid ${expert.accentColor}22`,
                                    }}
                                >
                                    {expert.icon}
                                </div>
                                {!collapsed && (
                                    <div className="flex-1 min-w-0">
                                        <div className="font-semibold text-[13.5px] truncate">{expert.name}</div>
                                        <div className="text-[11.5px] truncate text-muted-foreground">
                                            {expert.field}
                                        </div>
                                    </div>
                                )}
                            </button>
                        );

                        if (collapsed) {
                            return (
                                <Tooltip key={expert.id}>
                                    <TooltipTrigger asChild>{button}</TooltipTrigger>
                                    <TooltipContent side="right">
                                        <div className="font-semibold">{expert.name}</div>
                                        <div className="text-[11px] text-muted-foreground">{expert.field}</div>
                                    </TooltipContent>
                                </Tooltip>
                            );
                        }
                        return button;
                    })}
                </div>
            </div>

            {/* Footer */}
            <div className="p-2 border-t border-border space-y-1">
                {collapsed ? (
                    <>
                        {isAdmin && (
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button asChild variant="ghost" size="icon" className="w-full">
                                        <Link href="/admin">
                                            <Settings className="h-4 w-4" />
                                        </Link>
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="right">Admin</TooltipContent>
                            </Tooltip>
                        )}
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={onReset}
                                    className="w-full hover:text-destructive hover:bg-[color:color-mix(in_oklch,var(--destructive)_10%,transparent)]"
                                >
                                    <Trash2 className="h-4 w-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="right">Clear History</TooltipContent>
                        </Tooltip>
                        <Separator className="my-1" />
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="ghost" size="icon" onClick={onToggleCollapse} className="w-full">
                                    <PanelLeft className="h-4 w-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="right">Expand sidebar</TooltipContent>
                        </Tooltip>
                    </>
                ) : (
                    <>
                        {isAdmin && (
                            <Button
                                asChild
                                variant="ghost"
                                className="w-full justify-start gap-2.5 text-muted-foreground hover:text-primary"
                            >
                                <Link href="/admin">
                                    <Settings className="h-4 w-4" />
                                    <span className="text-[13px] font-medium">Admin</span>
                                </Link>
                            </Button>
                        )}
                        <Button
                            variant="ghost"
                            onClick={onReset}
                            className="w-full justify-start gap-2.5 text-muted-foreground hover:text-destructive hover:bg-[color:color-mix(in_oklch,var(--destructive)_10%,transparent)]"
                        >
                            <Trash2 className="h-4 w-4" />
                            <span className="text-[13px] font-medium">Clear History</span>
                        </Button>
                        <Button
                            variant="ghost"
                            onClick={onToggleCollapse}
                            className="w-full justify-start gap-2.5 text-muted-foreground"
                        >
                            <PanelLeftClose className="h-4 w-4" />
                            <span className="text-[13px] font-medium">Collapse</span>
                        </Button>
                    </>
                )}
            </div>
        </div>
    );
}
