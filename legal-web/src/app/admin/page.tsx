'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { UserButton, useAuth } from '@clerk/nextjs';
import {
    Scale, Database, FileText, AlertCircle, CheckCircle,
    Download, Clock, ArrowLeft, RefreshCw, Search, Globe,
    ChevronLeft, ChevronRight, Filter, ShieldX,
    Users, Settings, Crown, Trash2, Pencil, Save, X,
    BadgeCheck, UserCheck, UserX, RotateCcw, Upload, FilePlus2, MessageSquare,
    CreditCard
} from 'lucide-react';
import { config } from '@/lib/config';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PipelineStats {
    total_cases: number;
    by_status: Record<string, number>;
    by_court: Record<string, number>;
    pdfs_on_disk: number;
    total_size_mb: number;
}

interface CaseRecord {
    case_id: string;
    title: string;
    court_id: string;
    status: string;
    discovered_at: string;
    updated_at: string;
    error?: string;
    retry_count: number;
    url: string;
}

interface PipelineReport {
    timestamp: string;
    duration_seconds: number;
    discovered: number;
    downloaded: number;
    validated: number;
    successful: number;
    failed: number;
}

interface AdminUser {
    clerk_id: string;
    email: string;
    display_name: string;
    plan: string;
    used_today: number;
    created_at: string | null;
    updated_at: string | null;
}

interface PlatformConfig {
    free_tier_daily_limit: number;
    pro_monthly_price_ghs: number;
    enterprise_monthly_price_ghs: number;
}

interface PaymentRecord {
    id: number;
    reference: string;
    clerk_id: string | null;
    email: string | null;
    amount_ghs: number;
    currency: string;
    status: string;
    plan: string | null;
    channel: string | null;
    source: string;
    paid_at: string | null;
    created_at: string | null;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode }> = {
    discovered: { color: 'var(--info)', icon: <Search size={12} /> },
    downloaded: { color: 'var(--warning)', icon: <Download size={12} /> },
    validated: { color: 'var(--ghana-green)', icon: <CheckCircle size={12} /> },
    indexed: { color: 'var(--primary)', icon: <Database size={12} /> },
    failed: { color: 'var(--error)', icon: <AlertCircle size={12} /> },
};

const COURT_NAMES: Record<string, string> = {
    GHASC: 'Supreme Court',
    GHACA: 'Court of Appeal',
    GHAHC: 'High Court',
    GHACC: 'Commercial Court',
    GHADC: 'District Court',
    UNKNOWN: 'Unknown',
};

const PLAN_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
    free: { color: 'var(--muted-foreground)', label: 'Free', icon: <UserCheck size={12} /> },
    professional: { color: 'var(--ghana-gold)', label: 'Pro', icon: <Crown size={12} /> },
    enterprise: { color: 'var(--primary)', label: 'Enterprise', icon: <BadgeCheck size={12} /> },
};

// ─── Main Component ──────────────────────────────────────────────────────────

type Tab = 'overview' | 'cases' | 'reports' | 'users' | 'payments' | 'config' | 'feedback';

export default function AdminPage() {
    const { getToken } = useAuth();
    const [stats, setStats] = useState<PipelineStats | null>(null);
    const [cases, setCases] = useState<CaseRecord[]>([]);
    const [reports, setReports] = useState<PipelineReport[]>([]);
    const [totalCases, setTotalCases] = useState(0);
    const [page, setPage] = useState(1);
    const [statusFilter, setStatusFilter] = useState<string>('');
    const [courtFilter, setCourtFilter] = useState<string>('');
    const [loading, setLoading] = useState(true);
    const [forbidden, setForbidden] = useState(false);
    const [activeTab, setActiveTab] = useState<Tab>('overview');
    const perPage = 50;

    // Users tab state
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [usersTotal, setUsersTotal] = useState(0);
    const [usersPage, setUsersPage] = useState(1);
    const [userSearch, setUserSearch] = useState('');
    const [usersLoading, setUsersLoading] = useState(false);
    const [planSwitching, setPlanSwitching] = useState<Record<string, string>>({});
    const [wipingUsage, setWipingUsage] = useState<Record<string, boolean>>({});
    const [userFeedback, setUserFeedback] = useState<Record<string, { type: 'success' | 'error'; msg: string }>>({});
    const [enrichingAll, setEnrichingAll] = useState(false);
    const [enrichFeedback, setEnrichFeedback] = useState<string | null>(null);

    // Feedback tab state
    const [feedbacks, setFeedbacks] = useState<any[]>([]);
    const [feedbacksLoading, setFeedbacksLoading] = useState(false);
    const [deletingFeedback, setDeletingFeedback] = useState<Record<number, boolean>>({});

    // Payments tab state
    const [payments, setPayments] = useState<PaymentRecord[]>([]);
    const [paymentsTotal, setPaymentsTotal] = useState(0);
    const [paymentsRevenue, setPaymentsRevenue] = useState(0);
    const [paymentsSuccessCount, setPaymentsSuccessCount] = useState(0);
    const [paymentsPage, setPaymentsPage] = useState(1);
    const [paymentSearch, setPaymentSearch] = useState('');
    const [paymentsLoading, setPaymentsLoading] = useState(false);

    // Config tab state
    const [platformConfig, setPlatformConfig] = useState<PlatformConfig | null>(null);
    const [configDraft, setConfigDraft] = useState<PlatformConfig | null>(null);
    const [configSaving, setConfigSaving] = useState(false);
    const [configFeedback, setConfigFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

    // Ingestion state
    const [ingestionStatus, setIngestionStatus] = useState<{
        status: string;
        started_at: string | null;
        completed_at: string | null;
        result: { summary: string } | null;
        error: string | null;
    }>({ status: 'idle', started_at: null, completed_at: null, result: null, error: null });
    const [triggeringIngestion, setTriggeringIngestion] = useState(false);
    const [ingestionFeedback, setIngestionFeedback] = useState<string | null>(null);
    const [isIngestionModalOpen, setIsIngestionModalOpen] = useState(false);

    // Discovery state
    const [discoveryStatus, setDiscoveryStatus] = useState<{
        status: string;
        started_at: string | null;
        completed_at: string | null;
        result: {
            summary: string;
            scraped?: number;
            new?: number;
            downloaded?: number;
            inserted?: number;
            already_known?: number;
            mode?: string;
            cursor_before?: number;
            cursor_after?: number;
            pages_scraped?: number;
            reached_end?: boolean;
            flipped_to_incremental?: boolean;
        } | null;
        error: string | null;
    }>({ status: 'idle', started_at: null, completed_at: null, result: null, error: null });
    const [triggeringDiscovery, setTriggeringDiscovery] = useState(false);
    const [discoveryFeedback, setDiscoveryFeedback] = useState<string | null>(null);
    const [isDiscoveryModalOpen, setIsDiscoveryModalOpen] = useState(false);
    const [discoveryState, setDiscoveryState] = useState<{
        mode: string;
        backfill_next_page: number;
        batch_size: number;
        backfill_completed_at: string | null;
    } | null>(null);
    const [discoveryBatchSize, setDiscoveryBatchSize] = useState<number>(5);

    const authHeaders = useCallback(async (): Promise<Record<string, string>> => {
        const token = await getToken();
        return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : {};
    }, [getToken]);

    // ── Fetchers ──────────────────────────────────────────────────────────────

    const fetchStats = async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/stats`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) setStats(await res.json());
        } catch (e) { console.error(e); }
    };

    const fetchCases = async () => {
        try {
            const headers = await authHeaders();
            const params = new URLSearchParams({ page: String(page), per_page: String(perPage) });
            if (statusFilter) params.set('status', statusFilter);
            if (courtFilter) params.set('court_id', courtFilter);
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/cases?${params}`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) { const d = await res.json(); setCases(d.cases); setTotalCases(d.total); }
        } catch (e) { console.error(e); }
    };

    const fetchReports = async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/reports`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) { const d = await res.json(); setReports(d.reports); }
        } catch (e) { console.error(e); }
    };

    const fetchUsers = useCallback(async () => {
        setUsersLoading(true);
        try {
            const headers = await authHeaders();
            const params = new URLSearchParams({
                page: String(usersPage),
                per_page: '30',
                ...(userSearch ? { search: userSearch } : {}),
            });
            const res = await fetch(`${config.apiUrl}/api/admin/users?${params}`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) { const d = await res.json(); setUsers(d.users); setUsersTotal(d.total); }
        } catch (e) { console.error(e); }
        finally { setUsersLoading(false); }
    }, [authHeaders, usersPage, userSearch]);

    const fetchConfig = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/config`, { headers });
            if (res.ok) {
                const d: PlatformConfig = await res.json();
                setPlatformConfig(d);
                setConfigDraft(d);
            }
        } catch (e) { console.error(e); }
    }, [authHeaders]);

    const fetchPayments = useCallback(async () => {
        setPaymentsLoading(true);
        try {
            const headers = await authHeaders();
            const params = new URLSearchParams({
                page: String(paymentsPage),
                per_page: '50',
                ...(paymentSearch ? { search: paymentSearch } : {}),
            });
            const res = await fetch(`${config.apiUrl}/api/admin/payments?${params}`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) {
                const d = await res.json();
                setPayments(d.payments);
                setPaymentsTotal(d.total);
                setPaymentsRevenue(d.total_revenue_ghs);
                setPaymentsSuccessCount(d.successful_payments);
            }
        } catch (e) { console.error(e); }
        finally { setPaymentsLoading(false); }
    }, [authHeaders, paymentsPage, paymentSearch]);

    const fetchAdminFeedbacks = useCallback(async () => {
        setFeedbacksLoading(true);
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/feedback`, { headers });
            if (res.status === 403) { setForbidden(true); return; }
            if (res.ok) {
                const d = await res.json();
                setFeedbacks(d.feedbacks);
            }
        } catch (e) { console.error(e); }
        finally { setFeedbacksLoading(false); }
    }, [authHeaders]);

    const fetchIngestionStatus = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/ingestion-status`, { headers });
            if (res.ok) {
                const d = await res.json();
                setIngestionStatus(d);
            }
        } catch (e) { console.error(e); }
    }, [authHeaders]);

    const fetchDiscoveryStatus = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/discovery-status`, { headers });
            if (res.ok) {
                const d = await res.json();
                setDiscoveryStatus(d);
            }
        } catch (e) { console.error(e); }
    }, [authHeaders]);

    const fetchDiscoveryState = useCallback(async () => {
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/discovery-state`, { headers });
            if (res.ok) {
                const d = await res.json();
                setDiscoveryState(d);
                if (d.batch_size) setDiscoveryBatchSize(d.batch_size);
            }
        } catch (e) { console.error(e); }
    }, [authHeaders]);

    const triggerIngestion = async () => {
        setIsIngestionModalOpen(false);
        setTriggeringIngestion(true);
        setIngestionFeedback(null);
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/trigger-ingestion`, {
                method: 'POST', headers,
            });
            const d = await res.json();
            if (res.ok) {
                setIngestionFeedback('✓ Ingestion triggered — polling for status...');
                setIngestionStatus(prev => ({ ...prev, status: 'running' }));
            } else {
                setIngestionFeedback(`✗ ${d.detail || 'Failed to trigger'}`);
            }
        } catch {
            setIngestionFeedback('✗ Network error');
        } finally {
            setTriggeringIngestion(false);
            setTimeout(() => setIngestionFeedback(null), 5000);
        }
    };

    const triggerDiscovery = async () => {
        setIsDiscoveryModalOpen(false);
        setTriggeringDiscovery(true);
        setDiscoveryFeedback(null);
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/trigger-discovery`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ batch_size: discoveryBatchSize }),
            });
            const d = await res.json();
            if (res.ok) {
                setDiscoveryFeedback('✓ Discovery triggered — scraping ghalii.org...');
                setDiscoveryStatus(prev => ({ ...prev, status: 'running' }));
            } else {
                setDiscoveryFeedback(`✗ ${d.detail || 'Failed to trigger'}`);
            }
        } catch {
            setDiscoveryFeedback('✗ Network error');
        } finally {
            setTriggeringDiscovery(false);
            setTimeout(() => setDiscoveryFeedback(null), 5000);
        }
    };

    const fetchAll = async () => {
        setLoading(true);
        await Promise.all([fetchStats(), fetchCases(), fetchReports(), fetchIngestionStatus(), fetchDiscoveryStatus(), fetchDiscoveryState()]);
        setLoading(false);
    };

    useEffect(() => { fetchAll(); }, []);
    useEffect(() => { fetchCases(); }, [page, statusFilter, courtFilter]);
    useEffect(() => { if (activeTab === 'users') fetchUsers(); }, [activeTab, usersPage, userSearch]);
    useEffect(() => { if (activeTab === 'config') fetchConfig(); }, [activeTab]);
    useEffect(() => { if (activeTab === 'feedback') fetchAdminFeedbacks(); }, [activeTab, fetchAdminFeedbacks]);
    useEffect(() => { if (activeTab === 'payments') fetchPayments(); }, [activeTab, fetchPayments]);

    // Auto-poll ingestion status when running
    useEffect(() => {
        if (ingestionStatus.status !== 'running') return;
        const interval = setInterval(async () => {
            await fetchIngestionStatus();
        }, 3000);
        return () => clearInterval(interval);
    }, [ingestionStatus.status, fetchIngestionStatus]);

    // Refresh stats when ingestion completes
    useEffect(() => {
        if (ingestionStatus.status === 'completed') {
            fetchStats();
        }
    }, [ingestionStatus.status]);

    // Auto-poll discovery status when running
    useEffect(() => {
        if (discoveryStatus.status !== 'running') return;
        const interval = setInterval(async () => {
            await fetchDiscoveryStatus();
        }, 4000);
        return () => clearInterval(interval);
    }, [discoveryStatus.status, fetchDiscoveryStatus]);

    // Refresh stats + cursor when discovery completes
    useEffect(() => {
        if (discoveryStatus.status === 'completed') {
            fetchStats();
            fetchCases();
            fetchDiscoveryState();
        }
    }, [discoveryStatus.status]);

    // ── User Actions ──────────────────────────────────────────────────────────

    const switchPlan = async (clerk_id: string, newPlan: string) => {
        setPlanSwitching(prev => ({ ...prev, [clerk_id]: newPlan }));
        setUserFeedback(prev => { const n = { ...prev }; delete n[clerk_id]; return n; });
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/users/${clerk_id}/plan`, {
                method: 'PATCH',
                headers,
                body: JSON.stringify({ plan: newPlan }),
            });
            const d = await res.json();
            if (res.ok) {
                setUsers(prev => prev.map(u => u.clerk_id === clerk_id ? { ...u, plan: newPlan } : u));
                setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'success', msg: `Switched to ${newPlan}` } }));
            } else {
                setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'error', msg: d.detail || 'Failed' } }));
            }
        } catch {
            setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'error', msg: 'Network error' } }));
        } finally {
            setPlanSwitching(prev => { const n = { ...prev }; delete n[clerk_id]; return n; });
            setTimeout(() => setUserFeedback(prev => { const n = { ...prev }; delete n[clerk_id]; return n; }), 3000);
        }
    };

    const wipeUsage = async (clerk_id: string) => {
        if (!confirm('Reset today\'s usage for this user? This cannot be undone.')) return;
        setWipingUsage(prev => ({ ...prev, [clerk_id]: true }));
        setUserFeedback(prev => { const n = { ...prev }; delete n[clerk_id]; return n; });
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/users/${clerk_id}/usage`, {
                method: 'DELETE', headers,
            });
            const d = await res.json();
            if (res.ok) {
                setUsers(prev => prev.map(u => u.clerk_id === clerk_id ? { ...u, used_today: 0 } : u));
                setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'success', msg: `Wiped ${d.rows_deleted} entries` } }));
            } else {
                setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'error', msg: d.detail || 'Failed' } }));
            }
        } catch {
            setUserFeedback(prev => ({ ...prev, [clerk_id]: { type: 'error', msg: 'Network error' } }));
        } finally {
            setWipingUsage(prev => { const n = { ...prev }; delete n[clerk_id]; return n; });
            setTimeout(() => setUserFeedback(prev => { const n = { ...prev }; delete n[clerk_id]; return n; }), 3000);
        }
    };

    const deleteFeedback = async (id: number) => {
        if (!confirm('Are you sure you want to delete this feedback?')) return;
        setDeletingFeedback(prev => ({ ...prev, [id]: true }));
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/feedback/${id}`, {
                method: 'DELETE',
                headers,
            });
            if (res.ok) {
                setFeedbacks(prev => prev.filter(f => f.id !== id));
            } else {
                alert('Failed to delete feedback');
            }
        } catch (e) {
            alert('Network error');
        } finally {
            setDeletingFeedback(prev => { const n = { ...prev }; delete n[id]; return n; });
        }
    };

    // ── Config Actions ────────────────────────────────────────────────────────

    const saveConfig = async () => {
        if (!configDraft) return;
        setConfigSaving(true);
        setConfigFeedback(null);
        try {
            const headers = await authHeaders();
            const res = await fetch(`${config.apiUrl}/api/admin/config`, {
                method: 'PUT',
                headers,
                body: JSON.stringify(configDraft),
            });
            const d = await res.json();
            if (res.ok) {
                setPlatformConfig(d.config);
                setConfigDraft(d.config);
                setConfigFeedback({ type: 'success', msg: 'Configuration saved successfully.' });
            } else {
                setConfigFeedback({ type: 'error', msg: d.detail || 'Save failed.' });
            }
        } catch {
            setConfigFeedback({ type: 'error', msg: 'Network error.' });
        } finally {
            setConfigSaving(false);
            setTimeout(() => setConfigFeedback(null), 4000);
        }
    };

    // ── Forbidden ─────────────────────────────────────────────────────────────

    if (forbidden) {
        return (
            <div className="min-h-screen flex items-center justify-center"
                 style={{ background: 'var(--background)' }}>
                <div className="text-center p-8 rounded-2xl max-w-sm"
                     style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                    <ShieldX size={48} className="mx-auto mb-4" style={{ color: 'var(--error)' }} />
                    <h2 className="text-lg font-bold mb-2" style={{ color: 'var(--foreground)' }}>Access Denied</h2>
                    <p className="text-sm mb-4" style={{ color: 'var(--muted-foreground)' }}>
                        You need admin privileges to view this page.
                    </p>
                    <Link href="/chat" className="inline-block px-5 py-2.5 rounded-xl text-sm font-semibold"
                          style={{ background: 'var(--primary)', color: '#fff' }}>
                        Back to Chat
                    </Link>
                </div>
            </div>
        );
    }

    const totalPages = Math.ceil(totalCases / perPage);
    const usersTotalPages = Math.ceil(usersTotal / 30);
    const configChanged = JSON.stringify(configDraft) !== JSON.stringify(platformConfig);

    const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
        { id: 'overview', label: 'Overview', icon: <Database size={14} /> },
        { id: 'cases', label: 'Cases', icon: <FileText size={14} /> },
        { id: 'reports', label: 'Reports', icon: <Clock size={14} /> },
        { id: 'users', label: 'Users', icon: <Users size={14} /> },
        { id: 'payments', label: 'Payments', icon: <CreditCard size={14} /> },
        { id: 'feedback', label: 'Feedback', icon: <MessageSquare size={14} /> },
        { id: 'config', label: 'Config', icon: <Settings size={14} /> },
    ];

    return (
        <div className="min-h-screen" style={{ background: 'var(--background)' }}>
            
            {/* Ingestion Confirmation Modal */}
            {isIngestionModalOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
                     style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
                     onClick={() => setIsIngestionModalOpen(false)}>
                    <div className="relative w-full max-w-md rounded-2xl overflow-hidden shadow-2xl p-6 md:p-8 animate-in zoom-in-95"
                         style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
                         onClick={e => e.stopPropagation()}>
                        <div className="w-12 h-12 rounded-full flex items-center justify-center mb-5"
                             style={{ background: 'rgba(56, 189, 248, 0.1)' }}>
                            <Database size={24} style={{ color: 'var(--primary)' }} />
                        </div>
                        <h3 className="text-xl font-bold mb-2">Run Ingestion Pipeline</h3>
                        <p className="text-sm mb-6" style={{ color: 'var(--muted-foreground)' }}>
                            This will process pending cases and embed them into Qdrant Cloud using Voyage AI. Existing vectors will not be wiped.
                        </p>
                        <div className="flex gap-3 justify-end items-center">
                            <button onClick={() => setIsIngestionModalOpen(false)}
                                    className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-white/5 transition-colors"
                                    style={{ color: 'var(--muted-foreground)' }}>
                                Cancel
                            </button>
                            <button onClick={triggerIngestion}
                                    className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold transition-transform hover:scale-[1.02]"
                                    style={{ background: 'var(--primary)', color: 'white', boxShadow: '0 4px 14px rgba(91,106,240,0.3)' }}>
                                Confirm & Run
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Discovery Confirmation Modal */}
            {isDiscoveryModalOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200"
                     style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}
                     onClick={() => setIsDiscoveryModalOpen(false)}>
                    <div className="relative w-full max-w-md rounded-2xl overflow-hidden shadow-2xl p-6 md:p-8 animate-in zoom-in-95"
                         style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
                         onClick={e => e.stopPropagation()}>
                        <div className="w-12 h-12 rounded-full flex items-center justify-center mb-5"
                             style={{ background: 'rgba(234, 179, 8, 0.1)' }}>
                            <Globe size={24} style={{ color: 'var(--ghana-gold)' }} />
                        </div>
                        <h3 className="text-xl font-bold mb-2">Run Discovery</h3>
                        <p className="text-sm mb-6" style={{ color: 'var(--muted-foreground)' }}>
                            {discoveryState?.mode === 'incremental'
                                ? <>This will scan the newest pages on ghalii.org for any judgments published since the last run, and add new ones to the pipeline as &quot;pending&quot;. Run ingestion afterwards to embed them.</>
                                : <>This run will scrape <span className="font-mono font-semibold" style={{ color: 'var(--ghana-gold)' }}>{discoveryBatchSize}</span> pages of ghalii.org{discoveryState ? <> starting at page <span className="font-mono font-semibold" style={{ color: 'var(--ghana-gold)' }}>{discoveryState.backfill_next_page}</span></> : null} (oldest first). New cases get added as &quot;pending&quot; — the cursor advances on success so the next run picks up where this one left off.</>}
                        </p>
                        <div className="flex gap-3 justify-end items-center">
                            <button onClick={() => setIsDiscoveryModalOpen(false)}
                                    className="px-4 py-2 rounded-lg text-sm font-medium hover:bg-white/5 transition-colors"
                                    style={{ color: 'var(--muted-foreground)' }}>
                                Cancel
                            </button>
                            <button onClick={triggerDiscovery}
                                    className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-semibold transition-transform hover:scale-[1.02]"
                                    style={{ background: 'var(--ghana-gold)', color: '#000', boxShadow: '0 4px 14px rgba(234,179,8,0.3)' }}>
                                Confirm & Discover
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Header */}
            <header className="sticky top-0 z-50" style={{
                background: 'rgba(12,14,20,0.85)',
                backdropFilter: 'blur(16px)',
                borderBottom: '1px solid var(--border)',
            }}>
                <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/chat" className="flex items-center gap-2 text-sm"
                              style={{ color: 'var(--muted-foreground)' }}>
                            <ArrowLeft size={16} />
                            <span>Back to Chat</span>
                        </Link>
                        <div style={{ width: 1, height: 24, background: 'var(--border)' }} />
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
                                 style={{ background: 'linear-gradient(135deg, var(--ghana-gold), #e6a817)' }}>
                                <Scale size={14} className="text-black" />
                            </div>
                            <span className="font-bold text-sm">Admin Dashboard</span>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button onClick={fetchAll}
                                className="p-2 rounded-lg"
                                style={{ color: 'var(--muted-foreground)', border: '1px solid var(--border)' }}>
                            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                        </button>
                        <UserButton />
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto px-6 py-6">
                {/* Tabs */}
                <div className="flex gap-1 mb-6 p-1 rounded-xl w-fit"
                     style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                    {tabs.map(tab => (
                        <button key={tab.id} onClick={() => setActiveTab(tab.id)}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium"
                                style={{
                                    background: activeTab === tab.id ? 'var(--primary)' : 'transparent',
                                    color: activeTab === tab.id ? '#fff' : 'var(--muted-foreground)',
                                }}>
                            {tab.icon}
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* ── Overview Tab ─────────────────────────────────────────── */}
                {activeTab === 'overview' && stats && (
                    <div className="space-y-6">
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                            <StatCard label="Total Cases" value={stats.total_cases} icon={<FileText size={18} />} color="var(--primary)" />
                            <StatCard label="Indexed" value={stats.by_status.indexed || 0} icon={<Database size={18} />} color="var(--ghana-green)" />
                            <StatCard label="PDFs on Disk" value={stats.pdfs_on_disk} icon={<Download size={18} />} color="var(--ghana-gold)" />
                            <StatCard label="Storage" value={`${stats.total_size_mb} MB`} icon={<Database size={18} />} color="var(--info)" />
                        </div>
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <BreakdownCard title="By Status" items={Object.entries(stats.by_status).map(([k, v]) => ({
                                label: k, value: v, color: STATUS_CONFIG[k]?.color || 'var(--muted-foreground)',
                            }))} />
                            <CourtBreakdownCard title="By Court" items={Object.entries(stats.by_court)
                                .map(([k, v]) => ({ label: COURT_NAMES[k] || k, value: v }))
                                .sort((a, b) => b.value - a.value)} />
                        </div>

                        {/* Pipeline Operations — Discovery + Ingestion */}
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

                            {/* Discovery Card */}
                            <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                                <div className="flex items-center justify-between mb-3 gap-3 flex-wrap">
                                    <div className="min-w-0">
                                        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>Case Discovery</h3>
                                        <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                                            {discoveryState?.mode === 'incremental'
                                                ? 'Incremental: scanning newest judgments on ghalii.org'
                                                : 'Backfill: archiving historical judgments from ghalii.org'}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
                                              style={{
                                                  background: discoveryStatus.status === 'running' ? 'var(--warning)18' :
                                                             discoveryStatus.status === 'completed' ? 'var(--ghana-green)18' :
                                                             discoveryStatus.status === 'failed' ? 'var(--error)18' : 'var(--surface-2)',
                                                  color: discoveryStatus.status === 'running' ? 'var(--warning)' :
                                                         discoveryStatus.status === 'completed' ? 'var(--ghana-green)' :
                                                         discoveryStatus.status === 'failed' ? 'var(--error)' : 'var(--muted-foreground)',
                                              }}>
                                            {discoveryStatus.status === 'running' && <RefreshCw size={11} className="animate-spin" />}
                                            {discoveryStatus.status === 'completed' && <CheckCircle size={11} />}
                                            {discoveryStatus.status === 'failed' && <AlertCircle size={11} />}
                                            {discoveryStatus.status}
                                        </span>
                                        <button
                                            onClick={() => setIsDiscoveryModalOpen(true)}
                                            disabled={triggeringDiscovery || discoveryStatus.status === 'running'}
                                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-40 transition-opacity"
                                            style={{ background: 'var(--ghana-gold)', color: '#000' }}>
                                            {triggeringDiscovery || discoveryStatus.status === 'running'
                                                ? <><RefreshCw size={13} className="animate-spin" /> Scraping…</>
                                                : <><Globe size={13} /> Run Discovery</>}
                                        </button>
                                    </div>
                                </div>

                                {/* Cursor + batch-size controls */}
                                {discoveryState && (
                                    <div className="mt-3 p-3 rounded-lg flex items-center justify-between gap-4 flex-wrap"
                                         style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                                        <div className="flex items-center gap-4 text-xs flex-wrap">
                                            <div>
                                                <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted-foreground)' }}>Mode</div>
                                                <div className="font-mono font-semibold capitalize" style={{ color: discoveryState.mode === 'backfill' ? 'var(--ghana-gold)' : 'var(--ghana-green)' }}>
                                                    {discoveryState.mode}
                                                </div>
                                            </div>
                                            {discoveryState.mode === 'backfill' && (
                                                <div>
                                                    <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted-foreground)' }}>Next page</div>
                                                    <div className="font-mono font-semibold" style={{ color: 'var(--foreground)' }}>
                                                        {discoveryState.backfill_next_page}
                                                    </div>
                                                </div>
                                            )}
                                            {discoveryState.backfill_completed_at && (
                                                <div>
                                                    <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted-foreground)' }}>Backfill done</div>
                                                    <div className="font-mono text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                        {new Date(discoveryState.backfill_completed_at).toLocaleDateString()}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                        <label className="flex items-center gap-2 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                            <span>Pages per run</span>
                                            <input
                                                type="number"
                                                min={1}
                                                max={50}
                                                value={discoveryBatchSize}
                                                onChange={e => setDiscoveryBatchSize(Math.max(1, Math.min(50, Number(e.target.value) || 1)))}
                                                disabled={triggeringDiscovery || discoveryStatus.status === 'running'}
                                                className="w-16 px-2 py-1 rounded text-sm font-mono text-center"
                                                style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                                            />
                                            <span className="text-[10px]" style={{ color: 'var(--muted-foreground)' }}>(≈50/page)</span>
                                        </label>
                                    </div>
                                )}

                                {discoveryStatus.status === 'completed' && discoveryStatus.result && (
                                    <div className="mt-3 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap"
                                         style={{ background: 'var(--ghana-green)08', border: '1px solid var(--ghana-green)30', color: 'var(--ghana-green)' }}>
                                        ✓ {discoveryStatus.result.summary}
                                        {discoveryStatus.result.new !== undefined && (
                                            <span className="block mt-1" style={{ color: 'var(--foreground)', fontFamily: 'inherit' }}>
                                                New: {discoveryStatus.result.new} · Already known: {discoveryStatus.result.already_known ?? 0} · Inserted: {discoveryStatus.result.inserted ?? 0}
                                            </span>
                                        )}
                                        {discoveryStatus.result.cursor_before !== undefined && discoveryStatus.result.cursor_after !== undefined && discoveryStatus.result.mode === 'backfill' && (
                                            <span className="block mt-1" style={{ color: 'var(--foreground)', fontFamily: 'inherit' }}>
                                                Pages {discoveryStatus.result.cursor_before}–{(discoveryStatus.result.cursor_after ?? 0) - 1} scraped → next page {discoveryStatus.result.cursor_after}
                                            </span>
                                        )}
                                        {discoveryStatus.result.flipped_to_incremental && (
                                            <span className="block mt-1 font-semibold" style={{ color: 'var(--ghana-green)', fontFamily: 'inherit' }}>
                                                🎉 Backfill complete — switched to incremental mode.
                                            </span>
                                        )}
                                        {discoveryStatus.completed_at && (
                                            <span className="block mt-1" style={{ color: 'var(--muted-foreground)', fontFamily: 'inherit' }}>
                                                Completed: {new Date(discoveryStatus.completed_at).toLocaleString()}
                                            </span>
                                        )}
                                    </div>
                                )}
                                {discoveryStatus.status === 'failed' && discoveryStatus.error && (
                                    <div className="mt-3 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap"
                                         style={{ background: 'var(--error)08', border: '1px solid var(--error)30', color: 'var(--error)' }}>
                                        ✗ {discoveryStatus.error}
                                    </div>
                                )}
                                {discoveryFeedback && (
                                    <div className="mt-2 text-xs font-medium"
                                         style={{ color: discoveryFeedback.startsWith('✓') ? 'var(--ghana-green)' : 'var(--error)' }}>
                                        {discoveryFeedback}
                                    </div>
                                )}
                            </div>

                            {/* Ingestion Card */}
                            <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                                <div className="flex items-center justify-between mb-3">
                                    <div>
                                        <h3 className="text-sm font-bold" style={{ color: 'var(--foreground)' }}>Pipeline Ingestion</h3>
                                        <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                                            Embed pending cases into Qdrant using Voyage AI
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
                                              style={{
                                                  background: ingestionStatus.status === 'running' ? 'var(--warning)18' :
                                                             ingestionStatus.status === 'completed' ? 'var(--ghana-green)18' :
                                                             ingestionStatus.status === 'failed' ? 'var(--error)18' : 'var(--surface-2)',
                                                  color: ingestionStatus.status === 'running' ? 'var(--warning)' :
                                                         ingestionStatus.status === 'completed' ? 'var(--ghana-green)' :
                                                         ingestionStatus.status === 'failed' ? 'var(--error)' : 'var(--muted-foreground)',
                                              }}>
                                            {ingestionStatus.status === 'running' && <RefreshCw size={11} className="animate-spin" />}
                                            {ingestionStatus.status === 'completed' && <CheckCircle size={11} />}
                                            {ingestionStatus.status === 'failed' && <AlertCircle size={11} />}
                                            {ingestionStatus.status}
                                        </span>
                                        <button
                                            onClick={() => setIsIngestionModalOpen(true)}
                                            disabled={triggeringIngestion || ingestionStatus.status === 'running'}
                                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-40 transition-opacity"
                                            style={{ background: 'var(--primary)', color: '#fff' }}>
                                            {triggeringIngestion || ingestionStatus.status === 'running'
                                                ? <><RefreshCw size={13} className="animate-spin" /> Running…</>
                                                : <><Database size={13} /> Run Ingestion</>}
                                        </button>
                                    </div>
                                </div>
                                {ingestionStatus.status === 'completed' && ingestionStatus.result && (
                                    <div className="mt-3 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap"
                                         style={{ background: 'var(--ghana-green)08', border: '1px solid var(--ghana-green)30', color: 'var(--ghana-green)' }}>
                                        ✓ {ingestionStatus.result.summary}
                                        {ingestionStatus.completed_at && (
                                            <span className="block mt-1" style={{ color: 'var(--muted-foreground)', fontFamily: 'inherit' }}>
                                                Completed: {new Date(ingestionStatus.completed_at).toLocaleString()}
                                            </span>
                                        )}
                                    </div>
                                )}
                                {ingestionStatus.status === 'failed' && ingestionStatus.error && (
                                    <div className="mt-3 p-3 rounded-lg text-xs font-mono whitespace-pre-wrap"
                                         style={{ background: 'var(--error)08', border: '1px solid var(--error)30', color: 'var(--error)' }}>
                                        ✗ {ingestionStatus.error}
                                    </div>
                                )}
                                {ingestionFeedback && (
                                    <div className="mt-2 text-xs font-medium"
                                         style={{ color: ingestionFeedback.startsWith('✓') ? 'var(--ghana-green)' : 'var(--error)' }}>
                                        {ingestionFeedback}
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Bulk Upload — manually-downloaded PDFs */}
                        <BulkUploadPanel
                            onUploaded={async () => {
                                await Promise.all([fetchStats(), fetchCases()]);
                            }}
                            authHeaders={authHeaders}
                        />
                    </div>
                )}

                {/* ── Cases Tab ────────────────────────────────────────────── */}
                {activeTab === 'cases' && (
                    <div className="space-y-4">
                        <div className="flex gap-3 items-center flex-wrap">
                            <div className="flex items-center gap-2">
                                <Filter size={14} style={{ color: 'var(--muted-foreground)' }} />
                                <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                                        className="text-sm px-3 py-1.5 rounded-lg"
                                        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <option value="">All Statuses</option>
                                    {['discovered', 'downloaded', 'validated', 'indexed', 'failed'].map(s => (
                                        <option key={s} value={s}>{s}</option>
                                    ))}
                                </select>
                                <select value={courtFilter} onChange={e => { setCourtFilter(e.target.value); setPage(1); }}
                                        className="text-sm px-3 py-1.5 rounded-lg"
                                        style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <option value="">All Courts</option>
                                    {Object.entries(COURT_NAMES).filter(([k]) => k !== 'UNKNOWN').map(([id, name]) => (
                                        <option key={id} value={id}>{name}</option>
                                    ))}
                                </select>
                            </div>
                            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{totalCases} cases</span>
                        </div>
                        <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr style={{ background: 'var(--surface-1)' }}>
                                            {['Case', 'Court', 'Status', 'Discovered', 'Error'].map(h => (
                                                <th key={h} className="text-left px-4 py-3 font-semibold" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {cases.map(c => (
                                            <tr key={c.case_id} style={{ borderTop: '1px solid var(--border)' }}>
                                                <td className="px-4 py-3">
                                                    <a href={c.url} target="_blank" rel="noopener noreferrer"
                                                       className="hover:underline" style={{ color: 'var(--primary)' }}>
                                                        {c.title.length > 60 ? c.title.slice(0, 60) + '...' : c.title}
                                                    </a>
                                                    <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--muted-foreground)' }}>{c.case_id}</div>
                                                </td>
                                                <td className="px-4 py-3" style={{ color: 'var(--foreground)' }}>{COURT_NAMES[c.court_id] || c.court_id}</td>
                                                <td className="px-4 py-3">
                                                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
                                                          style={{ background: `${STATUS_CONFIG[c.status]?.color || 'var(--muted-foreground)'}15`, color: STATUS_CONFIG[c.status]?.color || 'var(--muted-foreground)' }}>
                                                        {STATUS_CONFIG[c.status]?.icon}{c.status}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>{new Date(c.discovered_at).toLocaleDateString()}</td>
                                                <td className="px-4 py-3 text-xs" style={{ color: 'var(--error)' }}>{c.error || '-'}</td>
                                            </tr>
                                        ))}
                                        {cases.length === 0 && (
                                            <tr><td colSpan={5} className="px-4 py-8 text-center" style={{ color: 'var(--muted-foreground)' }}>No cases found.</td></tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        {totalPages > 1 && (
                            <div className="flex items-center justify-center gap-2">
                                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                                        className="p-2 rounded-lg disabled:opacity-30"
                                        style={{ border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <ChevronLeft size={16} />
                                </button>
                                <span className="text-sm px-3" style={{ color: 'var(--muted-foreground)' }}>Page {page} of {totalPages}</span>
                                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                                        className="p-2 rounded-lg disabled:opacity-30"
                                        style={{ border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <ChevronRight size={16} />
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* ── Reports Tab ──────────────────────────────────────────── */}
                {activeTab === 'reports' && (
                    <div className="space-y-3">
                        {reports.length === 0 && (
                            <div className="p-8 text-center rounded-xl"
                                 style={{ background: 'var(--surface-1)', border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
                                No pipeline reports yet.
                            </div>
                        )}
                        {reports.map((r, i) => (
                            <div key={i} className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-2">
                                        <Clock size={14} style={{ color: 'var(--muted-foreground)' }} />
                                        <span className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{new Date(r.timestamp).toLocaleString()}</span>
                                    </div>
                                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'var(--surface-2)', color: 'var(--muted-foreground)' }}>{r.duration_seconds}s</span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                                    <MiniStat label="Discovered" value={r.discovered} color="var(--info)" />
                                    <MiniStat label="Downloaded" value={r.downloaded} color="var(--warning)" />
                                    <MiniStat label="Validated" value={r.validated} color="var(--ghana-green)" />
                                    <MiniStat label="Chunks OK" value={r.successful} color="var(--primary)" />
                                    <MiniStat label="Failed" value={r.failed} color="var(--error)" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* ── Users Tab ────────────────────────────────────────────── */}
                {activeTab === 'users' && (
                    <div className="space-y-4">
                        {/* Search + count + enrich button */}
                        <div className="flex items-center gap-3 flex-wrap">
                            <div className="relative">
                                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2"
                                        style={{ color: 'var(--muted-foreground)' }} />
                                <input
                                    type="text"
                                    placeholder="Search name, email or user ID…"
                                    value={userSearch}
                                    onChange={e => { setUserSearch(e.target.value); setUsersPage(1); }}
                                    className="text-sm pl-9 pr-4 py-2 rounded-lg w-72"
                                    style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                                />
                            </div>
                            <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                {usersTotal} user{usersTotal !== 1 ? 's' : ''}
                            </span>
                            <button onClick={fetchUsers} className="p-2 rounded-lg"
                                    style={{ border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
                                <RefreshCw size={13} className={usersLoading ? 'animate-spin' : ''} />
                            </button>
                            {/* Bulk enrich button */}
                            <button
                                onClick={async () => {
                                    setEnrichingAll(true);
                                    setEnrichFeedback(null);
                                    try {
                                        const headers = await authHeaders();
                                        const res = await fetch(`${config.apiUrl}/api/admin/users/enrich`, { method: 'POST', headers });
                                        const d = await res.json();
                                        if (res.ok) {
                                            setEnrichFeedback(`✓ ${d.message}`);
                                            await fetchUsers();
                                        } else {
                                            setEnrichFeedback(`✗ ${d.detail || 'Failed'}`);
                                        }
                                    } catch { setEnrichFeedback('✗ Network error'); }
                                    finally {
                                        setEnrichingAll(false);
                                        setTimeout(() => setEnrichFeedback(null), 5000);
                                    }
                                }}
                                disabled={enrichingAll}
                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold disabled:opacity-40"
                                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                                title="Fetch real names & emails from Clerk for placeholder users">
                                {enrichingAll
                                    ? <><RotateCcw size={12} className="animate-spin" /> Enriching…</>
                                    : <><UserCheck size={12} /> Enrich Users</>}
                            </button>
                            {enrichFeedback && (
                                <span className="text-xs" style={{ color: enrichFeedback.startsWith('✓') ? 'var(--ghana-green)' : 'var(--error)' }}>
                                    {enrichFeedback}
                                </span>
                            )}
                        </div>

                        {/* Users table */}
                        <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--border)' }}>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr style={{ background: 'var(--surface-1)' }}>
                                            {['User', 'Plan', 'Queries Today', 'Joined', 'Actions'].map(h => (
                                                <th key={h} className="text-left px-4 py-3 font-semibold"
                                                    style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {users.map(u => {
                                            const plan = PLAN_CONFIG[u.plan] || PLAN_CONFIG.free;
                                            const feedback = userFeedback[u.clerk_id];
                                            const switching = planSwitching[u.clerk_id];
                                            const wiping = wipingUsage[u.clerk_id];
                                            return (
                                                <tr key={u.clerk_id} style={{ borderTop: '1px solid var(--border)' }}>
                                                    {/* User info */}
                                                    <td className="px-4 py-3">
                                                        {/* Display name (real name or email from Clerk) */}
                                                        <div className="font-medium" style={{ color: 'var(--foreground)' }}>
                                                            {u.display_name || u.email}
                                                        </div>
                                                        {/* Show email as secondary if display_name is different */}
                                                        {u.display_name && u.display_name !== u.email && (
                                                            <div className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                                                                {u.email}
                                                            </div>
                                                        )}
                                                        {/* Show clerk_id if email is still a placeholder */}
                                                        {u.email.endsWith('@placeholder.local') ? (
                                                            <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--error)', opacity: 0.7 }}>
                                                                ⚠ placeholder — click Enrich Users
                                                            </div>
                                                        ) : (
                                                            <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--muted-foreground)', opacity: 0.5 }}>
                                                                {u.clerk_id.slice(0, 20)}…
                                                            </div>
                                                        )}
                                                    </td>

                                                    {/* Plan badge */}
                                                    <td className="px-4 py-3">
                                                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
                                                              style={{ background: `${plan.color}18`, color: plan.color }}>
                                                            {plan.icon}{plan.label}
                                                        </span>
                                                    </td>

                                                    {/* Usage today */}
                                                    <td className="px-4 py-3">
                                                        <span className="font-mono font-bold"
                                                              style={{ color: u.used_today > 0 ? 'var(--warning)' : 'var(--muted-foreground)' }}>
                                                            {u.used_today}
                                                        </span>
                                                    </td>

                                                    {/* Joined */}
                                                    <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                                                    </td>

                                                    {/* Actions */}
                                                    <td className="px-4 py-3">
                                                        <div className="flex items-center gap-2 flex-wrap">
                                                            {/* Tier switch */}
                                                            <select
                                                                value={switching || u.plan}
                                                                onChange={e => switchPlan(u.clerk_id, e.target.value)}
                                                                disabled={!!switching}
                                                                className="text-xs px-2 py-1 rounded-lg"
                                                                style={{
                                                                    background: 'var(--surface-2)',
                                                                    border: '1px solid var(--border)',
                                                                    color: 'var(--foreground)',
                                                                    opacity: switching ? 0.5 : 1,
                                                                }}>
                                                                <option value="free">Free</option>
                                                                <option value="professional">Professional</option>
                                                                <option value="enterprise">Enterprise</option>
                                                            </select>

                                                            {/* Wipe usage */}
                                                            <button
                                                                onClick={() => wipeUsage(u.clerk_id)}
                                                                disabled={wiping || u.used_today === 0}
                                                                title="Wipe today's usage"
                                                                className="p-1.5 rounded-lg disabled:opacity-30 transition-colors"
                                                                style={{
                                                                    background: 'var(--error)18',
                                                                    color: 'var(--error)',
                                                                    border: '1px solid var(--error)30',
                                                                }}>
                                                                {wiping ? <RotateCcw size={13} className="animate-spin" /> : <Trash2 size={13} />}
                                                            </button>

                                                            {/* Inline feedback */}
                                                            {feedback && (
                                                                <span className="text-xs font-medium"
                                                                      style={{ color: feedback.type === 'success' ? 'var(--ghana-green)' : 'var(--error)' }}>
                                                                    {feedback.msg}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        {!usersLoading && users.length === 0 && (
                                            <tr>
                                                <td colSpan={5} className="px-4 py-8 text-center"
                                                    style={{ color: 'var(--muted-foreground)' }}>
                                                    {userSearch ? 'No users match your search.' : 'No users found.'}
                                                </td>
                                            </tr>
                                        )}
                                        {usersLoading && (
                                            <tr>
                                                <td colSpan={5} className="px-4 py-8 text-center">
                                                    <RefreshCw size={20} className="animate-spin mx-auto" style={{ color: 'var(--primary)' }} />
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* User pagination */}
                        {usersTotalPages > 1 && (
                            <div className="flex items-center justify-center gap-2">
                                <button onClick={() => setUsersPage(p => Math.max(1, p - 1))} disabled={usersPage === 1}
                                        className="p-2 rounded-lg disabled:opacity-30"
                                        style={{ border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <ChevronLeft size={16} />
                                </button>
                                <span className="text-sm px-3" style={{ color: 'var(--muted-foreground)' }}>
                                    Page {usersPage} of {usersTotalPages}
                                </span>
                                <button onClick={() => setUsersPage(p => Math.min(usersTotalPages, p + 1))} disabled={usersPage === usersTotalPages}
                                        className="p-2 rounded-lg disabled:opacity-30"
                                        style={{ border: '1px solid var(--border)', color: 'var(--foreground)' }}>
                                    <ChevronRight size={16} />
                                </button>
                            </div>
                        )}
                    </div>
                )}

                {/* ── Config Tab ───────────────────────────────────────────── */}
                {activeTab === 'config' && (
                    <div className="max-w-xl space-y-5">
                        <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                            <h2 className="text-sm font-bold mb-1" style={{ color: 'var(--foreground)' }}>Platform Configuration</h2>
                            <p className="text-xs mb-5" style={{ color: 'var(--muted-foreground)' }}>
                                Changes take effect immediately — no restart required.
                            </p>

                            {configDraft ? (
                                <div className="space-y-5">
                                    {/* Free tier limit */}
                                    <ConfigField
                                        label="Free Tier Daily Query Limit"
                                        description="Number of queries a free-tier user can make per UTC day."
                                        type="number"
                                        min={1}
                                        value={configDraft.free_tier_daily_limit}
                                        onChange={v => setConfigDraft(d => d ? { ...d, free_tier_daily_limit: Number(v) } : d)}
                                        unit="queries / day"
                                    />

                                    <div style={{ height: 1, background: 'var(--border)' }} />

                                    {/* Pro price */}
                                    <ConfigField
                                        label="Pro Plan Monthly Price"
                                        description="Shown on the pricing/upgrade page."
                                        type="number"
                                        min={0}
                                        step={0.01}
                                        value={configDraft.pro_monthly_price_ghs}
                                        onChange={v => setConfigDraft(d => d ? { ...d, pro_monthly_price_ghs: Number(v) } : d)}
                                        unit="GHS / month"
                                        color="var(--ghana-gold)"
                                    />

                                    {/* Enterprise price */}
                                    <ConfigField
                                        label="Enterprise Plan Monthly Price"
                                        description="Shown on the pricing/upgrade page."
                                        type="number"
                                        min={0}
                                        step={0.01}
                                        value={configDraft.enterprise_monthly_price_ghs}
                                        onChange={v => setConfigDraft(d => d ? { ...d, enterprise_monthly_price_ghs: Number(v) } : d)}
                                        unit="GHS / month"
                                        color="var(--primary)"
                                    />

                                    {/* Actions */}
                                    <div className="flex items-center gap-3 pt-1">
                                        <button
                                            onClick={saveConfig}
                                            disabled={configSaving || !configChanged}
                                            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-40 transition-opacity"
                                            style={{ background: 'var(--primary)', color: '#fff' }}>
                                            {configSaving
                                                ? <><RotateCcw size={14} className="animate-spin" /> Saving…</>
                                                : <><Save size={14} /> Save Changes</>}
                                        </button>
                                        {configChanged && !configSaving && (
                                            <button
                                                onClick={() => setConfigDraft(platformConfig)}
                                                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm"
                                                style={{ color: 'var(--muted-foreground)', border: '1px solid var(--border)' }}>
                                                <X size={13} /> Discard
                                            </button>
                                        )}
                                        {configFeedback && (
                                            <span className="text-sm font-medium"
                                                  style={{ color: configFeedback.type === 'success' ? 'var(--ghana-green)' : 'var(--error)' }}>
                                                {configFeedback.type === 'success' ? <CheckCircle size={14} className="inline mr-1" /> : <AlertCircle size={14} className="inline mr-1" />}
                                                {configFeedback.msg}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center py-10">
                                    <RefreshCw size={20} className="animate-spin" style={{ color: 'var(--primary)' }} />
                                </div>
                            )}
                        </div>

                        {/* Info card */}
                        <div className="p-4 rounded-xl text-xs space-y-1"
                             style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
                            <p><strong style={{ color: 'var(--foreground)' }}>Free limit</strong> — sets <code>FREE_TIER_DAILY_LIMIT</code> at runtime, overriding the .env value.</p>
                            <p><strong style={{ color: 'var(--foreground)' }}>Prices</strong> — displayed on the upgrade UI. Update Paystack plan prices separately in your Paystack dashboard.</p>
                        </div>
                    </div>
                )}

                {activeTab === 'payments' && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <StatCard
                                label="Total Revenue"
                                value={`GHS ${paymentsRevenue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
                                icon={<CreditCard size={18} />}
                                color="var(--ghana-green)"
                            />
                            <StatCard
                                label="Successful Payments"
                                value={paymentsSuccessCount}
                                icon={<CheckCircle size={18} />}
                                color="var(--ghana-gold)"
                            />
                            <StatCard
                                label="Records"
                                value={paymentsTotal}
                                icon={<FileText size={18} />}
                                color="var(--primary)"
                            />
                        </div>

                        <div className="p-6 rounded-2xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                            <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                                <h2 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>Payment Records</h2>
                                <div className="flex items-center gap-2">
                                    <div className="relative">
                                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted-foreground)' }} />
                                        <input
                                            type="text"
                                            value={paymentSearch}
                                            onChange={e => { setPaymentSearch(e.target.value); setPaymentsPage(1); }}
                                            placeholder="email, clerk_id, reference"
                                            className="pl-9 pr-3 py-2 rounded-lg text-sm"
                                            style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--foreground)', minWidth: 260 }}
                                        />
                                    </div>
                                    <button onClick={fetchPayments}
                                            disabled={paymentsLoading}
                                            className="p-2 rounded-lg disabled:opacity-50"
                                            style={{ color: 'var(--muted-foreground)', border: '1px solid var(--border)' }}>
                                        <RefreshCw size={14} className={paymentsLoading ? 'animate-spin' : ''} />
                                    </button>
                                </div>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm">
                                    <thead>
                                        <tr style={{ color: 'var(--muted-foreground)', borderBottom: '1px solid var(--border)' }}>
                                            <th className="pb-3 font-semibold">Date</th>
                                            <th className="pb-3 font-semibold">Customer</th>
                                            <th className="pb-3 font-semibold">Amount</th>
                                            <th className="pb-3 font-semibold">Plan</th>
                                            <th className="pb-3 font-semibold">Status</th>
                                            <th className="pb-3 font-semibold">Reference</th>
                                            <th className="pb-3 font-semibold">Source</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                                        {paymentsLoading ? (
                                            <tr>
                                                <td colSpan={7} className="py-10 text-center">
                                                    <RefreshCw size={20} className="animate-spin inline" style={{ color: 'var(--primary)' }} />
                                                </td>
                                            </tr>
                                        ) : payments.length === 0 ? (
                                            <tr>
                                                <td colSpan={7} className="py-10 text-center" style={{ color: 'var(--muted-foreground)' }}>
                                                    No payments recorded yet.
                                                </td>
                                            </tr>
                                        ) : payments.map(p => (
                                            <tr key={p.id} className="group transition-colors hover:bg-white/[0.02]">
                                                <td className="py-3 pr-4 whitespace-nowrap text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                    {p.paid_at ? new Date(p.paid_at).toLocaleString() : (p.created_at ? new Date(p.created_at).toLocaleString() : '—')}
                                                </td>
                                                <td className="py-3 pr-4">
                                                    <div className="text-sm" style={{ color: 'var(--foreground)' }}>{p.email || '—'}</div>
                                                    {p.clerk_id && (
                                                        <div className="text-[11px] font-mono truncate max-w-[220px]" style={{ color: 'var(--muted-foreground)' }} title={p.clerk_id}>
                                                            {p.clerk_id}
                                                        </div>
                                                    )}
                                                </td>
                                                <td className="py-3 pr-4 font-mono text-sm font-semibold" style={{ color: 'var(--ghana-green)' }}>
                                                    {p.currency} {p.amount_ghs.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                                                </td>
                                                <td className="py-3 pr-4">
                                                    {p.plan && (
                                                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
                                                              style={{ background: `${PLAN_CONFIG[p.plan]?.color || 'var(--muted-foreground)'}15`, color: PLAN_CONFIG[p.plan]?.color || 'var(--muted-foreground)' }}>
                                                            {PLAN_CONFIG[p.plan]?.icon}
                                                            {PLAN_CONFIG[p.plan]?.label || p.plan}
                                                        </span>
                                                    )}
                                                </td>
                                                <td className="py-3 pr-4">
                                                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
                                                          style={{
                                                              background: p.status === 'success' ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
                                                              color: p.status === 'success' ? 'var(--ghana-green)' : 'var(--error)',
                                                          }}>
                                                        {p.status}
                                                    </span>
                                                </td>
                                                <td className="py-3 pr-4 font-mono text-[11px] truncate max-w-[180px]" style={{ color: 'var(--muted-foreground)' }} title={p.reference}>
                                                    {p.reference}
                                                </td>
                                                <td className="py-3 pr-4 text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                    {p.source === 'webhook' ? 'Webhook' : p.source === 'verify_endpoint' ? 'Verify' : p.source}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            {paymentsTotal > 50 && (
                                <div className="flex items-center justify-between mt-4 pt-4" style={{ borderTop: '1px solid var(--border)' }}>
                                    <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                        Page {paymentsPage} of {Math.ceil(paymentsTotal / 50)} · {paymentsTotal} total
                                    </div>
                                    <div className="flex gap-2">
                                        <button onClick={() => setPaymentsPage(p => Math.max(1, p - 1))}
                                                disabled={paymentsPage === 1}
                                                className="p-2 rounded-lg disabled:opacity-30"
                                                style={{ border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
                                            <ChevronLeft size={14} />
                                        </button>
                                        <button onClick={() => setPaymentsPage(p => p + 1)}
                                                disabled={paymentsPage >= Math.ceil(paymentsTotal / 50)}
                                                className="p-2 rounded-lg disabled:opacity-30"
                                                style={{ border: '1px solid var(--border)', color: 'var(--muted-foreground)' }}>
                                            <ChevronRight size={14} />
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === 'feedback' && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <div className="p-6 rounded-2xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                            <div className="flex items-center justify-between mb-6">
                                <h2 className="text-lg font-bold" style={{ color: 'var(--foreground)' }}>User Feedback</h2>
                                <span className="text-sm font-mono bg-primary/10 text-primary px-3 py-1 rounded-lg">
                                    {feedbacks.length} Total
                                </span>
                            </div>

                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm">
                                    <thead>
                                        <tr style={{ color: 'var(--muted-foreground)', borderBottom: '1px solid var(--border)' }}>
                                            <th className="pb-3 font-semibold w-1/4">User</th>
                                            <th className="pb-3 font-semibold w-1/2">Content</th>
                                            <th className="pb-3 font-semibold w-1/6">Date</th>
                                            <th className="pb-3 font-semibold text-right w-1/12">Action</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y" style={{ borderColor: 'var(--border)' }}>
                                        {feedbacksLoading ? (
                                            <tr>
                                                <td colSpan={4} className="py-10 text-center">
                                                    <RefreshCw size={20} className="animate-spin inline" style={{ color: 'var(--primary)' }} />
                                                </td>
                                            </tr>
                                        ) : feedbacks.length === 0 ? (
                                            <tr>
                                                <td colSpan={4} className="py-10 text-center text-muted-foreground">
                                                    No feedback submissions yet.
                                                </td>
                                            </tr>
                                        ) : feedbacks.map((f: any) => (
                                            <tr key={f.id} className="group transition-colors hover:bg-surface-2/50">
                                                <td className="py-4 pr-4">
                                                    <div className="font-medium" style={{ color: 'var(--foreground)' }}>{f.name}</div>
                                                    <div className="text-xs font-mono" style={{ color: 'var(--muted-foreground)' }}>{f.clerk_id}</div>
                                                </td>
                                                <td className="py-4 pr-4">
                                                    <p className="text-sm whitespace-pre-wrap" style={{ color: 'var(--foreground)' }}>{f.content}</p>
                                                </td>
                                                <td className="py-4 whitespace-nowrap text-xs" style={{ color: 'var(--muted-foreground)' }}>
                                                    {new Date(f.created_at).toLocaleString()}
                                                </td>
                                                <td className="py-4 text-right">
                                                    <button
                                                        onClick={() => deleteFeedback(f.id)}
                                                        disabled={deletingFeedback[f.id]}
                                                        className="p-2 rounded-lg transition-colors hover:bg-error/10 text-error disabled:opacity-50"
                                                        title="Delete feedback"
                                                    >
                                                        {deletingFeedback[f.id] ? <RefreshCw size={16} className="animate-spin" /> : <Trash2 size={16} />}
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                )}

                {/* Loading state */}
                {loading && !stats && (
                    <div className="flex items-center justify-center py-20">
                        <RefreshCw size={24} className="animate-spin" style={{ color: 'var(--primary)' }} />
                    </div>
                )}
            </div>
        </div>
    );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, icon, color }: { label: string; value: number | string; icon: React.ReactNode; color: string }) {
    return (
        <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--muted-foreground)' }}>{label}</span>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: `${color}15`, color }}>{icon}</div>
            </div>
            <span className="text-2xl font-bold" style={{ color }}>{value}</span>
        </div>
    );
}

function BreakdownCard({ title, items }: { title: string; items: { label: string; value: number; color: string }[] }) {
    return (
        <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
            <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--foreground)' }}>{title}</h3>
            <div className="space-y-3">
                {items.map(({ label, value, color }) => (
                    <div key={label} className="flex items-center justify-between gap-3 min-w-0">
                        <div className="flex items-center gap-2 min-w-0 flex-1">
                            <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                            <span className="text-sm capitalize truncate" style={{ color: 'var(--foreground)' }}>{label}</span>
                        </div>
                        <span className="text-sm font-mono font-semibold tabular-nums shrink-0" style={{ color }}>{value.toLocaleString()}</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

function CourtBreakdownCard({ title, items }: { title: string; items: { label: string; value: number }[] }) {
    const total = items.reduce((sum, i) => sum + i.value, 0);
    const max = Math.max(...items.map(i => i.value), 1);

    return (
        <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-4 gap-3">
                <h3 className="text-sm font-semibold" style={{ color: 'var(--foreground)' }}>{title}</h3>
                <span className="text-xs font-mono tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                    {total.toLocaleString()} total
                </span>
            </div>
            <div className="space-y-3">
                {items.map(({ label, value }) => {
                    const pct = total > 0 ? (value / total) * 100 : 0;
                    const barWidth = (value / max) * 100;
                    return (
                        <div key={label} className="min-w-0">
                            <div className="flex items-baseline justify-between gap-3 mb-1.5 min-w-0">
                                <span className="text-sm truncate" style={{ color: 'var(--foreground)' }} title={label}>
                                    {label}
                                </span>
                                <div className="flex items-baseline gap-2 shrink-0">
                                    <span className="text-xs font-mono tabular-nums" style={{ color: 'var(--muted-foreground)' }}>
                                        {pct.toFixed(1)}%
                                    </span>
                                    <span className="text-sm font-mono font-semibold tabular-nums" style={{ color: 'var(--ghana-gold)' }}>
                                        {value.toLocaleString()}
                                    </span>
                                </div>
                            </div>
                            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--surface-2, rgba(127,127,127,0.15))' }}>
                                <div
                                    className="h-full rounded-full transition-all duration-500"
                                    style={{ width: `${barWidth}%`, background: 'var(--ghana-gold)' }}
                                />
                            </div>
                        </div>
                    );
                })}
                {items.length === 0 && (
                    <div className="text-sm" style={{ color: 'var(--muted-foreground)' }}>No data</div>
                )}
            </div>
        </div>
    );
}

function MiniStat({ label, value, color }: { label: string; value: number; color: string }) {
    return (
        <div>
            <div className="text-[11px] uppercase tracking-wider mb-0.5" style={{ color: 'var(--muted-foreground)' }}>{label}</div>
            <div className="text-lg font-bold font-mono" style={{ color }}>{value}</div>
        </div>
    );
}

function ConfigField({
    label, description, type, min, step, value, onChange, unit, color,
}: {
    label: string;
    description: string;
    type: 'number';
    min?: number;
    step?: number;
    value: number;
    onChange: (v: string) => void;
    unit: string;
    color?: string;
}) {
    return (
        <div className="space-y-1.5">
            <label className="text-sm font-semibold" style={{ color: color || 'var(--foreground)' }}>{label}</label>
            <p className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{description}</p>
            <div className="flex items-center gap-2">
                <input
                    type={type}
                    min={min}
                    step={step ?? 1}
                    value={value}
                    onChange={e => onChange(e.target.value)}
                    className="w-36 px-3 py-2 rounded-lg text-sm font-mono font-bold"
                    style={{
                        background: 'var(--surface-2)',
                        border: `1px solid ${color || 'var(--border)'}`,
                        color: color || 'var(--foreground)',
                    }}
                />
                <span className="text-xs" style={{ color: 'var(--muted-foreground)' }}>{unit}</span>
            </div>
        </div>
    );
}

// ─── Bulk Upload Panel ────────────────────────────────────────────────────────

type UploadResult = {
    accepted: { filename: string; case_id: string; court_id: string; size_kb: number }[];
    errors: { filename: string; url: string; error: string }[];
    accepted_count: number;
    error_count: number;
};

function deriveCaseIdFromUrl(url: string): { case_id: string; court_id: string } | null {
    const match = url.match(/\/judgment\/([a-z]+)\/(\d{4})\/(\d+)\//i);
    if (!match) return null;
    const slug = match[1].toLowerCase();
    const slugMap: Record<string, string> = {
        ghasc: 'GHASC', ghaca: 'GHACA', ghahc: 'GHAHC',
        ghacc: 'GHACC', ghadc: 'GHADC', ecowascj: 'ECOWASCJ', afchpr: 'AFCHPR',
    };
    const court_id = slugMap[slug] || 'UNKNOWN';
    return { case_id: `${court_id}_${match[2]}_${match[3]}`, court_id };
}

function BulkUploadPanel({
    onUploaded,
    authHeaders,
}: {
    onUploaded: () => void | Promise<void>;
    authHeaders: () => Promise<Record<string, string>>;
}) {
    const [files, setFiles] = useState<File[]>([]);
    const [urlsText, setUrlsText] = useState('');
    const [uploading, setUploading] = useState(false);
    const [result, setResult] = useState<UploadResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [dragActive, setDragActive] = useState(false);

    const urls = urlsText.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
    const pairs = files.map((f, i) => {
        const url = urls[i] ?? '';
        const derived = url ? deriveCaseIdFromUrl(url) : null;
        return { file: f, url, derived };
    });

    const ready = files.length > 0 && files.length === urls.length && pairs.every(p => p.derived);

    const handleFiles = (fileList: FileList | null) => {
        if (!fileList) return;
        const pdfs = Array.from(fileList).filter(f =>
            f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
        );
        setFiles(prev => [...prev, ...pdfs]);
        setResult(null);
        setError(null);
    };

    const removeFile = (idx: number) => {
        setFiles(prev => prev.filter((_, i) => i !== idx));
        setResult(null);
    };

    const clearAll = () => {
        setFiles([]);
        setUrlsText('');
        setResult(null);
        setError(null);
    };

    const submit = async () => {
        if (!ready) return;
        setUploading(true);
        setError(null);
        setResult(null);

        try {
            const formData = new FormData();
            files.forEach(f => formData.append('files', f));
            formData.append('urls', urls.join('\n'));

            const headers = await authHeaders();
            // Don't set Content-Type — let the browser add the multipart boundary.
            delete (headers as Record<string, string>)['Content-Type'];

            const res = await fetch(`${config.apiUrl}/api/admin/pipeline/upload-cases`, {
                method: 'POST',
                headers,
                body: formData,
            });

            const data = await res.json();
            if (!res.ok) {
                setError(data.detail || `Upload failed (HTTP ${res.status})`);
            } else {
                setResult(data as UploadResult);
                if (data.accepted_count > 0) {
                    await onUploaded();
                    if (data.error_count === 0) {
                        // Clean slate when everything succeeded.
                        setFiles([]);
                        setUrlsText('');
                    }
                }
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Network error');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="p-5 rounded-xl" style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                <div className="min-w-0">
                    <h3 className="text-sm font-bold flex items-center gap-2" style={{ color: 'var(--foreground)' }}>
                        <FilePlus2 size={14} style={{ color: 'var(--ghana-gold)' }} />
                        Bulk Upload — Manually Downloaded PDFs
                    </h3>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--muted-foreground)' }}>
                        Drop PDFs you saved from ghalii, paste their URLs (one per line, in matching order), submit. Ingestion picks them up automatically.
                    </p>
                </div>
                {(files.length > 0 || urlsText) && (
                    <button onClick={clearAll}
                            disabled={uploading}
                            className="text-xs px-3 py-1.5 rounded-lg transition-colors disabled:opacity-40"
                            style={{ background: 'var(--surface-2)', color: 'var(--muted-foreground)' }}>
                        Clear all
                    </button>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
                {/* Dropzone */}
                <div
                    onDragOver={e => { e.preventDefault(); setDragActive(true); }}
                    onDragLeave={() => setDragActive(false)}
                    onDrop={e => {
                        e.preventDefault();
                        setDragActive(false);
                        handleFiles(e.dataTransfer.files);
                    }}
                    className="relative rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer"
                    style={{
                        borderColor: dragActive ? 'var(--ghana-gold)' : 'var(--border)',
                        background: dragActive ? 'rgba(234,179,8,0.04)' : 'var(--surface-2)',
                    }}
                    onClick={() => document.getElementById('bulk-upload-input')?.click()}>
                    <input
                        id="bulk-upload-input"
                        type="file"
                        accept="application/pdf,.pdf"
                        multiple
                        className="hidden"
                        onChange={e => handleFiles(e.target.files)}
                    />
                    <Upload size={28} className="mx-auto mb-2" style={{ color: 'var(--ghana-gold)' }} />
                    <div className="text-sm font-semibold mb-1" style={{ color: 'var(--foreground)' }}>
                        Drop PDFs here or click to choose
                    </div>
                    <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                        {files.length === 0 ? 'Multiple files supported · PDF only' : `${files.length} file${files.length === 1 ? '' : 's'} queued`}
                    </div>
                </div>

                {/* URLs textarea */}
                <div>
                    <label className="text-xs font-semibold uppercase tracking-wider mb-2 block" style={{ color: 'var(--muted-foreground)' }}>
                        Source URLs · one per line · same order as files
                    </label>
                    <textarea
                        value={urlsText}
                        onChange={e => setUrlsText(e.target.value)}
                        placeholder={'https://ghalii.org/akn/gh/judgment/ghasc/2024/15/eng@2024-XX-XX\nhttps://ghalii.org/akn/gh/judgment/ghaca/2023/87/eng@2023-XX-XX'}
                        rows={6}
                        className="w-full px-3 py-2 rounded-lg text-xs font-mono"
                        style={{
                            background: 'var(--surface-2)',
                            border: '1px solid var(--border)',
                            color: 'var(--foreground)',
                            resize: 'vertical',
                        }}
                    />
                    <div className="text-[11px] mt-1" style={{ color: 'var(--muted-foreground)' }}>
                        {urls.length} URL{urls.length === 1 ? '' : 's'} · {files.length} file{files.length === 1 ? '' : 's'}
                        {files.length !== urls.length && (urls.length > 0 || files.length > 0) && (
                            <span style={{ color: 'var(--warning)' }}> · counts must match</span>
                        )}
                    </div>
                </div>
            </div>

            {/* Pair preview table */}
            {pairs.length > 0 && (
                <div className="rounded-lg overflow-hidden mb-4" style={{ border: '1px solid var(--border)' }}>
                    <table className="w-full text-xs">
                        <thead style={{ background: 'var(--surface-2)' }}>
                            <tr>
                                {['#', 'File', 'URL', 'Derived case_id', 'Court', ''].map(h => (
                                    <th key={h} className="px-3 py-2 text-left font-semibold" style={{ color: 'var(--muted-foreground)' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {pairs.map((p, i) => (
                                <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                                    <td className="px-3 py-2 font-mono" style={{ color: 'var(--muted-foreground)' }}>{i + 1}</td>
                                    <td className="px-3 py-2 truncate max-w-[200px]" style={{ color: 'var(--foreground)' }} title={p.file.name}>
                                        {p.file.name}
                                        <span className="ml-2 text-[10px]" style={{ color: 'var(--muted-foreground)' }}>
                                            {(p.file.size / 1024).toFixed(0)} KB
                                        </span>
                                    </td>
                                    <td className="px-3 py-2 truncate max-w-[280px] font-mono text-[11px]" style={{ color: p.url ? 'var(--foreground)' : 'var(--error)' }} title={p.url || 'missing'}>
                                        {p.url || '— missing —'}
                                    </td>
                                    <td className="px-3 py-2 font-mono" style={{ color: p.derived ? 'var(--ghana-gold)' : 'var(--error)' }}>
                                        {p.derived?.case_id || (p.url ? 'invalid URL' : '—')}
                                    </td>
                                    <td className="px-3 py-2 font-mono" style={{ color: 'var(--foreground)' }}>
                                        {p.derived?.court_id || '—'}
                                    </td>
                                    <td className="px-3 py-2">
                                        <button onClick={() => removeFile(i)}
                                                disabled={uploading}
                                                className="p-1 rounded hover:bg-white/5 transition-colors"
                                                title="Remove">
                                            <Trash2 size={12} style={{ color: 'var(--muted-foreground)' }} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Action row */}
            <div className="flex items-center justify-between gap-3 flex-wrap">
                <div className="text-xs" style={{ color: 'var(--muted-foreground)' }}>
                    {ready
                        ? <>Ready: <span className="font-semibold" style={{ color: 'var(--ghana-green)' }}>{files.length}</span> file{files.length === 1 ? '' : 's'} will be uploaded</>
                        : files.length === 0
                            ? 'Add files and matching URLs to begin'
                            : 'Fix mismatches above to enable upload'}
                </div>
                <button
                    onClick={submit}
                    disabled={!ready || uploading}
                    className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold disabled:opacity-40 transition-opacity"
                    style={{ background: 'var(--ghana-gold)', color: '#000' }}>
                    {uploading
                        ? <><RefreshCw size={13} className="animate-spin" /> Uploading…</>
                        : <><Upload size={13} /> Upload {files.length || ''} PDF{files.length === 1 ? '' : 's'}</>}
                </button>
            </div>

            {/* Result */}
            {result && (
                <div className="mt-4 p-3 rounded-lg text-xs"
                     style={{
                         background: result.error_count === 0 ? 'var(--ghana-green)08' : 'var(--warning)08',
                         border: `1px solid ${result.error_count === 0 ? 'var(--ghana-green)30' : 'var(--warning)30'}`,
                         color: result.error_count === 0 ? 'var(--ghana-green)' : 'var(--warning)',
                     }}>
                    <div className="font-semibold mb-1">
                        ✓ Accepted {result.accepted_count}{result.error_count > 0 && ` · ✗ Failed ${result.error_count}`}
                    </div>
                    {result.error_count > 0 && (
                        <ul className="mt-2 space-y-1 font-mono text-[11px]" style={{ color: 'var(--error)' }}>
                            {result.errors.map((e, i) => (
                                <li key={i}>• {e.filename}: {e.error}</li>
                            ))}
                        </ul>
                    )}
                    {result.accepted_count > 0 && (
                        <div className="mt-2 text-[11px]" style={{ color: 'var(--foreground)' }}>
                            Run ingestion next to embed them.
                        </div>
                    )}
                </div>
            )}

            {error && (
                <div className="mt-4 p-3 rounded-lg text-xs"
                     style={{ background: 'var(--error)08', border: '1px solid var(--error)30', color: 'var(--error)' }}>
                    ✗ {error}
                </div>
            )}
        </div>
    );
}
