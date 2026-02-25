import { redirect } from 'next/navigation';
import { auth } from '@/auth';

export async function requireAuth() {
  const session = await auth();
  if (!session?.user) redirect('/login');
  return session.user;
}

export async function requireRole(roles: string[]) {
  const user = await requireAuth();
  if (!roles.includes(user.role)) redirect('/projects');
  return user;
}
