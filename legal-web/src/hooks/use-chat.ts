'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { config } from '@/lib/config';

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface UseChatOptions {
    expertId: string;
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

export function useChat({ expertId }: UseChatOptions): UseChatReturn {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const reconnectAttempts = useRef(0);
    const maxReconnectAttempts = 5;
    const currentExpertId = useRef(expertId);

    // Update ref when expertId changes
    useEffect(() => {
        currentExpertId.current = expertId;
    }, [expertId]);

    const connectRef = useRef<() => void>(() => { });

    const connect = useCallback(() => {
        // Clean up existing connection
        if (wsRef.current) {
            wsRef.current.close();
        }

        setConnectionStatus('connecting');

        try {
            const ws = new WebSocket(`${config.wsUrl}/ws/chat`);

            ws.onopen = () => {
                console.log('WebSocket connected');
                setConnectionStatus('connected');
                reconnectAttempts.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.streaming === true && !data.chunk) {
                        // Stream starting
                        setIsStreaming(true);
                    } else if (data.chunk) {
                        // Append chunk to last assistant message
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
                                    {
                                        id: generateId(),
                                        role: 'assistant',
                                        content: data.chunk,
                                        timestamp: new Date(),
                                    },
                                ];
                            }
                        });
                    } else if (data.streaming === false) {
                        // Stream complete
                        setIsStreaming(false);
                    } else if (data.error) {
                        console.error('WebSocket error:', data.error);
                        setIsStreaming(false);
                        setMessages((prev) => [
                            ...prev,
                            {
                                id: generateId(),
                                role: 'assistant',
                                content: `I apologize, but I encountered an error: ${data.error}`,
                                timestamp: new Date(),
                            },
                        ]);
                    }
                } catch (e) {
                    console.error('Failed to parse message:', e);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setConnectionStatus('error');
            };

            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setConnectionStatus('disconnected');
                setIsStreaming(false);

                // Attempt reconnection with exponential backoff
                if (reconnectAttempts.current < maxReconnectAttempts) {
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
                    console.log(`Reconnecting in ${delay}ms...`);
                    reconnectTimeoutRef.current = setTimeout(() => {
                        reconnectAttempts.current++;
                        connectRef.current();
                    }, delay);
                }
            };

            wsRef.current = ws;
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            setConnectionStatus('error');
        }
    }, []);

    // Update ref
    useEffect(() => {
        connectRef.current = connect;
    }, [connect]);

    // Initialize connection
    useEffect(() => {
        const timer = setTimeout(() => {
            connect();
        }, 0);

        return () => {
            clearTimeout(timer);
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
            }
        };
    }, [connect]);

    const sendMessage = useCallback((text: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.error('WebSocket not connected');
            return;
        }

        // Add user message
        const userMessage: Message = {
            id: generateId(),
            role: 'user',
            content: text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);

        // Send to backend
        wsRef.current.send(
            JSON.stringify({
                message: text,
                expert_id: currentExpertId.current,
            })
        );
    }, []);

    const resetChat = useCallback(async () => {
        try {
            await fetch(`${config.apiUrl}/reset-memory`, { method: 'POST' });
            setMessages([]);
        } catch (error) {
            console.error('Failed to reset memory:', error);
        }
    }, []);

    const reconnect = useCallback(() => {
        reconnectAttempts.current = 0;
        connect();
    }, [connect]);

    return {
        messages,
        sendMessage,
        resetChat,
        isStreaming,
        connectionStatus,
        reconnect,
    };
}
