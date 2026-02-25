import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user || session.user.role !== 'BUSINESS_ADMIN') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

  const formData = await req.formData();
  const applicationId = String(formData.get('applicationId'));
  const decision = String(formData.get('decision'));

  await prisma.projectApplication.update({ where: { id: applicationId }, data: { status: decision } });
  if (decision === 'ACCEPTED') {
    await prisma.project.update({ where: { id: params.id }, data: { status: 'IN_PROGRESS' } });
  }

  return NextResponse.redirect(new URL(`/projects/${params.id}`, req.url));
}
