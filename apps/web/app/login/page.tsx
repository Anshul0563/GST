import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#F7FAFD] p-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>Login to GST Bharat</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div><Label>Email</Label><Input type="email" placeholder="owner@example.com" /></div>
          <div><Label>Password</Label><Input type="password" /></div>
          <Button className="w-full">Login</Button>
          <p className="text-center text-sm text-slate-500">New seller? <Link className="font-medium text-primary" href="/register">Create account</Link></p>
        </CardContent>
      </Card>
    </main>
  );
}

