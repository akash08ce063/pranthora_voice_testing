'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTestStore } from '@/src/store/useTestStore';
import { Terminal } from 'lucide-react';
import { useEffect, useRef } from 'react';

export function LogStreamViewer() {
    const { logs, addLog, isLoading, setTestResults, setIsLoading } = useTestStore();
    const endRef = useRef<HTMLDivElement>(null);

    // Connect to log stream only when test is running
    // Actually, with the new async architecture, we might want to stay connected or connect on demand.
    // For now, let's keep the logic bound to `isLoading` but handle the 'result' event to turn it off.
    useEffect(() => {
        // Only connect if a test is currently running
        if (!isLoading) {
            return;
        }

        let eventSource: EventSource | null = null;

        const connectLogs = () => {
            // Close existing if open (though useEffect cleanup handles this)
            if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
                eventSource.close();
            }

            // Direct connection to Python backend (port 8000)
            // Dynamically determine host to support LAN/Remote access
            const protocol = window.location.protocol;
            const hostname = window.location.hostname;
            const backendUrl = `${protocol}//${hostname}:8000/logs`;

            eventSource = new EventSource(backendUrl);

            eventSource.onopen = () => {
                console.log('Connected to log stream');
            };

            eventSource.onmessage = (event) => {
                try {
                    // Parse the event data which is now a JSON string containing type and payload
                    const data = JSON.parse(event.data);

                    if (data.type === 'log') {
                        addLog(data.payload);
                    } else if (data.type === 'result') {
                        console.log("Received test results:", data.payload);
                        setTestResults(data.payload);
                        setIsLoading(false);
                        eventSource?.close(); // Stop listening explicitly
                    } else if (data.type === 'error') {
                        console.error("Received error:", data.payload);
                        addLog(`ERROR: ${data.payload}`);
                        setIsLoading(false);
                        eventSource?.close();
                    }
                } catch (e) {
                    // Fallback for raw string logs if any legacy ones come through
                    console.warn('Error parsing log event, treating as raw text:', e);
                    addLog(event.data);
                }
            };

            eventSource.onerror = (err) => {
                console.error('Log stream error:', err);
                // Don't close immediately on error, might be temporary
            };
        };

        connectLogs();

        return () => {
            eventSource?.close();
        };
    }, [addLog, isLoading, setTestResults, setIsLoading]);

    // Auto-scroll to bottom
    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <Card className="flex flex-col h-full bg-zinc-950 border-zinc-800 shadow-inner">
            <CardHeader className="py-3 px-4 border-b border-zinc-800 bg-zinc-900/50">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-mono text-zinc-400 flex items-center gap-2">
                        <Terminal className="w-4 h-4" />
                        System Logs
                    </CardTitle>
                    <Badge variant="outline" className="text-[10px] border-zinc-700 text-zinc-500 bg-zinc-900">
                        {logs.length} Lines
                    </Badge>
                </div>
            </CardHeader>
            <CardContent className="p-0 flex-1 min-h-[200px] h-[300px]">
                <ScrollArea className="h-full w-full p-4">
                    <div className="font-mono text-xs text-zinc-300 space-y-1">
                        {logs.length === 0 && (
                            <div className="text-zinc-600 italic">Waiting for logs...</div>
                        )}
                        {logs.map((log, i) => (
                            <div key={i} className="whitespace-pre-wrap break-all border-b border-zinc-900/50 pb-0.5 mb-0.5 last:border-0">
                                <span className="text-zinc-600 mr-2 select-none">{i + 1}</span>
                                {log}
                            </div>
                        ))}
                        <div ref={endRef} />
                    </div>
                </ScrollArea>
            </CardContent>
        </Card>
    );
}
