"use client";

import { useState } from "react";
import { CheckCircle2, FileSpreadsheet, UploadCloud } from "lucide-react";
import { platforms } from "@/lib/mock-data";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { uploadMarketplaceFiles } from "@/lib/api";

export function UploadZone({ token, profileId, onUploaded }: { token?: string; profileId?: number; onUploaded?: () => void }) {
  const [selected, setSelected] = useState<(typeof platforms)[number] | null>(null);
  const [status, setStatus] = useState("Validation pending");
  const [files, setFiles] = useState<FileList | null>(null);
  async function upload(platform: string) {
    if (!token || !profileId || !files?.length) {
      setStatus("Choose files after the demo workspace is ready");
      return;
    }
    setStatus("Uploading and parsing in background");
    await uploadMarketplaceFiles(token, profileId, platform, files);
    setStatus("Upload accepted. Refreshing dashboard shortly.");
    onUploaded?.();
  }
  return (
    <Card id="marketplace-upload">
      <CardHeader>
        <CardTitle>Marketplace Upload</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {platforms.map((platform) => (
            <Dialog key={platform.key}>
              <DialogTrigger asChild>
                <button onClick={() => setSelected(platform)} className="rounded-lg border border-slate-200 bg-white p-4 text-left transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-soft">
                  <div className={`mb-4 inline-flex rounded-lg px-3 py-1 text-sm font-semibold ${platform.color}`}>{platform.name}</div>
                  <p className="min-h-10 text-sm text-slate-500">{platform.files}</p>
                  <div className="mt-5 flex items-center gap-2 text-sm font-medium text-primary"><UploadCloud className="size-4" />Upload files</div>
                </button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{selected?.name || platform.name} import</DialogTitle>
                </DialogHeader>
                <div className="space-y-5 p-5">
                  <div className="rounded-lg border border-dashed border-primary/30 bg-[#F8FBFF] p-6">
                    <FileSpreadsheet className="mb-3 size-8 text-primary" />
                    <p className="font-medium text-slate-900">Required files</p>
                    <p className="mt-1 text-sm text-slate-500">{platform.files}</p>
                    <Input type="file" multiple className="mt-4" onChange={(event) => setFiles(event.target.files)} />
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    {["File format guide ready", status, "Parsed rows update after import"].map((text) => (
                      <div key={text} className="flex items-center gap-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-600"><CheckCircle2 className="size-4 text-success" />{text}</div>
                    ))}
                  </div>
                  <Button className="w-full" onClick={() => upload(platform.key)}>Start secure import</Button>
                </div>
              </DialogContent>
            </Dialog>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
