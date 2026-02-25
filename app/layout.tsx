import type { Metadata } from 'next';
import './globals.css';
import Link from 'next/link';
import { auth, signOut } from '@/auth';

export const metadata: Metadata = {
  title: 'Empower Your Dream | SkillBridge',
  description: 'Outcome-driven experiential learning and workforce readiness platform.'
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();

  return (
    <html lang="en">
      <body>
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link className="font-semibold" href="/projects">Empower Your Dream (SkillBridge)</Link>
            <nav className="flex items-center gap-4 text-sm">
              <Link href="/projects">Projects</Link>
              {session?.user?.role === 'SCHOOL_ADMIN' && <Link href="/school/admin">School Admin</Link>}
              {session?.user?.role === 'BUSINESS_ADMIN' && <Link href="/business/admin">Business Admin</Link>}
              {session?.user?.role === 'SUPER_ADMIN' && <Link href="/super-admin">Super Admin</Link>}
              {session?.user && <Link href={`/portfolio/${session.user.id}`}>My Portfolio</Link>}
              {!session?.user ? (
                <Link href="/login">Login</Link>
              ) : (
                <form
                  action={async () => {
                    'use server';
                    await signOut({ redirectTo: '/login' });
                  }}
                >
                  <button className="text-sm">Logout</button>
                </form>
              )}
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
