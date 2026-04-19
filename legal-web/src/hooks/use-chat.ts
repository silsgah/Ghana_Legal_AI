'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@clerk/nextjs';
import { config } from '@/lib/config';

export interface Source {
    title: string;
    court: string;
    year: string;
    document_type: string;
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    sources?: Source[];
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseChatOptions {
    expertId: string;
    onStreamComplete?: () => void;
}

interface UseChatReturn {
    messages: Message[];
    sendMessage: (text: string) => void;
    resetChat: () => Promise<void>;
    isStreaming: boolean;
    connectionStatus: ConnectionStatus;
    reconnect: () => void;
}

const generateId = () => Math.random().toString(36).substring(2, 15);

export function useChat({ expertId, onStreamComplete }: UseChatOptions): UseChatReturn {
    const { getToken } = useAuth();
    const [messages, setMessages] = useState<Message[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connected');
    const [historyLoaded, setHistoryLoaded] = useState(false);

    const currentExpertId = useRef(expertId);
    const abortControllerRef = useRef<AbortController | null>(null);

    // Update ref when expertId changes
    useEffect(() => {
        currentExpertId.current = expertId;
    }, [expertId]);

    // Load conversation history when expert changes
    useEffect(() => {
        const loadHistory = async () => {
            try {
                const token = await getToken();
                if (!token) return;

                const res = await fetch(`${config.apiUrl}/api/history/${currentExpertId.current}`, {
                    headers: { Authorization: `Bearer ${token}` },
                });

                if (!res.ok) return;

                const data = await res.json();
                if (data.messages && data.messages.length > 0) {
                    const loadedMessages: Message[] = data.messages.map((msg: { role: string; content: string }, i: number) => ({
                        id: `history_${i}`,
                        role: msg.role as 'user' | 'assistant',
                        content: msg.content,
                        timestamp: new Date(),
                    }));
                    setMessages(loadedMessages);
                } else {
                    setMessages([]);
                }
            } catch (err) {
                console.error('Failed to load history:', err);
                setMessages([]);
            } finally {
                setHistoryLoaded(true);
            }
        };

        setHistoryLoaded(false);
        loadHistory();
    }, [expertId]);

    const sendMessage = useCallback(async (text: string) => {
        // Cancel any existing stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }

        // Add user message
        const userMessage: Message = {
            id: generateId(),
            role: 'user',
            content: text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);

        setIsStreaming(true);
        setConnectionStatus('connected');

        try {
            const token = await getToken();
            const abortController = new AbortController();
            abortControllerRef.current = abortController;

            const response = await fetch(`${config.apiUrl}/chat/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    message: text,
                    expert_id: currentExpertId.current,
                }),
                signal: abortController.signal,
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete SSE lines
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;

                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.chunk) {
                            // Append chunk or create assistant message
                            setMessages((prev) => {
                                const lastMsg = prev[prev.length - 1];
                                if (lastMsg?.role === 'assistant') {
                                    return [
                                        ...prev.slice(0, -1),
                                        { ...lastMsg, content: lastMsg.content + data.chunk },
                                    ];
                                } else {
                                    return [
                                        ...prev,
                                        { id: generateId(), role: 'assistant', content: data.chunk, timestamp: new Date() }
                                    ];
                                }
                            });
                        } else if (data.sources && data.sources.length > 0) {
                            // Attach sources to assistant message
                            setMessages((prev) => {
                                const lastMsg = prev[prev.length - 1];
                                if (lastMsg?.role === 'assistant') {
                                    return [
                                        ...prev.slice(0, -1),
                                        { ...lastMsg, sources: data.sources },
                                    ];
                                } else {
                                    return [
                                        ...prev,
                                        { id: generateId(), role: 'assistant', content: '', sources: data.sources, timestamp: new Date() }
                                    ];
                                }
                            });
                        } else if (data.error) {
                            console.error('Stream error:', data.error);
                            setMessages((prev) => {
                                const lastMsg = prev[prev.length - 1];
                                if (lastMsg?.role === 'assistant' && lastMsg.content === '') {
                                    return [
                                        ...prev.slice(0, -1),
                                        {
                                            ...lastMsg,
                                            content: data.quota_exceeded
                                                ? `⚠️ ${data.error}`
                                                : `I apologize, but I encountered an error: ${data.error}`,
                                        },
                                    ];
                                }
                                return prev;
                            });
                        } else if (data.done) {
                            // Stream complete
                            onStreamComplete?.();
                        }
                    } catch {
                        // Skip malformed JSON lines
                    }
                }
            }
        } catch (err: unknown) {
            if (err instanceof Error && err.name === 'AbortError') {
                // User cancelled — not an error
                return;
            }
            console.error('Stream request failed:', err);
            setConnectionStatus('error');
            setMessages((prev) => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg?.role === 'assistant' && lastMsg.content === '') {
                    return [
                        ...prev.slice(0, -1),
                        {
                            ...lastMsg,
                            content: 'Connection failed. Please check your network and try again.',
                        },
                    ];
                }
                return prev;
            });
        } finally {
            setIsStreaming(false);
            abortControllerRef.current = null;
        }
    }, [getToken, onStreamComplete]);

    const resetChat = useCallback(async () => {
        // Abort any in-flight stream
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        setMessages([]);
        try {
            const token = await getToken();
            await fetch(`${config.apiUrl}/reset-memory`, {
                method: 'POST',
                headers: token ? { Authorization: `Bearer ${token}` } : {},
            });
        } catch (error) {
            console.error('Failed to reset memory:', error);
        }
    }, [getToken]);

    const reconnect = useCallback(() => {
        setConnectionStatus('connected');
    }, []);

    return {
        messages,
        sendMessage,
        resetChat,
        isStreaming,
        connectionStatus,
        reconnect,
    };
}
