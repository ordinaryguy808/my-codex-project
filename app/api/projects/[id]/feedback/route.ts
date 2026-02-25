import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user || session.user.role !== 'BUSINESS_ADMIN') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

  const formData = await req.formData();
  const studentId = String(formData.get('studentId'));
  const rating = Number(formData.get('rating'));
  const comments = String(formData.get('comments'));

  await prisma.projectFeedback.upsert({
    where: { projectId_studentId: { projectId: params.id, studentId } },
    update: { rating, comments },
    create: { projectId: params.id, studentId, rating, comments }
  });

  await prisma.project.update({ where: { id: params.id }, data: { status: 'REVIEWED' } });
  return NextResponse.redirect(new URL(`/projects/${params.id}`, req.url));
}
