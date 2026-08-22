'use client';

import React from 'react';
import Link from 'next/link';
import { Scale, Plus, Trash2, Settings, PanelLeftClose, PanelLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { LegalExpert } from '@/lib/legal-experts';
import { useUser } from '@clerk/nextjs';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

interface SidebarProps {
    experts: LegalExpert[];
    selectedExpertId: string;
    onSelectExpert: (id: string) => void;
    onReset: () => void;
    onUpgradeClick: () => void;
    collapsed: boolean;
    onToggleCollapse: () => void;
}

export function Sidebar({
    experts,
    selectedExpertId,
    onSelectExpert,
    onReset,
    collapsed,
    onToggleCollapse,
}: SidebarProps) {
    const { user } = useUser();
    const isAdmin = user?.publicMetadata?.role === 'admin' || user?.publicMetadata?.role === 'ADMIN';

    return (
        <div
            className={cn(
                'flex flex-col h-screen bg-background/95 border-r border-border transition-[width] duration-300 ease-out',
                collapsed ? 'w-16' : 'w-64'
            )}
        >
            {/* Brand + New Consultation */}
            <div className="p-3 space-y-4">
                <div className={cn('flex items-center', collapsed ? 'justify-center' : 'gap-2.5 px-1')}>
                    <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 bg-primary text-primary-foreground shadow-sm"
                    >
                        <Scale className="h-4 w-4" />
                    </div>
                    {!collapsed && (
                        <div className="min-w-0">
                            <div className="font-semibold text-[14px] leading-tight tracking-tight">LexGH</div>
                            <div className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                                Research
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
                        className="w-full justify-start gap-2 rounded-lg bg-primary text-primary-foreground border-primary shadow-sm hover:bg-primary/90 hover:text-primary-foreground"
                    >
                        <Plus className="h-4 w-4" />
                        <span className="font-medium">New Consultation</span>
                    </Button>
                )}
            </div>

            {/* Experts list */}
            <div className="flex-1 overflow-y-auto px-2 py-2">
                {!collapsed && (
                    <div className="text-[10px] font-semibold uppercase tracking-[0.14em] mb-2.5 px-2 text-muted-foreground">
                        Research modes
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
                                    'group w-full flex items-center rounded-lg text-left transition-colors duration-150 border border-transparent',
                                    collapsed ? 'justify-center p-2' : 'gap-2.5 px-2.5 py-2',
                                    isSelected
                                        ? 'bg-primary/10 text-foreground'
                                        : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                                )}
                            >
                                <div
                                    className={cn(
                                        'rounded-md flex items-center justify-center text-sm flex-shrink-0 transition-all',
                                        collapsed ? 'w-9 h-9' : 'w-8 h-8'
                                    )}
                                    style={{
                                        background: `linear-gradient(135deg, ${expert.accentColor}22, ${expert.accentColor}44)`,
                                        border: isSelected
                                            ? `1px solid ${expert.accentColor}99`
                                            : `1px solid ${expert.accentColor}22`,
                                    }}
                                >
                                    {expert.icon}
                                </div>
                                {!collapsed && (
                                    <div className="flex-1 min-w-0">
                                        <div className="font-medium text-[13px] truncate">{expert.name}</div>
                                        <div className="text-[11px] truncate text-muted-foreground">
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
            <div className="p-2 border-t border-border space-y-1 bg-muted/20">
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
