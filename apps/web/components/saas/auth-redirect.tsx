"use client";

import { useEffect } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { getStoredAuthToken } from "@/lib/auth";

export function AuthRedirect({ to = "/dashboard" }: { to?: Route }) {
  const router = useRouter();

  useEffect(() => {
    if (getStoredAuthToken()) {
      router.replace(to);
    }
  }, [router, to]);

  return null;
}
