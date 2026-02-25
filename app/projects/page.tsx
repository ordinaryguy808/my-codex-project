import Link from 'next/link';
import { prisma } from '@/lib/prisma';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { requireAuth } from '@/lib/authz';

export default async function ProjectsPage() {
  await requireAuth();
  const projects = await prisma.project.findMany({
    where: { status: { in: ['OPEN', 'IN_PROGRESS', 'SUBMITTED', 'REVIEWED', 'COMPLETED'] } },
    include: { businessOrg: true, school: true },
    orderBy: { createdAt: 'desc' }
  });

  return (
    <div>
      <h1 className="text-2xl font-semibold">Live Projects</h1>
      <p className="mb-4 mt-1 text-sm text-slate-600">Educational outcomes first: each project maps to evidence, reflection, and verified skill growth.</p>
      <div className="grid gap-4">
        {projects.map((project) => (
          <Card key={project.id}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                <Link href={`/projects/${project.id}`}>{project.title}</Link>
              </h2>
              <Badge>{project.status}</Badge>
            </div>
            <p className="mt-2 text-sm text-slate-700">{project.description}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {project.requiredSkills.map((skill) => <Badge key={skill}>{skill}</Badge>)}
            </div>
            <p className="mt-3 text-xs text-slate-500">{project.businessOrg.name} • {project.category} • {project.expectedHours} hrs</p>
          </Card>
        ))}
        {projects.length === 0 && <Card>No projects yet. Business partners can publish outcome-aligned opportunities from the business dashboard.</Card>}
      </div>
    </div>
  );
}
