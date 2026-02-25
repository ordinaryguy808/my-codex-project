import crypto from 'crypto';
import { prisma } from '@/lib/prisma';
import { requireRole } from '@/lib/authz';
import { Card } from '@/components/ui/card';
import { Role, SchoolTier } from '@prisma/client';
import { schoolTierDefaults } from '@/lib/subscription';
import { revalidatePath } from 'next/cache';

async function updateTier(formData: FormData) {
  'use server';
  const schoolId = String(formData.get('schoolId'));
  const tier = formData.get('tier') as SchoolTier;
  const defaults = schoolTierDefaults(tier);
  await prisma.school.update({ where: { id: schoolId }, data: { tier, ...defaults } });
  revalidatePath('/school/admin');
}

async function inviteAdmin(formData: FormData) {
  'use server';
  const schoolId = String(formData.get('schoolId'));
  const invitedById = String(formData.get('invitedById'));
  const email = String(formData.get('email'));
  const token = crypto.randomUUID();
  await prisma.schoolInvite.create({
    data: { schoolId, invitedById, email, role: Role.SCHOOL_ADMIN, token }
  });
  revalidatePath('/school/admin');
}

export default async function SchoolAdminPage() {
  const user = await requireRole(['SCHOOL_ADMIN', 'SUPER_ADMIN']);
  const school = await prisma.school.findUnique({
    where: { id: user.schoolId ?? '' },
    include: {
      users: { where: { role: 'STUDENT' } },
      projects: true,
      invites: { orderBy: { createdAt: 'desc' }, take: 5 },
      approvedBusinesses: { include: { businessOrg: true } }
    }
  });
  if (!school) return <p>School not found.</p>;

  const completed = await prisma.project.count({ where: { schoolId: school.id, status: 'COMPLETED' } });
  const artifacts = await prisma.portfolioArtifact.count({ where: { student: { schoolId: school.id } } });
  const avgRating = await prisma.projectFeedback.aggregate({ _avg: { rating: true }, where: { student: { schoolId: school.id } } });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">School Admin Dashboard</h1>
      <p className="text-sm text-slate-600">Outcome vs transaction: monitor measurable growth, verified experience, and curriculum impact.</p>
      <div className="grid gap-4 md:grid-cols-4">
        <Card>Active students: <strong>{school.users.length}</strong> / {school.seatLimit}</Card>
        <Card>Projects completed: <strong>{completed}</strong></Card>
        <Card>Portfolio artifacts: <strong>{artifacts}</strong></Card>
        <Card>Business satisfaction: <strong>{(avgRating._avg.rating ?? 0).toFixed(1)}</strong> / 5</Card>
      </div>
      <Card>
        <h2 className="font-semibold">School Profile</h2>
        <p className="text-sm text-slate-600">Domain: {school.domain}</p>
      </Card>
      <Card>
        <h2 className="font-semibold">Subscription Tier</h2>
        <form action={updateTier} className="mt-2 flex items-center gap-2">
          <input type="hidden" name="schoolId" value={school.id} />
          <select name="tier" defaultValue={school.tier} className="rounded border p-2 text-sm">
            <option value="PILOT">Pilot</option>
            <option value="CAMPUS">Campus</option>
            <option value="ENTERPRISE">Enterprise</option>
          </select>
          <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Update</button>
        </form>
      </Card>
      <Card>
        <h2 className="font-semibold">Invite Additional School Admin</h2>
        <form action={inviteAdmin} className="mt-2 flex gap-2">
          <input type="hidden" name="schoolId" value={school.id} />
          <input type="hidden" name="invitedById" value={user.id} />
          <input className="w-full rounded border p-2 text-sm" name="email" type="email" placeholder="admin email" required />
          <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Create Invite</button>
        </form>
        <div className="mt-3 space-y-1 text-xs text-slate-600">
          {school.invites.map((invite) => <p key={invite.id}>{invite.email} • token: {invite.token}</p>)}
        </div>
      </Card>
      <Card>
        <h2 className="font-semibold">Reporting</h2>
        <a className="text-sm text-blue-600 underline" href="/api/schools/export">Export CSV</a>
      </Card>
    </div>
  );
}
