import { DefaultSession } from 'next-auth';

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      organizationId?: string;
      organization?: {
        id: string;
        name: string;
        subscription_tier: string;
        subscription_status: string;
        seats_purchased: number;
        seats_used: number;
      };
      role?: string;
      freeGenerationUsed?: boolean;
    } & DefaultSession['user'];
  }

  interface User {
    id: string;
    email: string;
    name?: string;
    image?: string;
  }
}