import { prisma } from '@/lib/prisma';
import { requireRole } from '@/lib/authz';
import { Card } from '@/components/ui/card';
import { revalidatePath } from 'next/cache';
import { BusinessTier } from '@prisma/client';
import { businessTierDefaults } from '@/lib/subscription';

async function createProject(formData: FormData) {
  'use server';
  const businessOrgId = String(formData.get('businessOrgId'));
  const title = String(formData.get('title'));
  const description = String(formData.get('description'));
  const deliverables = String(formData.get('deliverables'));
  const expectedHours = Number(formData.get('expectedHours'));
  const timeline = String(formData.get('timeline'));
  const category = String(formData.get('category'));
  const requiredSkills = String(formData.get('requiredSkills')).split(',').map((s) => s.trim()).filter(Boolean);

  const org = await prisma.businessOrg.findUnique({ where: { id: businessOrgId }, include: { projects: true } });
  if (!org) return;

  const monthStart = new Date();
  monthStart.setDate(1);
  monthStart.setHours(0, 0, 0, 0);
  const postsThisMonth = org.projects.filter((p) => p.createdAt >= monthStart).length;
  if (postsThisMonth >= org.monthlyPostingLimit) {
    throw new Error('Monthly posting limit reached for this subscription tier.');
  }

  await prisma.project.create({
    data: { title, description, deliverables, expectedHours, timeline, category, requiredSkills, businessOrgId, status: 'OPEN' }
  });
  revalidatePath('/business/admin');
}

async function updateTier(formData: FormData) {
  'use server';
  const businessOrgId = String(formData.get('businessOrgId'));
  const tier = formData.get('tier') as BusinessTier;
  const defaults = businessTierDefaults(tier);
  await prisma.businessOrg.update({ where: { id: businessOrgId }, data: { tier, ...defaults } });
  revalidatePath('/business/admin');
}

export default async function BusinessAdminPage() {
  const user = await requireRole(['BUSINESS_ADMIN', 'SUPER_ADMIN']);
  const org = await prisma.businessOrg.findUnique({ where: { id: user.businessOrgId ?? '' }, include: { projects: true } });
  if (!org) return <p>Business org not found.</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Business Admin Dashboard</h1>
      <p className="text-sm text-slate-600">Create educational projects that produce outcomes: skills, reflections, and verified records.</p>
      <Card>
        <p><strong>{org.name}</strong> • Tier: {org.tier}</p>
        <p className="text-sm text-slate-600">Monthly posting limit: {org.monthlyPostingLimit} • Priority access: {org.priorityAccess ? 'Yes' : 'No'}</p>
        <form action={updateTier} className="mt-2 flex gap-2">
          <input type="hidden" name="businessOrgId" value={org.id} />
          <select name="tier" defaultValue={org.tier} className="rounded border p-2 text-sm">
            <option value="STARTER">Starter</option>
            <option value="GROWTH">Growth</option>
            <option value="PARTNER">Partner</option>
          </select>
          <button className="rounded bg-slate-900 px-3 py-2 text-sm text-white">Change Tier</button>
        </form>
      </Card>
      <Card>
        <h2 className="font-semibold">Create Project</h2>
        <form action={createProject} className="mt-2 grid gap-2">
          <input type="hidden" name="businessOrgId" value={org.id} />
          <input className="rounded border p-2 text-sm" name="title" placeholder="Project title" required />
          <textarea className="rounded border p-2 text-sm" name="description" placeholder="Description" required />
          <textarea className="rounded border p-2 text-sm" name="deliverables" placeholder="Deliverables" required />
          <input className="rounded border p-2 text-sm" name="requiredSkills" placeholder="skills comma separated" required />
          <input className="rounded border p-2 text-sm" name="expectedHours" type="number" placeholder="Expected hours" required />
          <input className="rounded border p-2 text-sm" name="timeline" placeholder="Timeline" required />
          <input className="rounded border p-2 text-sm" name="category" placeholder="Category" required />
          <button className="rounded bg-slate-900 px-4 py-2 text-sm text-white">Publish OPEN Project</button>
        </form>
      </Card>
    </div>
  );
}
