'use client';

import { Button } from '@/components/ui/button';
import { useTestStore } from '@/src/store/useTestStore';
import { Play } from 'lucide-react';

export function TestRunnerControl() {
    const {
        agents,
        selectedAgentId,
        testerAgents,
        scenarios,
        setTestResults,
        setIsLoading,
        isLoading, // Add this
        clearLogs,
        addLog
    } = useTestStore();

    // Removed local isRunning state

    const handleRunTest = async () => {
        if (!selectedAgentId) {
             // Should be handled by validation ideally
             return;
        }

        setIsLoading(true);
        setTestResults(null);
        clearLogs();
        addLog('Starting test suite execution...');

        try {
            // Get the selected agent's phone number
            const selectedAgent = agents.find(a => a.id === selectedAgentId);
            if (!selectedAgent) {
                addLog('ERROR: Selected agent not found');
                setIsLoading(false);
                return;
            }

            // Transform the payload to match Python API's TestConfig model
            const payload = {
                phone_number_to_call: selectedAgent.phoneNumber,
                agents: testerAgents.map(agent => ({
                    name: agent.name,
                    prompt: agent.prompt,
                    ...(agent.voice_id && { voice_id: agent.voice_id })
                })),
                scenarios: scenarios.map(scenario => ({
                    name: scenario.name,
                    prompt: scenario.prompt,
                    evaluations: scenario.evaluations.map(evaluation => ({
                        name: evaluation.name,
                        prompt: evaluation.prompt
                    }))
                }))
            };

            const response = await fetch('/api/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                // Async job started successfully.
                // We keep isLoading(true). The LogStreamViewer will listen for the 'result' event
                // and call setTestResults(results) and setIsLoading(false).
                addLog(`Job started: ${data.job_id}. Waiting for completion...`);
            } else {
                console.error('Test run failed to start:', data.error || data.detail);
                addLog(`ERROR: Test run failed to start: ${data.error || data.detail}`);
                setIsLoading(false); // Only reset if start failed
            }
        } catch (error) {
            console.error('Network error during test:', error);
            addLog(`ERROR: Network error during test execution.`);
            setIsLoading(false);
        }
        // NOTE: We do NOT set setIsRunning(false) or setIsLoading(false) here on success.
        // That happens when the SSE 'result' event is received.
    };

    const isValid = selectedAgentId && testerAgents.length > 0 && scenarios.length > 0;

    return (
        <div className="flex flex-col gap-4">
             <Button
                size="lg"
                className="w-full text-lg h-14 font-semibold shadow-lg hover:shadow-xl transition-all"
                onClick={handleRunTest}
                disabled={isLoading || !isValid}
            >
                {isLoading ? (
                    <>
                        <div className="h-5 w-5 animate-spin rounded-full border-b-2 border-white mr-2"></div>
                        Running Tests...
                    </>
                ) : (
                    <>
                        <Play className="w-5 h-5 mr-2 fill-current" />
                        Run Test Suite
                    </>
                )}
            </Button>
            {!isValid && (
                 <p className="text-xs text-center text-red-500 animate-pulse">
                     Select a target agent, at least one tester, and one scenario to run.
                 </p>
            )}
        </div>
    );
}
