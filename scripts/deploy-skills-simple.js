const fs = require('fs');
const path = require('path');

// Manually load env variables
const envPath = path.join(__dirname, '..', '.env.local');
const envContent = fs.readFileSync(envPath, 'utf8');
const env = {};
envContent.split('\n').forEach(line => {
  const [key, value] = line.split('=');
  if (key && value) {
    env[key.trim()] = value.trim();
  }
});

async function deploySkills() {
  const { createClient } = await import('@supabase/supabase-js');
  
  const supabaseUrl = env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = env.SUPABASE_SERVICE_ROLE_KEY;
  
  if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase credentials');
    process.exit(1);
  }
  
  const supabase = createClient(supabaseUrl, supabaseKey);
  
  console.log('🚀 Deploying skills database to Supabase...');
  console.log(`📍 URL: ${supabaseUrl}`);
  
  // Read SQL file
  const sqlPath = path.join(__dirname, 'comprehensive_skills_database.sql');
  const fullSql = fs.readFileSync(sqlPath, 'utf8');
  
  // For Supabase, we need to execute the SQL through the SQL editor API
  // or split it into individual statements
  
  // Split into major sections
  const sections = [
    // Drop and create table
    fullSql.match(/DROP TABLE[\s\S]*?CREATE INDEX idx_skills_complexity[^;]*;/)[0],
    // Create search function
    fullSql.match(/CREATE OR REPLACE FUNCTION search_skills[\s\S]*?\$\$;/)[0],
    // Insert statements - need to handle these individually
    ...fullSql.matchAll(/INSERT INTO modeling_skills[\s\S]*?(?=INSERT INTO|UPDATE|CREATE OR REPLACE|$)/g)
  ].filter(Boolean);
  
  console.log(`📝 Found ${sections.length} sections to deploy`);
  
  for (let i = 0; i < sections.length; i++) {
    const section = typeof sections[i] === 'string' ? sections[i] : sections[i][0];
    const preview = section.substring(0, 60).replace(/\n/g, ' ');
    console.log(`\n[${i + 1}/${sections.length}] ${preview}...`);
    
    try {
      // Try to execute via raw SQL
      const { data, error } = await supabase
        .from('_sql')
        .select()
        .sql(section);
      
      if (error) {
        console.log(`⚠️  Section failed, will try manual approach`);
      } else {
        console.log(`✅ Success`);
      }
    } catch (err) {
      console.log(`⚠️  ${err.message}`);
    }
  }
  
  // Verify deployment
  console.log('\n🧪 Verifying deployment...');
  const { data: skills, error } = await supabase
    .from('modeling_skills')
    .select('count')
    .single();
  
  if (skills) {
    console.log(`✅ Skills table exists with ${skills.count} records`);
  } else {
    console.log('⚠️  Could not verify - you may need to run the SQL manually in Supabase dashboard');
    console.log('📋 SQL file location: scripts/comprehensive_skills_database.sql');
  }
}

deploySkills().catch(console.error);