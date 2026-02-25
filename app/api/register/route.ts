import { NextResponse } from 'next/server';
import bcrypt from 'bcryptjs';
import { prisma } from '@/lib/prisma';

export async function POST(req: Request) {
  const form = await req.formData();
  const name = String(form.get('name'));
  const email = String(form.get('email'));
  const password = String(form.get('password'));
  const inviteToken = String(form.get('inviteToken') || '');

  if (await prisma.user.findUnique({ where: { email } })) {
    return NextResponse.json({ error: 'Email already used' }, { status: 400 });
  }

  let schoolId: string | null = null;
  if (inviteToken) {
    const invite = await prisma.schoolInvite.findUnique({ where: { token: inviteToken } });
    if (!invite) return NextResponse.json({ error: 'Invalid invite token' }, { status: 400 });
    schoolId = invite.schoolId;
    await prisma.schoolInvite.update({ where: { id: invite.id }, data: { usedAt: new Date() } });
  } else {
    const domain = email.split('@')[1];
    const school = await prisma.school.findUnique({ where: { domain } });
    if (!school) return NextResponse.json({ error: 'No school found for this email domain' }, { status: 400 });
    const activeCount = await prisma.user.count({ where: { schoolId: school.id, role: 'STUDENT' } });
    if (activeCount >= school.seatLimit) return NextResponse.json({ error: 'Seat limit reached for this school tier' }, { status: 400 });
    schoolId = school.id;
  }

  const passwordHash = await bcrypt.hash(password, 10);
  await prisma.user.create({ data: { name, email, passwordHash, role: 'STUDENT', schoolId } });

  return NextResponse.json({ ok: true });
}
