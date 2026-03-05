import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { getSupabaseServer } from '@/lib/supabase/server';

export async function GET() {
  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();

  // Show all cookies (names only, not values for security)
  const cookieNames = allCookies.map(c => c.name);
  const supabaseCookies = allCookies.filter(c => c.name.includes('sb-') || c.name.includes('supabase'));

  // Try getUser with the canonical server client (same encode: 'tokens-only' config)
  let userResult: any = null;
  let userError: any = null;

  try {
    const supabase = await getSupabaseServer();
    const { data, error } = await supabase.auth.getUser();
    userResult = data?.user ? { id: data.user.id, email: data.user.email } : null;
    userError = error ? { message: error.message, status: error.status } : null;
  } catch (e: any) {
    userError = { message: e.message, stack: e.stack };
  }

  return NextResponse.json({
    totalCookies: allCookies.length,
    cookieNames,
    supabaseCookies: supabaseCookies.map(c => ({ name: c.name, length: c.value.length })),
    user: userResult,
    error: userError,
  });
}
