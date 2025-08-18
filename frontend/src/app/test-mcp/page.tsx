'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

export default function TestMCPPage() {
  const [tools, setTools] = useState<any[]>([]);
  const [testResults, setTestResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Discover available tools
  const discoverTools = async () => {
    const response = await fetch('/api/agent/mcp');
    const data = await response.json();
    setTools(data.availableTools);
  };
  
  // Test a specific company
  const testCompany = async (company: string) => {
    setLoading(true);
    setTestResults([]);
    
    try {
      const response = await fetch('/api/agent/mcp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: `@${company} tell me about their funding and financials`
        })
      });
      
      const data = await response.json();
      setTestResults([{
        company,
        response: data.response,
        toolsUsed: data.toolsUsed,
        toolResults: data.toolResults
      }]);
    } catch (error) {
      console.error('Test failed:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">MCP Tools Test</h1>
      
      {/* Tool Discovery */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Available MCP Tools</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={discoverTools} className="mb-4">
            Discover Tools
          </Button>
          
          {tools.length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              {tools.map((tool, idx) => (
                <div key={idx} className="border p-3 rounded">
                  <h3 className="font-semibold">{tool.name}</h3>
                  <p className="text-sm text-gray-600">{tool.description}</p>
                  <div className="mt-2">
                    <Badge variant="outline">
                      {Object.keys(tool.inputSchema.properties).join(', ')}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Test Companies */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Test MCP Integration</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2 mb-4">
            <Button 
              onClick={() => testCompany('Stripe')}
              disabled={loading}
            >
              Test @Stripe
            </Button>
            <Button 
              onClick={() => testCompany('OpenAI')}
              disabled={loading}
            >
              Test @OpenAI
            </Button>
            <Button 
              onClick={() => testCompany('Anthropic')}
              disabled={loading}
            >
              Test @Anthropic
            </Button>
          </div>
          
          {loading && <p>Loading... (Tools are gathering data)</p>}
          
          {testResults.map((result, idx) => (
            <div key={idx} className="mt-4 space-y-4">
              <div>
                <h3 className="font-semibold mb-2">Tools Used:</h3>
                <div className="flex gap-2">
                  {result.toolsUsed?.map((tool: string) => (
                    <Badge key={tool} variant="secondary">
                      {tool}
                    </Badge>
                  ))}
                </div>
              </div>
              
              <div>
                <h3 className="font-semibold mb-2">Tool Results:</h3>
                {result.toolResults?.map((tr: any, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <span>{tr.tool}:</span>
                    {tr.success ? (
                      <Badge variant="default">✓ Success</Badge>
                    ) : (
                      <Badge variant="destructive">✗ Failed</Badge>
                    )}
                  </div>
                ))}
              </div>
              
              <div>
                <h3 className="font-semibold mb-2">Response:</h3>
                <div className="bg-gray-50 p-4 rounded whitespace-pre-wrap">
                  {result.response}
                </div>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}