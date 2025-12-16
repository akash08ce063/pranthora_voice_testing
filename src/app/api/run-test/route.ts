import { NextResponse } from 'next/server';

const PYTHON_API_URL = 'http://127.0.0.1:8000/test';

export async function POST(request: Request) {
  try {
    const body = await request.json()
    const { agentId, agentPhoneNumber, testerAgents, scenarios } = body

    if (!agentId || !agentPhoneNumber || !testerAgents || !scenarios) {
      return NextResponse.json(
        { error: 'Missing required fields: agentId, agentPhoneNumber, testerAgents, scenarios' },
        { status: 400 }
      )
    }

    // Agent validation (optional, can just trust the phone number if needed, or keeping basic checks)
    // For now we trust the phone number passed from the client which came from our /agents API


    // 2. Create Config Payload
    const overridePhoneNumber = process.env.TEST_PHONE_NUMBER

    // Define minimal types for the input to avoid 'any'
    interface AgentInput {
        name: string;
        prompt: string;
        voice_id?: string;
    }

    interface ScenarioInput {
        name: string;
        prompt: string;
        evaluations: unknown[];
    }

    const configPayload = {
        phone_number_to_call: overridePhoneNumber || agentPhoneNumber,
        // Optional: Pass twilio_phone_number if needed, otherwise Python server defaults or uses env
        agents: (testerAgents as AgentInput[]).map((agent) => ({
            name: agent.name,
            prompt: agent.prompt,
            voice_id: agent.voice_id
        })),
        scenarios: (scenarios as ScenarioInput[]).map((scenario) => ({
            name: scenario.name,
            prompt: scenario.prompt,
            evaluations: scenario.evaluations || []
        }))
    }

    // 3. Call Python FastAPI Server
    try {
        const response = await fetch(PYTHON_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(configPayload),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errorData.detail || `Server error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();

        // The Python server returns { results: [...], passed: boolean }
        // The frontend might expect specific format, but usually we just return what we got.
        // Based on previous code, it returned the raw JSON output from the script.

        return NextResponse.json(data);

    } catch (fetchError: unknown) {
        // Type guard for fetch errors or connection errors
        const isConnectionError = (err: unknown): boolean => {
            return (
                (typeof err === 'object' && err !== null && 'cause' in err && (err as { cause?: { code?: string } }).cause?.code === 'ECONNREFUSED') ||
                (err instanceof Error && err.message.includes('ECONNREFUSED'))
            );
        };

        if (isConnectionError(fetchError)) {
             return NextResponse.json(
                { error: 'Python Test Server is not running. Please run `uv run scripts/api.py`.' },
                { status: 503 }
            )
        }
        throw fetchError;
    }

  } catch (error: unknown) {
    console.error('Error running test:', error)
    const errorMessage = error instanceof Error ? error.message : 'Internal server error'
    return NextResponse.json(
      { error: errorMessage },
      { status: 500 }
    )
  }
}

