// Test the optimization changes
const testCompoundName = () => {
  // Test the camelCase splitting logic
  const testCases = [
    'artificialsocieties',
    'ArtificialSocieties', 
    'FinsterAI',
    'OpenAI',
    'ByteDance',
    'DeepMind'
  ];

  testCases.forEach(name => {
    const spacedName = name
      .replace(/([a-z])([A-Z])/g, '$1 $2')  
      .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2')
      .replace(/AI$/g, ' AI')
      .replace(/  +/g, ' ')
      .trim();
    
    console.log(`${name} → "${spacedName}"`);
  });
};

// Test @ extraction
const testExtraction = () => {
  const prompt = "Compare @artificialsocieties with @Ramp and @Deel";
  
  const parts = prompt.split('@').slice(1);
  const companies = [];
  
  for (const part of parts) {
    const company = part.split(/[\s,;.!?]/)[0].trim();
    if (company && company.length > 0) {
      companies.push(company);
    }
  }
  
  console.log('\nExtracted companies:', companies);
  return companies;
};

// Test Set deduplication
const testDeduplication = () => {
  const uniqueCompanies = new Set();
  
  // Add companies (some duplicates)
  uniqueCompanies.add('Ramp');
  uniqueCompanies.add('Deel');
  uniqueCompanies.add('Ramp'); // Duplicate
  uniqueCompanies.add('artificialsocieties');
  uniqueCompanies.add('Deel'); // Duplicate
  
  console.log('\nUnique companies:', Array.from(uniqueCompanies));
  console.log('Count:', uniqueCompanies.size);
};

console.log('=== TESTING OPTIMIZATIONS ===\n');
console.log('1. Compound Name Splitting:');
testCompoundName();

console.log('\n2. @ Extraction:');
testExtraction();

console.log('\n3. Deduplication:');
testDeduplication();