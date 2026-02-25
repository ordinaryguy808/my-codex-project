import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request, { params }: { params: { id: string } }) {
  const session = await auth();
  if (!session?.user || !['SCHOOL_ADMIN', 'SUPER_ADMIN'].includes(session.user.role)) return NextResponse.json({ error: 'Forbidden' }, { status: 403 });

  const formData = await req.formData();
  const studentId = String(formData.get('studentId'));

  const project = await prisma.project.findUnique({ where: { id: params.id } });
  if (!project) return NextResponse.json({ error: 'Project not found' }, { status: 404 });
  const latestSubmission = await prisma.projectSubmission.findFirst({ where: { projectId: params.id, studentId }, orderBy: { createdAt: 'desc' } });
  if (!latestSubmission) return NextResponse.json({ error: 'No submission found' }, { status: 400 });

  await prisma.projectFeedback.upsert({
    where: { projectId_studentId: { projectId: params.id, studentId } },
    update: { verified: true },
    create: { projectId: params.id, studentId, rating: 5, comments: 'Verified by school admin.', verified: true }
  });

  await prisma.portfolioArtifact.upsert({
    where: { studentId_projectId: { studentId, projectId: params.id } },
    update: { verified: true },
    create: {
      studentId,
      projectId: params.id,
      title: latestSubmission.artifactTitle,
      description: latestSubmission.reflection,
      skills: project.requiredSkills,
      verified: true,
      artifactLink: latestSubmission.artifactLink,
      artifactFile: latestSubmission.artifactFile
    }
  });

  await prisma.project.update({ where: { id: params.id }, data: { status: 'COMPLETED' } });
  return NextResponse.redirect(new URL(`/projects/${params.id}`, req.url));
}
