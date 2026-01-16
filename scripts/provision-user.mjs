#!/usr/bin/env node
import 'dotenv/config';
import { createClient } from '@supabase/supabase-js';

const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: node scripts/provision-user.mjs <work-email> [key=value ...]');
  process.exit(1);
}

const [email, ...metadataArgs] = args;

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
if (!emailPattern.test(email)) {
  console.error(`Invalid email: ${email}`);
  process.exit(1);
}

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  console.error('Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY environment variables.');
  process.exit(1);
}

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: {
    autoRefreshToken: false,
    persistSession: false
  }
});

const metadata = metadataArgs.reduce((acc, pair) => {
  const [key, value] = pair.split('=');
  if (key && value) {
    acc[key] = value;
  }
  return acc;
}, {});

async function inviteUser() {
  try {
    const { data, error } = await supabase.auth.admin.inviteUserByEmail(email, {
      data: Object.keys(metadata).length ? metadata : undefined
    });

    if (error) {
      console.error('Failed to invite user:', error.message);
      process.exit(1);
    }

    console.log('Invitation email sent.');
    console.log(JSON.stringify(
      {
        id: data?.user?.id,
        email: data?.user?.email,
        metadata: data?.user?.user_metadata ?? null
      },
      null,
      2
    ));
  } catch (err) {
    console.error('Unexpected error:', err instanceof Error ? err.message : err);
    process.exit(1);
  }
}

inviteUser();
