// Test streaming endpoint
async function testStreaming() {
  try {
    const response = await fetch('http://localhost:3000/api/agent/unified-brain-stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: 'Create a simple test',
        outputFormat: 'deck'
      })
    });

    if (!response.ok) {
      console.error('Response not OK:', response.status);
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    console.log('Starting to read stream...');
    let chunks = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log('Stream complete!');
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          chunks++;
          const data = line.slice(6);
          if (data === '[DONE]') {
            console.log('Received [DONE] signal');
          } else {
            try {
              const parsed = JSON.parse(data);
              console.log(`Chunk ${chunks}:`, parsed.type, parsed.message || '');
            } catch (e) {
              console.log(`Chunk ${chunks}: Could not parse:`, data.substring(0, 50));
            }
          }
        }
      }
    }
    
    console.log(`Total chunks received: ${chunks}`);
  } catch (error) {
    console.error('Error:', error);
  }
}

console.log('Testing streaming endpoint...');
console.log('Make sure the dev server is running on port 3000');
testStreaming();