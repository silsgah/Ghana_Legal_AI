'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@clerk/nextjs';
import { config } from '@/lib/config';

export interface Source {
    title: string;
    court: string;
    year: string;
    document_type: string;
    case_id?: string;
    paragraph_id?: string;
}

// Mirrors the backend Pydantic LegalAnswer envelope (PR 2 + PR 4).
export type ClaimKind = 'direct' | 'synthesis' | 'constitutional';
export type ConfidenceTier = 'high' | 'medium' | 'low' | 'insufficient';

export interface Citation {
    case_id: string;
    paragraph_id: string;
    case_title?: string | null;
    court?: string | null;
    year?: number | null;
}

export interface Claim {
    text: string;
    kind: ClaimKind;
    citations: Citation[];
}

export interface LegalAnswer {
    claims: Claim[];
    holding?: string | null;
    principle?: string | null;
    human_text: string;
    retrieval_used: boolean;
    confidence?: ConfidenceTier | null;
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    sources?: Source[];
    envelope?: LegalAnswer;
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
const RETRYABLE_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504]);
const STREAM_TIMEOUT_MS = 75_000;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

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

        let receivedAnswer = false;
        let completed = false;
        let timedOut = false;

        const addAssistantMessage = (content: string) => {
            setMessages((prev) => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg?.role === 'assistant') {
                    return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content || content }];
                }
                return [...prev, { id: generateId(), role: 'assistant', content, timestamp: new Date() }];
            });
        };

        try {
            const token = await getToken();
            const abortController = new AbortController();
            abortControllerRef.current = abortController;

            let response: Response | undefined;
            let lastError: unknown;
            for (let attempt = 0; attempt < 2; attempt += 1) {
                const timeoutId = window.setTimeout(() => {
                    timedOut = true;
                    abortController.abort();
                }, STREAM_TIMEOUT_MS);
                try {
                    const candidate = await fetch(`${config.apiUrl}/chat/stream`, {
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
                    if (candidate.ok || !RETRYABLE_STATUS_CODES.has(candidate.status) || attempt === 1) {
                        response = candidate;
                        break;
                    }
                    lastError = new Error(`HTTP ${candidate.status}: ${candidate.statusText}`);
                } catch (error) {
                    lastError = error;
                    if (abortController.signal.aborted || attempt === 1) throw error;
                } finally {
                    window.clearTimeout(timeoutId);
                }
                await wait(1_000 * (attempt + 1));
            }

            if (!response) throw lastError || new Error('Unable to start response stream');

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
                            receivedAnswer = true;
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
                        } else if (data.envelope) {
                            // Attach the structured LegalAnswer to the assistant message.
                            // The bubble uses it for confidence badge, per-claim citations,
                            // and the insufficient-confidence refusal card.
                            setMessages((prev) => {
                                const lastMsg = prev[prev.length - 1];
                                if (lastMsg?.role === 'assistant') {
                                    return [
                                        ...prev.slice(0, -1),
                                        { ...lastMsg, envelope: data.envelope },
                                    ];
                                } else {
                                    return [
                                        ...prev,
                                        { id: generateId(), role: 'assistant', content: '', envelope: data.envelope, timestamp: new Date() }
                                    ];
                                }
                            });
                        } else if (data.error) {
                            console.error('Stream error:', data.error);
                            addAssistantMessage(
                                data.quota_exceeded
                                    ? `⚠️ ${data.error}`
                                    : `I’m sorry, but I couldn’t complete that request: ${data.error}`,
                            );
                        } else if (data.done) {
                            // Stream complete
                            completed = true;
                            onStreamComplete?.();
                        }
                    } catch {
                        // Skip malformed JSON lines
                    }
                }
            }

            if (!receivedAnswer && !completed) {
                setConnectionStatus('error');
                addAssistantMessage('The research service ended without an answer. Please try again.');
            } else if (!receivedAnswer) {
                addAssistantMessage('The research service did not return an answer. Please try again.');
            }
        } catch (err: unknown) {
            if (err instanceof Error && err.name === 'AbortError') {
                // User cancelled — not an error. A request timeout is visible
                // to the user and can be retried from the status control.
                if (!timedOut) return;
            }
            console.error('Stream request failed:', err);
            setConnectionStatus('error');
            addAssistantMessage('Connection to the research service failed. Please try again in a moment.');
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
            // Scope the wipe to the active expert so other experts' history survives.
            const url = `${config.apiUrl}/reset-memory?expert_id=${encodeURIComponent(currentExpertId.current)}`;
            await fetch(url, {
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
