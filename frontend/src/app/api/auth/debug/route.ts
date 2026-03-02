import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function GET() {
  const cookieStore = await cookies();
  const allCookies = cookieStore.getAll();

  // Show all cookies (names only, not values for security)
  const cookieNames = allCookies.map(c => c.name);
  const supabaseCookies = allCookies.filter(c => c.name.includes('sb-') || c.name.includes('supabase'));

  // Try getUser with the cookies
  let userResult: any = null;
  let userError: any = null;

  try {
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() {
            return cookieStore.getAll();
          },
          setAll() {
            // read-only for debug
          },
        },
      }
    );

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
