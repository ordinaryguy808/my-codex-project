import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user || session.user.role !== 'STUDENT') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

  const formData = await req.formData();
  const note = String(formData.get('note') || '');

  await prisma.projectApplication.upsert({
    where: { projectId_studentId: { projectId: params.id, studentId: session.user.id } },
    update: { note },
    create: { projectId: params.id, studentId: session.user.id, note }
  });

  return NextResponse.redirect(new URL(`/projects/${params.id}`, req.url));
}
