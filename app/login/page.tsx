'use client';

import { useState } from 'react';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('admin@riverside.edu');
  const [password, setPassword] = useState('Password123!');
  const [error, setError] = useState('');

  return (
    <div className="mx-auto mt-10 max-w-md">
      <Card>
        <h1 className="text-xl font-semibold">Sign in to SkillBridge</h1>
        <p className="mt-2 text-sm text-slate-600">Outcome over transaction: build verified experience, not gig work.</p>
        <form
          className="mt-4 space-y-3"
          onSubmit={async (e) => {
            e.preventDefault();
            const result = await signIn('credentials', { email, password, redirect: false });
            if (result?.error) return setError('Invalid credentials');
            router.push('/projects');
          }}
        >
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" />
          {error && <p className="text-sm text-red-600">{error}</p>}
          <Button type="submit" className="w-full">Login</Button>
        </form>
        <p className="mt-3 text-sm">No account? <a className="text-blue-600 underline" href="/register">Register as student</a></p>
      </Card>
    </div>
  );
}
