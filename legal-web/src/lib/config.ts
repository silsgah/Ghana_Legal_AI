/**
 * Environment configuration
 */

const getEnvVar = (key: string, defaultValue: string): string => {
    if (typeof window !== 'undefined') {
        // Client-side: use NEXT_PUBLIC_ prefixed vars
        return (process.env[`NEXT_PUBLIC_${key}`] as string) || defaultValue;
    }
    return (process.env[key] as string) || defaultValue;
};

export const config = {
    apiUrl: getEnvVar('API_URL', 'http://localhost:8000'),
    wsUrl: getEnvVar('WS_URL', 'ws://localhost:8000'),
} as const;
