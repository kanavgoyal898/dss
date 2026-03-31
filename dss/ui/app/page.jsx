"use client";

/**
 * DSS root landing page — mode selection.
 * Purpose: Allow the user to navigate to the Admin or Node dashboard.
 * Dependencies: React, Next.js App Router, shadcn/ui
 */

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6">
      <div className="mb-10 text-center">
        <h1 className="text-5xl font-bold tracking-tight">DSS</h1>
        <p className="text-muted-foreground mt-3 text-base">Distributed Storage System</p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 w-full max-w-xl">
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle>DSS Admin</CardTitle>
            <CardDescription>
              Manage the storage coordinator — monitor nodes, files, and network policy.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/admin">
              <Button className="w-full">Open Admin Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader>
            <CardTitle>DSS Node</CardTitle>
            <CardDescription>
              Join a storage network, upload files, and access your data from anywhere.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/node">
              <Button variant="outline" className="w-full">Open Node Dashboard</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
