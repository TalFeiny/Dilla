'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { User } from '@supabase/supabase-js';
import { getSupabaseBrowser } from '@/lib/supabase/browser';

interface UserProfile {
  id: string;
  email: string;
  name?: string;
  avatar_url?: string;
  organization_id?: string;
  organization?: {
    id: string;
    name: string;
    subscription_tier: string;
    subscription_status: string;
    seats_purchased: number;
    seats_used: number;
  };
  role?: string;
}

interface AuthContext {
  user: User | null;
  profile: UserProfile | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContext>({
  user: null,
  profile: null,
  loading: true,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const supabase = getSupabaseBrowser();

    async function fetchProfile(email: string) {
      const { data } = await supabase
        .from('users')
        .select('*, organizations(*)')
        .eq('email', email)
        .single();

      if (data) {
        setProfile({
          id: data.id,
          email: data.email,
          name: data.name,
          avatar_url: data.avatar_url,
          organization_id: data.organization_id,
          organization: data.organizations,
          role: data.role,
        });
      }
      setLoading(false);
    }

    // Get initial session
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user);
      if (user) fetchProfile(user.email!);
      else setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (_event, session) => {
        const newUser = session?.user ?? null;
        setUser(newUser);
        if (newUser) {
          await fetchProfile(newUser.email!);
        } else {
          setProfile(null);
          setLoading(false);
        }
      }
    );

    return () => subscription.unsubscribe();
  }, []);

  async function handleSignOut() {
    const supabase = getSupabaseBrowser();
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
  }

  return (
    <AuthContext.Provider value={{ user, profile, loading, signOut: handleSignOut }}>
      {children}
    </AuthContext.Provider>
  );
}
