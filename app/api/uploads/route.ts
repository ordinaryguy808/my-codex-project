import { NextResponse } from 'next/server';
import { auth } from '@/auth';
import { saveLocalFile } from '@/lib/storage';

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user) return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });

  const formData = await req.formData();
  const file = formData.get('file');
  if (!(file instanceof File)) return NextResponse.json({ error: 'Invalid file' }, { status: 400 });

  const storedPath = await saveLocalFile(file);
  return NextResponse.json({ storedPath });
}
