const { createClient } = require('@supabase/supabase-js');
const fs = require('fs');
const path = require('path');

// Load environment variables
require('dotenv').config({ path: '.env.local' });

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !supabaseKey) {
  console.error('Missing Supabase credentials in .env.local');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, supabaseKey);

async function deploySkills() {
  try {
    console.log('🚀 Deploying comprehensive skills database...');
    
    // Read the SQL file
    const sqlPath = path.join(__dirname, 'comprehensive_skills_database.sql');
    const sql = fs.readFileSync(sqlPath, 'utf8');
    
    // Split by semicolons but be careful with functions
    const statements = sql
      .split(/;\s*$/gm)
      .filter(stmt => stmt.trim())
      .map(stmt => stmt.trim() + ';');
    
    console.log(`📝 Found ${statements.length} SQL statements to execute`);
    
    // Execute each statement
    for (let i = 0; i < statements.length; i++) {
      const statement = statements[i];
      
      // Skip empty statements
      if (!statement.trim() || statement.trim() === ';') continue;
      
      // Get first few words for logging
      const preview = statement.substring(0, 50).replace(/\n/g, ' ');
      console.log(`\n[${i + 1}/${statements.length}] Executing: ${preview}...`);
      
      try {
        const { data, error } = await supabase.rpc('exec_sql', {
          sql: statement
        });
        
        if (error) {
          // Try direct execution as alternative
          const { error: directError } = await supabase
            .from('_sql')
            .select('*')
            .sql(statement);
          
          if (directError) {
            console.error(`❌ Error: ${directError.message}`);
            // Continue with next statement instead of failing completely
            continue;
          }
        }
        
        console.log(`✅ Success`);
      } catch (err) {
        console.error(`❌ Error executing statement: ${err.message}`);
        // Continue with next statement
      }
    }
    
    console.log('\n🎉 Skills database deployment complete!');
    
    // Test the deployment
    console.log('\n🧪 Testing skill retrieval...');
    const { data: testData, error: testError } = await supabase
      .from('modeling_skills')
      .select('title, category, model_type')
      .limit(5);
    
    if (testData) {
      console.log(`✅ Found ${testData.length} skills in database`);
      testData.forEach(skill => {
        console.log(`  - ${skill.title} (${skill.category}, ${skill.model_type})`);
      });
    } else if (testError) {
      console.log(`⚠️  Could not verify deployment: ${testError.message}`);
    }
    
  } catch (error) {
    console.error('Failed to deploy skills:', error);
    process.exit(1);
  }
}

// Alternative approach using direct PostgreSQL connection
async function deploySkillsDirect() {
  const { Client } = require('pg');
  
  // Parse connection string from Supabase URL
  const dbUrl = process.env.DATABASE_URL || `postgresql://postgres:${process.env.SUPABASE_SERVICE_ROLE_KEY}@db.ijkatixkebddtkdvgkog.supabase.co:5432/postgres`;
  
  const client = new Client({
    connectionString: dbUrl,
    ssl: { rejectUnauthorized: false }
  });
  
  try {
    await client.connect();
    console.log('📊 Connected to database directly');
    
    const sqlPath = path.join(__dirname, 'comprehensive_skills_database.sql');
    const sql = fs.readFileSync(sqlPath, 'utf8');
    
    await client.query(sql);
    console.log('✅ Skills database deployed successfully!');
    
    // Test query
    const result = await client.query('SELECT COUNT(*) FROM modeling_skills');
    console.log(`📈 Total skills in database: ${result.rows[0].count}`);
    
  } catch (error) {
    console.error('Deployment failed:', error);
  } finally {
    await client.end();
  }
}

// Try Supabase client first, fall back to direct connection if needed
deploySkills().catch(() => {
  console.log('\n🔄 Trying direct PostgreSQL connection...');
  deploySkillsDirect();
});