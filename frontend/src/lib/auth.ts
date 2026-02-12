import { NextAuthOptions } from 'next-auth';
import GoogleProvider from 'next-auth/providers/google';
import CredentialsProvider from 'next-auth/providers/credentials';
import { createClient } from '@supabase/supabase-js';

// Create Supabase client with server-side key
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY || ''
);

export const authOptions: NextAuthOptions = {
  providers: [
    // Google OAuth provider (production)
    ...(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET ? [
      GoogleProvider({
        clientId: process.env.GOOGLE_CLIENT_ID,
        clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      })
    ] : []),
    
    // Credentials provider for development/testing
    CredentialsProvider({
      name: 'Development',
      credentials: {
        email: { label: "Email", type: "email", placeholder: "test@example.com" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // Development mode authentication
        if (process.env.NODE_ENV === 'development') {
          // Accept any email/password in dev mode
          if (credentials?.email) {
            return {
              id: '1',
              email: credentials.email,
              name: 'Dev User',
              image: null,
            };
          }
        }
        return null;
      }
    }),
  ],
  callbacks: {
    async signIn({ user, account, profile }) {
      if (account?.provider === 'google') {
        try {
          // Check if user exists in Supabase
          const { data: existingUser, error: fetchError } = await supabase
            .from('users')
            .select('*')
            .eq('email', user.email!)
            .single();

          if (fetchError && fetchError.code !== 'PGRST116') {
            console.error('Error fetching user:', fetchError);
            return false;
          }

          if (!existingUser) {
            // Check if this is the first free generation
            const { data: anonSession } = await supabase
              .from('anonymous_sessions')
              .select('*')
              .eq('session_id', profile?.sub)
              .single();

            // Create new user
            const { data: newUser, error: createError } = await supabase
              .from('users')
              .insert({
                email: user.email!,
                google_id: profile?.sub,
                name: user.name,
                avatar_url: user.image,
                free_generation_used: anonSession?.free_generation_used || false,
              })
              .select()
              .single();

            if (createError) {
              console.error('Error creating user:', createError);
              return false;
            }

            // Update anonymous session if exists
            if (anonSession) {
              await supabase
                .from('anonymous_sessions')
                .update({ converted_user_id: newUser.id })
                .eq('id', anonSession.id);
            }
          } else {
            // Update existing user
            await supabase
              .from('users')
              .update({
                google_id: profile?.sub,
                name: user.name,
                avatar_url: user.image,
                last_active: new Date().toISOString(),
              })
              .eq('id', existingUser.id);
          }

          return true;
        } catch (error) {
          console.error('Error in signIn callback:', error);
          return false;
        }
      }
      return true;
    },

    async session({ session, token }) {
      if (session.user?.email) {
        // Fetch user data from Supabase
        const { data: userData } = await supabase
          .from('users')
          .select('*, organizations(*)')
          .eq('email', session.user.email)
          .single();

        if (userData) {
          session.user = {
            ...session.user,
            id: userData.id,
            organizationId: userData.organization_id,
            organization: userData.organizations,
            role: userData.role,
            freeGenerationUsed: userData.free_generation_used,
          };
        }
      }
      return session;
    },

    async jwt({ token, user, account }) {
      if (account && user) {
        token.id = user.id;
        token.email = user.email;
      }
      return token;
    },
  },
  pages: {
    signIn: '/signin',
    error: '/auth/error',
  },
  secret: process.env.NEXTAUTH_SECRET || (process.env.NODE_ENV === 'development' ? 'dev-secret-change-in-production' : undefined),
};