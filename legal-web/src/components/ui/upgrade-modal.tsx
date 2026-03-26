'use client';

import React, { useEffect, useState } from 'react';
import { X, Check, Zap, Shield, Scale, ArrowRight } from 'lucide-react';
import { useUser } from '@clerk/nextjs';
import { useUsage } from '@/hooks/use-usage';
import { cn } from '@/lib/utils';
import Script from 'next/script';

interface UpgradeModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function UpgradeModal({ isOpen, onClose }: UpgradeModalProps) {
    const { usage } = useUsage();
    const { user } = useUser();
    const [isMounted, setIsMounted] = useState(false);

    useEffect(() => {
        setIsMounted(true);
    }, []);

    if (!isMounted || !isOpen) return null;

    const currentPlan = usage?.plan || 'free';

    const handleUpgradeClick = (e: React.MouseEvent) => {
        e.preventDefault();
        
        // Ensure Paystack JS is loaded
        // @ts-ignore
        if (typeof window.PaystackPop !== 'undefined') {
            // @ts-ignore
            const handler = window.PaystackPop.setup({
                key: process.env.NEXT_PUBLIC_PAYSTACK_PUBLIC_KEY || '', // TODO: Add your Paystack Public Key here!
                email: user?.primaryEmailAddress?.emailAddress || 'user@ghanalegal.ai',
                amount: 15000, // 150 GHS in pesewas
                currency: 'GHS',
                // plan: process.env.NEXT_PUBLIC_PAYSTACK_PRO_PLAN, // Add this if it's a recurring subscription plan code
                callback: function(response: any) {
                    console.log('Payment complete! Reference: ' + response.reference);
                    // The backend Paystack Webhook will automatically provision the user.
                    // You could also poll /api/usage here to show immediate success.
                    onClose();
                },
                onClose: function() {
                    console.log('Payment modal closed');
                }
            });
            handler.openIframe();
        } else {
            // Fallback to payment link if script failed
            window.open('https://paystack.com/pay/ghana-legal-pro', '_blank');
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6"
             style={{ background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)' }}>
             
            <Script src="https://js.paystack.co/v1/inline.js" strategy="lazyOnload" />
            
            {/* Modal Container */}
            <div className="relative w-full max-w-5xl rounded-3xl overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200"
                 style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}>
                
                {/* Close Button */}
                <button 
                    onClick={onClose}
                    className="absolute top-4 right-4 z-10 p-2 rounded-full hover:bg-white/10 transition-colors"
                    style={{ color: 'var(--muted-foreground)' }}
                >
                    <X size={20} />
                </button>

                <div className="p-8 md:p-12 text-center border-b border-white/5 relative overflow-hidden">
                    {/* Background glow */}
                    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full max-w-3xl opacity-30 pointer-events-none"
                         style={{ background: 'radial-gradient(circle, var(--primary-muted) 0%, transparent 70%)' }} />
                         
                    <h2 className="text-3xl md:text-4xl font-bold mb-4 tracking-tight" style={{ color: 'var(--foreground)' }}>
                        Unlock the Full Power of <span style={{ color: 'var(--ghana-gold)' }}>Ghana Legal AI</span>
                    </h2>
                    <p className="text-lg max-w-2xl mx-auto" style={{ color: 'var(--muted-foreground)' }}>
                        Get unlimited answers, deeper research, and export tools tailored for legal professionals and everyday citizens.
                    </p>
                </div>

                {/* Pricing Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-0 divide-y md:divide-y-0 md:divide-x divide-white/10"
                     style={{ background: 'var(--surface-2)' }}>
                    
                    {/* Free Tier */}
                    <div className="p-8 md:p-10 flex flex-col relative transition-colors duration-300 hover:bg-white/[0.02]">
                        {currentPlan === 'free' && (
                            <div className="absolute top-0 right-0 px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-bl-xl rounded-tr-3xl"
                                 style={{ background: 'var(--surface-3)', color: 'var(--muted-foreground)' }}>
                                Current
                            </div>
                        )}
                        <h3 className="text-xl font-bold mb-2">Basic</h3>
                        <div className="flex items-baseline gap-1 mb-6">
                            <span className="text-3xl font-bold">Free</span>
                        </div>
                        <p className="text-sm mb-8 flex-1" style={{ color: 'var(--muted-foreground)' }}>
                            Essential legal AI for quick insights and general research.
                        </p>
                        
                        <ul className="space-y-4 mb-8">
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>5 legal queries per day</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>Access to Constitutional Expert</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>Standard response speed</span>
                            </li>
                        </ul>
                        
                        <button 
                            disabled
                            className="w-full py-3.5 rounded-xl text-sm font-semibold opacity-50 cursor-not-allowed border"
                            style={{ borderColor: 'var(--border)', color: 'var(--muted-foreground)' }}
                        >
                            {currentPlan === 'free' ? 'Current Plan' : 'Downgrade'}
                        </button>
                    </div>

                    {/* Pro Tier (Highlight) */}
                    <div className="p-8 md:p-10 flex flex-col relative"
                         style={{ 
                             background: 'linear-gradient(to bottom, var(--primary-muted), transparent)',
                             boxShadow: 'inset 0 2px 0 var(--primary)'
                         }}>
                        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 px-4 py-1 text-[11px] font-bold uppercase tracking-widest rounded-full shadow-lg"
                             style={{ background: 'var(--primary)', color: 'white' }}>
                            Most Popular
                        </div>
                        
                        <div className="flex items-center gap-2 mb-2">
                            <Zap size={20} style={{ color: 'var(--primary)' }} />
                            <h3 className="text-xl font-bold" style={{ color: 'var(--primary)' }}>Professional</h3>
                        </div>
                        <div className="flex items-baseline gap-1 mb-6">
                            <span className="text-4xl font-bold text-white">₵150</span>
                            <span className="text-sm" style={{ color: 'var(--muted-foreground)' }}>/month</span>
                        </div>
                        <p className="text-sm mb-8 flex-1 text-white/80">
                            Unrestricted AI assistance built specifically for legal practitioners and law students.
                        </p>
                        
                        <ul className="space-y-4 mb-8">
                            <li className="flex gap-3 text-sm font-medium text-white">
                                <Check size={18} style={{ color: 'var(--primary)' }} />
                                <span>Unlimited legal queries</span>
                            </li>
                            <li className="flex gap-3 text-sm text-white/80">
                                <Check size={18} style={{ color: 'var(--primary)' }} />
                                <span>Access to all specialized experts</span>
                            </li>
                            <li className="flex gap-3 text-sm text-white/80">
                                <Check size={18} style={{ color: 'var(--primary)' }} />
                                <span>Priority response speed</span>
                            </li>
                            <li className="flex gap-3 text-sm text-white/80">
                                <Check size={18} style={{ color: 'var(--primary)' }} />
                                <span>Export chats to PDF/TXT</span>
                            </li>
                        </ul>
                        
                        <button 
                            onClick={handleUpgradeClick}
                            className="w-full py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-transform hover:scale-[1.02] active:scale-[0.98]"
                            style={{ background: 'var(--primary)', color: 'white', boxShadow: '0 8px 24px rgba(91,106,240,0.3)' }}
                        >
                            {currentPlan === 'professional' ? 'Manage Subscription' : 'Upgrade to Pro'}
                            <ArrowRight size={16} />
                        </button>
                    </div>

                    {/* Enterprise Tier */}
                    <div className="p-8 md:p-10 flex flex-col transition-colors duration-300 hover:bg-white/[0.02]">
                        <div className="flex items-center gap-2 mb-2">
                            <Shield size={20} style={{ color: 'var(--ghana-gold)' }} />
                            <h3 className="text-xl font-bold">Enterprise</h3>
                        </div>
                        <div className="flex items-baseline gap-1 mb-6">
                            <span className="text-3xl font-bold">Custom</span>
                        </div>
                        <p className="text-sm mb-8 flex-1" style={{ color: 'var(--muted-foreground)' }}>
                            Tailored AI solutions for law firms and corporate legal departments.
                        </p>
                        
                        <ul className="space-y-4 mb-8">
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>Everything in Professional</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>Upload internal documents securely</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>API Access for integration</span>
                            </li>
                            <li className="flex gap-3 text-sm">
                                <Check size={18} style={{ color: 'var(--muted-foreground)' }} />
                                <span>Dedicated account manager</span>
                            </li>
                        </ul>
                        
                        <button 
                            onClick={() => window.location.href = 'mailto:sales@ghanalegal.ai'}
                            className="w-full py-3.5 rounded-xl text-sm font-semibold transition-colors border hover:bg-white/5"
                            style={{ borderColor: 'var(--border)', color: 'var(--foreground)' }}
                        >
                            Contact Sales
                        </button>
                    </div>

                </div>
                
                <div className="p-4 text-center text-xs" style={{ background: 'var(--surface-1)', color: 'var(--muted-foreground)', borderTop: '1px solid var(--border)' }}>
                    Payments are securely processed by Paystack. Cancel anytime.
                </div>
            </div>
        </div>
    );
}
