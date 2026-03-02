import { NextResponse } from 'next/server';
import { getSupabaseServer, getSupabaseServiceRole } from '@/lib/supabase/server';

/**
 * Supabase redirects here after any auth flow (email, invite link, OAuth, etc).
 * Exchanges the auth code for a session, then ensures a public.users row exists
 * so org-scoped RLS works.
 */
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/';

  if (code) {
    const supabase = await getSupabaseServer();
    const { error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error) {
      const { data: { user } } = await supabase.auth.getUser();
      if (user) {
        // Use service role to bypass RLS for user/org provisioning
        const admin = getSupabaseServiceRole();

        const { data: existingUser } = await admin
          .from('users')
          .select('id')
          .eq('id', user.id)
          .single();

        if (!existingUser) {
          // Derive org from email domain
          const domain = user.email!.split('@')[1];
          const orgName = domain;

          // Find or create the organization
          let orgId: string;
          const { data: existingOrg } = await admin
            .from('organizations')
            .select('id')
            .eq('name', orgName)
            .single();

          if (existingOrg) {
            orgId = existingOrg.id;
          } else {
            const { data: newOrg } = await admin
              .from('organizations')
              .insert({ name: orgName })
              .select('id')
              .single();
            orgId = newOrg!.id;
          }

          await admin.from('users').insert({
            id: user.id, // = auth.uid()
            email: user.email!,
            name: user.user_metadata.full_name || user.user_metadata.name || null,
            avatar_url: user.user_metadata.avatar_url || null,
            organization_id: orgId,
          });
        }
      }

      return NextResponse.redirect(`${origin}${next}`);
    }
  }

  // Auth error — redirect to error page
  return NextResponse.redirect(`${origin}/auth/error`);
}
