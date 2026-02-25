'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState('');
  return (
    <div className="mx-auto mt-10 max-w-md">
      <Card>
        <h1 className="text-xl font-semibold">Create Student Account</h1>
        <p className="text-sm text-slate-600">Use a school domain email or invite token to join your school tenant.</p>
        <form
          className="mt-3 space-y-2"
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget as HTMLFormElement;
            const data = new FormData(form);
            const res = await fetch('/api/register', { method: 'POST', body: data });
            if (!res.ok) {
              const payload = await res.json();
              setError(payload.error || 'Registration failed');
              return;
            }
            router.push('/login');
          }}
        >
          <Input name="name" placeholder="Full name" required />
          <Input name="email" type="email" placeholder="you@school.edu" required />
          <Input name="password" type="password" placeholder="Password" required />
          <Input name="inviteToken" placeholder="Optional invite token" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button className="w-full" type="submit">Register</Button>
        </form>
      </Card>
    </div>
  );
}
