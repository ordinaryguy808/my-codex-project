import { notFound } from 'next/navigation';
import { prisma } from '@/lib/prisma';
import { requireAuth } from '@/lib/authz';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default async function ProjectDetailPage({ params }: { params: { id: string } }) {
  const user = await requireAuth();
  const project = await prisma.project.findUnique({
    where: { id: params.id },
    include: {
      businessOrg: true,
      applications: { include: { student: true } },
      submissions: { include: { student: true } },
      feedback: { include: { student: true } }
    }
  });

  if (!project) notFound();

  const isBusiness = user.role === 'BUSINESS_ADMIN' && user.businessOrgId === project.businessOrgId;
  const myApplication = project.applications.find((a) => a.studentId === user.id);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">{project.title}</h1>
          <Badge>{project.status}</Badge>
        </div>
        <p className="mt-2 text-sm">{project.description}</p>
        <p className="mt-3 text-sm"><strong>Deliverables:</strong> {project.deliverables}</p>
        <p className="mt-1 text-sm"><strong>Timeline:</strong> {project.timeline} • {project.expectedHours} hours</p>
        <div className="mt-2 flex flex-wrap gap-2">{project.requiredSkills.map((s) => <Badge key={s}>{s}</Badge>)}</div>

        {user.role === 'STUDENT' && !myApplication && (
          <form action={`/api/projects/${project.id}/apply`} method="post" className="mt-4">
            <textarea name="note" className="w-full rounded border p-2 text-sm" placeholder="Why are you a good fit?" />
            <Button className="mt-2" type="submit">Apply to Project</Button>
          </form>
        )}
        {myApplication && <p className="mt-3 text-sm">Application status: <strong>{myApplication.status}</strong></p>}
      </Card>

      {isBusiness && (
        <Card>
          <h2 className="font-semibold">Applications</h2>
          <div className="mt-2 space-y-2">
            {project.applications.map((app) => (
              <div key={app.id} className="rounded border p-3">
                <p className="text-sm font-medium">{app.student.name} ({app.student.email}) — {app.status}</p>
                <p className="text-sm text-slate-600">{app.note || 'No note'}</p>
                {app.status === 'PENDING' && (
                  <form action={`/api/projects/${project.id}/decision`} method="post" className="mt-2 flex gap-2">
                    <input type="hidden" name="applicationId" value={app.id} />
                    <Button name="decision" value="ACCEPTED">Accept</Button>
                    <Button className="bg-red-600 hover:bg-red-500" name="decision" value="REJECTED">Reject</Button>
                  </form>
                )}
              </div>
            ))}
            {project.applications.length === 0 && <p className="text-sm text-slate-500">No applications yet.</p>}
          </div>
        </Card>
      )}

      {user.role === 'STUDENT' && (
        <Card>
          <h2 className="font-semibold">Submit Work + Reflection</h2>
          <form action={`/api/projects/${project.id}/submission`} method="post" className="mt-2 space-y-2">
            <input className="w-full rounded border p-2 text-sm" name="artifactTitle" placeholder="Artifact title" required />
            <input className="w-full rounded border p-2 text-sm" name="artifactLink" placeholder="Artifact link (optional)" />
            <textarea className="w-full rounded border p-2 text-sm" name="reflection" placeholder="Reflection on learning outcomes" required />
            <Button type="submit">Submit</Button>
          </form>
        </Card>
      )}

      {isBusiness && (
        <Card>
          <h2 className="font-semibold">Provide Feedback</h2>
          <form action={`/api/projects/${project.id}/feedback`} method="post" className="mt-2 space-y-2">
            <input className="w-full rounded border p-2 text-sm" name="studentId" placeholder="Student ID" required />
            <input className="w-full rounded border p-2 text-sm" name="rating" type="number" min={1} max={5} placeholder="Rating 1-5" required />
            <textarea className="w-full rounded border p-2 text-sm" name="comments" placeholder="Outcome-focused feedback" required />
            <Button type="submit">Submit Feedback</Button>
          </form>
        </Card>
      )}

      {(user.role === 'SCHOOL_ADMIN' || user.role === 'SUPER_ADMIN') && (
        <Card>
          <h2 className="font-semibold">Verify Experience Outcome</h2>
          <form action={`/api/projects/${project.id}/verify`} method="post" className="mt-2 flex gap-2">
            <input className="w-full rounded border p-2 text-sm" name="studentId" placeholder="Student ID" required />
            <Button type="submit">Mark Verified</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
