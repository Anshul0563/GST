import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function RegisterPage() {
  return (
    <main className="grid min-h-screen place-items-center bg-[#F7FAFD] p-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>Create GST Bharat account</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div><Label>Full name</Label><Input placeholder="Aarav Sharma" /></div>
          <div><Label>Email</Label><Input type="email" placeholder="owner@example.com" /></div>
          <div><Label>Password</Label><Input type="password" /></div>
          <Button className="w-full">Create account</Button>
          <p className="text-center text-sm text-slate-500">Already registered? <Link className="font-medium text-primary" href="/login">Login</Link></p>
        </CardContent>
      </Card>
    </main>
  );
}

