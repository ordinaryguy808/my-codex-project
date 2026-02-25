import { mkdir, writeFile } from 'fs/promises';
import path from 'path';

export async function saveLocalFile(file: File) {
  const bytes = Buffer.from(await file.arrayBuffer());
  const uploadDir = path.join(process.cwd(), 'uploads');
  await mkdir(uploadDir, { recursive: true });
  const fileName = `${Date.now()}-${file.name.replace(/\s+/g, '-')}`;
  const fullPath = path.join(uploadDir, fileName);
  await writeFile(fullPath, bytes);
  return `/uploads/${fileName}`;
}
