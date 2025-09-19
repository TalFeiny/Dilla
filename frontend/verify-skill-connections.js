/**
 * Verify Skill Chain System Connections
 */

const fs = require('fs');
const path = require('path');

console.log('🔍 Verifying Skill Chain System Connections\n');
console.log('============================================\n');

// Read the orchestrator file
const orchestratorPath = path.join(__dirname, 'src/lib/agent-skills/skill-orchestrator.ts');
const orchestratorContent = fs.readFileSync(orchestratorPath, 'utf8');

// Read the dynamic chain file
const dynamicChainPath = path.join(__dirname, 'src/lib/agent-skills/dynamic-skill-chain.ts');
const dynamicChainContent = fs.readFileSync(dynamicChainPath, 'utf8');

// Read the unified brain file
const unifiedBrainPath = path.join(__dirname, 'src/app/api/agent/unified-brain/route.ts');
const unifiedBrainContent = fs.readFileSync(unifiedBrainPath, 'utf8');

// 1. Check skill implementations
console.log('📦 SKILL IMPLEMENTATIONS in SkillOrchestrator:');
const skillImplMatches = orchestratorContent.match(/skillImplementations\.set\('([^']+)'/g) || [];
const implementedSkills = skillImplMatches.map(m => m.match(/'([^']+)'/)[1]);
console.log(`   Found ${implementedSkills.length} skills implemented:`);
implementedSkills.forEach(skill => console.log(`   ✓ ${skill}`));

// 2. Check backend mappings
console.log('\n🔌 BACKEND ENDPOINTS:');
const backendMatches = orchestratorContent.match(/SKILL_TO_BACKEND\[['"]([^'"]+)['"]\]/g) || [];
const backendMapped = [...new Set(backendMatches.map(m => m.match(/\[['"]([^'"]+)['"]\]/)[1]))];
console.log(`   Found ${backendMapped.length} skills with backend endpoints:`);
backendMapped.forEach(skill => console.log(`   ✓ ${skill} → backend`));

// 3. Check MCP mappings
console.log('\n💰 MCP FINANCIAL TOOLS:');
const mcpMatches = orchestratorContent.match(/SKILL_TO_MCP_TOOL\[['"]([^'"]+)['"]\]/g) || [];
const mcpMapped = [...new Set(mcpMatches.map(m => m.match(/\[['"]([^'"]+)['"]\]/)[1]))];
console.log(`   Found ${mcpMapped.length} skills with MCP tools:`);
mcpMapped.forEach(skill => console.log(`   ✓ ${skill} → MCP`));

// 4. Check dynamic chain capabilities
console.log('\n🔗 DYNAMIC CHAIN CAPABILITIES:');
const capabilityMatches = dynamicChainContent.match(/'([^']+)':\s*{\s*skill:\s*'([^']+)'/g) || [];
const capabilities = capabilityMatches.map(m => {
  const match = m.match(/'([^']+)':\s*{\s*skill:\s*'([^']+)'/);
  return match ? match[1] : null;
}).filter(Boolean);
console.log(`   Found ${capabilities.length} skills in dynamic chain registry:`);
capabilities.forEach(skill => console.log(`   ✓ ${skill}`));

// 5. Check unified brain integration
console.log('\n🧠 UNIFIED BRAIN INTEGRATION:');
const hasDynamicChain = unifiedBrainContent.includes('dynamicChain.buildChain');
const hasSkillOrchestrator = unifiedBrainContent.includes('skillOrchestrator');
const hasExecuteChain = unifiedBrainContent.includes('dynamicChain.execute');

console.log(`   ✓ Dynamic chain imported: ${hasDynamicChain ? 'YES' : 'NO'}`);
console.log(`   ✓ Skill orchestrator imported: ${hasSkillOrchestrator ? 'YES' : 'NO'}`);
console.log(`   ✓ Chain execution wired: ${hasExecuteChain ? 'YES' : 'NO'}`);

// 6. Analysis skills check
console.log('\n📊 ANALYSIS SKILLS:');
const analysisSkills = [
  'financial-analyzer',
  'advanced-analytics',
  'unit-economics-analyzer',
  'funding-cadence-analyzer',
  'investment-analyzer'
];

analysisSkills.forEach(skill => {
  const hasImpl = implementedSkills.includes(skill);
  const hasBackend = backendMapped.includes(skill);
  const hasCap = capabilities.includes(skill);
  
  console.log(`   ${skill}:`);
  console.log(`     Implementation: ${hasImpl ? '✓' : '✗'}`);
  console.log(`     Backend mapped: ${hasBackend ? '✓' : '✗ (will use local)'}`);
  console.log(`     In dynamic chain: ${hasCap ? '✓' : '✗'}`);
});

// 7. Check for missing connections
console.log('\n⚠️  POTENTIAL ISSUES:');
const issues = [];

// Skills in dynamic chain but not implemented
capabilities.forEach(skill => {
  if (!implementedSkills.includes(skill)) {
    issues.push(`   - ${skill} in dynamic chain but NOT implemented`);
  }
});

// Skills implemented but not in dynamic chain
implementedSkills.forEach(skill => {
  if (!capabilities.includes(skill) && !skill.includes('-sourcer')) {
    issues.push(`   - ${skill} implemented but NOT in dynamic chain`);
  }
});

if (issues.length > 0) {
  issues.forEach(issue => console.log(issue));
} else {
  console.log('   ✓ All connections look good!');
}

// 8. Summary
console.log('\n📈 SUMMARY:');
console.log(`   Total skills implemented: ${implementedSkills.length}`);
console.log(`   Skills with backend: ${backendMapped.length}`);
console.log(`   Skills with MCP: ${mcpMapped.length}`);
console.log(`   Skills in dynamic chain: ${capabilities.length}`);
console.log(`   Analysis skills ready: ${analysisSkills.filter(s => implementedSkills.includes(s)).length}/${analysisSkills.length}`);

console.log('\n✅ Verification complete!\n');