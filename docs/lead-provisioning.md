# Lead Intake & User Provisioning

### Marketing Lead Flow
- The Talk to Sales form on the landing page (`frontend/src/app/page.tsx`) posts to `/api/leads`.
- The API handler (`frontend/src/app/api/leads/route.ts`) validates work-email domains and sends a notification email via Resend.
- Configure with environment variables:
  - `RESEND_API_KEY` – required. Your Resend API key.
  - `LEAD_NOTIFY_EMAIL` – the inbox that receives lead alerts (defaults to the founder email).
  - `LEAD_FROM_ADDRESS` – the "from" address on notification emails (defaults to Resend sandbox).
- No lead data is persisted to a database today; leads are delivered as notification emails only.

### Inviting Customers Without the Supabase Dashboard
- Use the helper script `scripts/provision-user.mjs` to send Supabase invite emails:

```bash
# Install dependencies if you have not already
cd frontend
npm install

# Back at the repo root, run:
node scripts/provision-user.mjs user@firm.com firm_type=mid
```

  - Load `NEXT_PUBLIC_SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in your environment (e.g. via `.env.local` or shell export) before running the script.
  - Optional `key=value` pairs are added to `user_metadata` when the user accepts the invite.
  - Supabase emails the recipient a password set link; once complete they can log in via `/login`.

### Day-to-Day Flow
1. You receive a Talk to Sales submission as an email to `LEAD_NOTIFY_EMAIL`.
2. When the customer is ready, run `node scripts/provision-user.mjs their@work.email` to send the invite.
3. The user accepts the Supabase invite, sets a password, and signs in from the landing page login button.
4. Newsletter opt-ins are handled by Beehiiv; export/import your existing list there so it remains the source of truth.
