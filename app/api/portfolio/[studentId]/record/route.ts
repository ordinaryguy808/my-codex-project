import { NextResponse } from 'next/server';
import { PDFDocument, StandardFonts, rgb } from 'pdf-lib';
import { prisma } from '@/lib/prisma';
import { auth } from '@/auth';

export async function GET(_: Request, { params }: { params: { studentId: string } }) {
  const session = await auth();
  if (!session?.user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const student = await prisma.user.findUnique({
    where: { id: params.studentId },
    include: { artifacts: { include: { project: true } } }
  });
  if (!student) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const pdfDoc = await PDFDocument.create();
  const page = pdfDoc.addPage([612, 792]);
  const font = await pdfDoc.embedFont(StandardFonts.Helvetica);

  page.drawText('SkillBridge Experience Record', { x: 50, y: 740, size: 20, font, color: rgb(0.1, 0.1, 0.1) });
  page.drawText(`Student: ${student.name} (${student.email})`, { x: 50, y: 710, size: 12, font });

  let y = 680;
  student.artifacts.forEach((artifact) => {
    page.drawText(`• ${artifact.title} (${artifact.project.title})`, { x: 50, y, size: 11, font });
    y -= 18;
    page.drawText(`  Skills: ${artifact.skills.join(', ')} | Verified: ${artifact.verified ? 'Yes' : 'No'}`, { x: 60, y, size: 10, font });
    y -= 20;
  });

  const bytes = await pdfDoc.save();
  return new NextResponse(Buffer.from(bytes), {
    headers: {
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="experience-record-${student.id}.pdf"`
    }
  });
}
