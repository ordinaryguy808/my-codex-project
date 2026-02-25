import crypto from 'crypto';
import { prisma } from '@/lib/prisma';
import { requireRole } from '@/lib/authz';
import { SchoolTier, Role } from '@prisma/client';
import { schoolTierDefaults } from '@/lib/subscription';
import { revalidatePath } from 'next/cache';
import { Card } from '@/components/ui/card';

async function createSchool(formData: FormData) {
  'use server';
  const name = String(formData.get('name'));
  const domain = String(formData.get('domain'));
  const adminEmail = String(formData.get('adminEmail'));
  const tier = (formData.get('tier') as SchoolTier) || SchoolTier.PILOT;
  const defaults = schoolTierDefaults(tier);

  const school = await prisma.school.create({
    data: { name, domain, tier, ...defaults }
  });

  const superAdmin = await prisma.user.findFirst({ where: { role: Role.SUPER_ADMIN } });
  if (superAdmin) {
    await prisma.schoolInvite.create({
      data: {
        email: adminEmail,
        schoolId: school.id,
        invitedById: superAdmin.id,
        role: Role.SCHOOL_ADMIN,
        token: crypto.randomUUID()
      }
    });
  }
  revalidatePath('/super-admin');
}

export default async function SuperAdminPage() {
  await requireRole(['SUPER_ADMIN']);
  const schools = await prisma.school.findMany({ include: { users: { where: { role: 'STUDENT' } } } });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Super Admin • School Onboarding</h1>
      <Card>
        <form action={createSchool} className="grid gap-2">
          <input className="rounded border p-2 text-sm" name="name" placeholder="School name" required />
          <input className="rounded border p-2 text-sm" name="domain" placeholder="school.edu" required />
          <input className="rounded border p-2 text-sm" name="adminEmail" type="email" placeholder="Founding admin email" required />
          <select className="rounded border p-2 text-sm" name="tier" defaultValue="PILOT">
            <option value="PILOT">Pilot</option>
            <option value="CAMPUS">Campus</option>
            <option value="ENTERPRISE">Enterprise</option>
          </select>
          <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Create School + Admin Invite</button>
        </form>
      </Card>
      <Card>
        <h2 className="font-semibold">Current Schools</h2>
        <div className="mt-2 space-y-1 text-sm">
          {schools.map((s) => <p key={s.id}>{s.name} ({s.domain}) • {s.tier} • seats {s.users.length}/{s.seatLimit}</p>)}
        </div>
      </Card>
    </div>
  );
}
