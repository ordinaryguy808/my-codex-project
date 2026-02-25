import Link from 'next/link';
import { notFound } from 'next/navigation';
import { prisma } from '@/lib/prisma';
import { requireAuth } from '@/lib/authz';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

export default async function PortfolioPage({ params }: { params: { studentId: string } }) {
  const user = await requireAuth();
  if (user.role === 'STUDENT' && user.id !== params.studentId) notFound();

  const student = await prisma.user.findUnique({
    where: { id: params.studentId },
    include: { artifacts: { include: { project: true }, orderBy: { createdAt: 'desc' } }, school: true }
  });

  if (!student) notFound();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{student.name}&apos;s Portfolio</h1>
        <p className="text-sm text-slate-600">Portable evidence of learning outcomes. Access remains even after coursework ends.</p>
        <Link className="text-sm text-blue-600 underline" href={`/api/portfolio/${student.id}/record`}>Download Experience Record (PDF)</Link>
      </div>
      {student.artifacts.map((artifact) => (
        <Card key={artifact.id}>
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">{artifact.title}</h2>
            {artifact.verified && <Badge>Verified Experience</Badge>}
          </div>
          <p className="text-sm text-slate-600">Project: {artifact.project.title}</p>
          <p className="mt-2 text-sm">{artifact.description}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {artifact.skills.map((skill) => <Badge key={skill}>{skill}</Badge>)}
          </div>
          {artifact.artifactLink && <a className="mt-2 block text-sm text-blue-600 underline" href={artifact.artifactLink}>View Artifact</a>}
        </Card>
      ))}
      {student.artifacts.length === 0 && <Card>No artifacts yet. Complete projects and submit reflection to generate verified portfolio evidence.</Card>}
    </div>
  );
}
