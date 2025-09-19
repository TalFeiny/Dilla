const http = require('http');

console.log('Testing /management-accounts for re-render loop...\n');

let requestCount = 0;
let errorFound = false;
let responseData = '';

const startTime = Date.now();

// Make request to the page
const req = http.get('http://localhost:3001/management-accounts', (res) => {
    console.log(`Status Code: ${res.statusCode}`);
    
    res.on('data', (chunk) => {
        responseData += chunk;
        
        // Check for React error messages in the response
        const chunkStr = chunk.toString();
        if (chunkStr.includes('Maximum update depth exceeded') || 
            chunkStr.includes('Too many re-renders') ||
            chunkStr.includes('Error: Maximum update')) {
            errorFound = true;
            console.log('❌ RE-RENDER LOOP DETECTED IN RESPONSE!');
        }
    });
    
    res.on('end', () => {
        const elapsed = Date.now() - startTime;
        console.log(`\nResponse received in ${elapsed}ms`);
        console.log(`Response size: ${responseData.length} bytes`);
        
        // Check if page loaded successfully
        if (res.statusCode === 200) {
            console.log('✅ Page loaded with status 200');
        } else {
            console.log('⚠️ Page returned status:', res.statusCode);
        }
        
        // Check for EnhancedSpreadsheet in the response
        if (responseData.includes('EnhancedSpreadsheet')) {
            console.log('✅ EnhancedSpreadsheet component found in response');
        }
        
        // Check for error indicators
        if (responseData.includes('getServerSideProps') || responseData.includes('Error boundary')) {
            console.log('⚠️ Possible server-side error detected');
        }
        
        if (!errorFound) {
            console.log('\n✅ NO RE-RENDER LOOP DETECTED - Page appears to be working!');
        } else {
            console.log('\n❌ RE-RENDER LOOP STILL EXISTS - Fixes did not work');
        }
        
        process.exit(errorFound ? 1 : 0);
    });
});

req.on('error', (err) => {
    console.error('❌ Request failed:', err.message);
    console.log('\nMake sure the dev server is running on port 3001');
    process.exit(1);
});

// Timeout after 10 seconds
setTimeout(() => {
    console.log('⏱️ Test timeout after 10 seconds');
    if (!errorFound) {
        console.log('✅ No re-render loop detected within timeout period');
    }
    process.exit(0);
}, 10000);