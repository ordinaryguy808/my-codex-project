import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user || session.user.role !== 'STUDENT') return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

  const formData = await req.formData();
  const artifactTitle = String(formData.get('artifactTitle'));
  const artifactLink = String(formData.get('artifactLink') || '');
  const reflection = String(formData.get('reflection'));

  await prisma.projectSubmission.create({
    data: {
      projectId: params.id,
      studentId: session.user.id,
      artifactTitle,
      artifactLink,
      reflection
    }
  });
  await prisma.project.update({ where: { id: params.id }, data: { status: 'SUBMITTED' } });

  return NextResponse.redirect(new URL(`/projects/${params.id}`, req.url));
}
