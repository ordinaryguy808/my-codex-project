# Empower Your Dream (SkillBridge) MVP

Production-ready MVP for an experiential learning + workforce readiness platform where schools are the primary payer and students never pay.

## Outcome vs Transaction framing
SkillBridge prioritizes educational outcomes over transactional gig activity:
- Verified experience records
- Portfolio artifacts for every completed project
- Reflection and measurable skill progression
- Curriculum-aligned school reporting

## Tech stack
- Next.js 14 (App Router) + TypeScript + Tailwind
- Prisma + PostgreSQL
- NextAuth (credentials)
- pdf-lib for downloadable experience record PDFs
- Shadcn-style UI primitives (`components/ui`)

## Core MVP capabilities
- Multi-tenant schools with tiering: PILOT / CAMPUS / ENTERPRISE
- Student seat caps + active counts
- School admin dashboard with outcomes + CSV export
- Business tiering: STARTER / GROWTH / PARTNER with posting limits
- Project lifecycle: DRAFT → OPEN → IN_PROGRESS → SUBMITTED → REVIEWED → COMPLETED
- Student applications, submissions, and reflection
- Business feedback/rating and school verification
- Portfolio artifacts and downloadable experience record PDF

## Routes
- `/login`
- `/school/admin`
- `/business/admin`
- `/projects`
- `/projects/[id]`
- `/portfolio/[studentId]`

## Local setup
1. Install dependencies
   ```bash
   npm install
   ```
2. Start Postgres
   ```bash
   docker compose up -d
   ```
3. Configure env
   ```bash
   cp .env.example .env
   ```
4. Run migrations + Prisma client generation
   ```bash
   npx prisma migrate dev --name init
   npx prisma generate
   ```
5. Seed demo data
   ```bash
   npm run prisma:seed
   ```
6. Start app
   ```bash
   npm run dev
   ```

## Demo users (after seed)
Password for all users: `Password123!`
- superadmin@skillbridge.app
- admin@riverside.edu (school admin)
- owner@growthops.example.com (business admin)
- student1@riverside.edu ... student5@riverside.edu

## Env vars
- `DATABASE_URL`: PostgreSQL connection string
- `NEXTAUTH_SECRET`: required for auth signing
- `NEXTAUTH_URL`: app URL in current environment

## Security / authorization
- Server-side role checks for school and business dashboards
- Server route role checks for project workflow actions
- Students restricted to their own portfolio view

## Notes
- File storage uses local filesystem abstraction (`lib/storage.ts`) and can be swapped for S3.
- Google OAuth is optional and not enabled in this MVP build.
