import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { prisma } from '@/lib/prisma';

export async function GET() {
  const session = await auth();
  if (!session?.user || !['SCHOOL_ADMIN', 'SUPER_ADMIN'].includes(session.user.role)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  const schoolId = session.user.schoolId;
  const students = await prisma.user.findMany({
    where: { schoolId: schoolId ?? undefined, role: 'STUDENT' },
    include: {
      applications: true,
      submissions: true,
      artifacts: true
    }
  });

  const rows = ['student_name,student_email,applications,submissions,artifacts'];
  for (const s of students) {
    rows.push(`${s.name ?? ''},${s.email},${s.applications.length},${s.submissions.length},${s.artifacts.length}`);
  }

  return new NextResponse(rows.join('\n'), {
    headers: {
      'Content-Type': 'text/csv',
      'Content-Disposition': 'attachment; filename="school-outcomes.csv"'
    }
  });
}
