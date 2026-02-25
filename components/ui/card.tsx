import { cn } from '@/lib/utils';

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn('rounded-lg border border-slate-200 bg-white p-5 shadow-sm', className)}>{children}</div>;
}
