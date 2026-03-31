"use client";

/**
 * DSS Node Dashboard.
 * Purpose: Full peer node management — coordinator connection with URL persistence,
 *   drag-and-drop upload with real-time SSE progress, file table with one-click download,
 *   shard inventory, and disk usage display.
 * Dependencies: React, shadcn/ui, Next.js App Router
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const NODE_API = process.env.NEXT_PUBLIC_NODE_URL ?? "http://localhost:8100";
const COORD_URL_KEY = "dss_coordinator_url";

async function nodeFetch(path, options = {}) {
  const res = await fetch(`${NODE_API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

function bytes(n) {
  if (!n || n === 0) return "0 B";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)} KB`;
  return `${n} B`;
}

function ConnectionBadge({ connected }) {
  return (
    <Badge variant={connected ? "default" : "destructive"} className="text-xs gap-1">
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? "bg-white" : "bg-red-300"}`} />
      {connected ? "Connected" : "Not connected"}
    </Badge>
  );
}

function DropZone({ onFiles, disabled }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      if (disabled) return;
      const dropped = Array.from(e.dataTransfer.files);
      if (dropped.length) onFiles(dropped);
    },
    [onFiles, disabled]
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={[
        "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors select-none",
        dragging ? "border-foreground bg-muted" : "border-muted-foreground/25",
        disabled ? "opacity-40 cursor-not-allowed" : "hover:border-muted-foreground/60 hover:bg-muted/30",
      ].join(" ")}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => !disabled && onFiles(Array.from(e.target.files))}
        disabled={disabled}
      />
      <p className="text-sm font-medium">
        {dragging ? "Drop to upload" : "Drag & drop files here"}
      </p>
      <p className="text-xs text-muted-foreground mt-1">
        {disabled ? "Connect to a coordinator first" : "or click to browse — all files are encrypted"}
      </p>
    </div>
  );
}

function UploadItem({ name, pct, done, error }) {
  return (
    <div className="space-y-1.5 py-2 border-b last:border-0">
      <div className="flex justify-between text-xs">
        <span className="truncate max-w-[180px] font-medium">{name}</span>
        <span className="text-muted-foreground shrink-0 ml-2">
          {error ? "Failed" : done ? "Done" : `${pct}%`}
        </span>
      </div>
      <Progress
        value={done ? 100 : error ? 100 : pct}
        className={`h-1.5 ${error ? "[&>div]:bg-destructive" : done ? "[&>div]:bg-green-500" : ""}`}
      />
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

const DEFAULT_COORD_URL = process.env.NEXT_PUBLIC_COORDINATOR_URL || "http://localhost:8000";

export default function NodeDashboard() {
  const [info, setInfo] = useState(null);
  const [shards, setShards] = useState([]);
  const [files, setFiles] = useState([]);
  const [coordinatorUrl, setCoordinatorUrl] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(COORD_URL_KEY) || DEFAULT_COORD_URL;
    }
    return DEFAULT_COORD_URL;
  });
  const [connecting, setConnecting] = useState(false);
  const [uploads, setUploads] = useState({});
  const [downloads, setDownloads] = useState({});
  const [toast, setToast] = useState(null);
  const [error, setError] = useState("");
  const nodeReady = useRef(false);

  const showToast = (msg, variant = "ok") => {
    setToast({ msg, variant });
    setTimeout(() => setToast(null), 4000);
  };

  const refresh = useCallback(async () => {
    try {
      const [i, s] = await Promise.all([
        nodeFetch("/api/v1/node/info"),
        nodeFetch("/api/v1/shards"),
      ]);
      setInfo(i);
      setShards(s.shards ?? []);
      nodeReady.current = true;
      setError("");
      if (i.coordinator_connected) {
        const f = await nodeFetch("/api/v1/node/files").catch(() => ({ files: [] }));
        setFiles(f.files ?? []);
      }
    } catch {
      if (nodeReady.current) setError("Lost connection to DSS Node — is the service still running?");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, [refresh]);

  async function handleConnect() {
    setConnecting(true);
    setError("");
    try {
      const url = coordinatorUrl.trim();
      await nodeFetch("/api/v1/node/connect", {
        method: "POST",
        body: JSON.stringify({ coordinator_url: url }),
      });
      localStorage.setItem(COORD_URL_KEY, url);
      showToast(`Connected to ${url}`);
      await refresh();
    } catch (e) {
      setError(`Connection failed: ${e.message}`);
    } finally {
      setConnecting(false);
    }
  }

  async function handleFiles(fileList) {
    for (const file of fileList) {
      const id = `${file.name}-${Date.now()}`;
      setUploads((u) => ({ ...u, [id]: { name: file.name, pct: 0, done: false, error: null } }));

      const form = new FormData();
      form.append("file", file);

      try {
        const res = await fetch(`${NODE_API}/api/v1/node/upload-bytes`, { method: "POST", body: form });
        if (!res.ok || !res.body) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail ?? `HTTP ${res.status}`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          const parts = buf.split("\n\n");
          buf = parts.pop();
          for (const part of parts) {
            const line = part.replace(/^data: /, "").trim();
            if (!line) continue;
            try {
              const msg = JSON.parse(line);
              if (msg.type === "progress") {
                setUploads((u) => ({ ...u, [id]: { ...u[id], pct: msg.pct } }));
              } else if (msg.type === "done") {
                setUploads((u) => ({ ...u, [id]: { ...u[id], pct: 100, done: true } }));
                showToast(`${file.name} uploaded successfully`);
                setTimeout(() => setUploads((u) => { const n = { ...u }; delete n[id]; return n; }), 3000);
                await refresh();
              } else if (msg.type === "error") {
                throw new Error(msg.detail);
              }
            } catch {}
          }
        }
      } catch (e) {
        setUploads((u) => ({ ...u, [id]: { ...u[id], error: e.message } }));
        setTimeout(() => setUploads((u) => { const n = { ...u }; delete n[id]; return n; }), 6000);
      }
    }
  }

  async function handleDownload(fileId, filename) {
    const key = fileId;
    setDownloads((d) => ({ ...d, [key]: { filename: filename || fileId, pct: 0, done: false, error: null } }));
    try {
      const res = await fetch(`${NODE_API}/api/v1/node/download`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId }),
      });
      if (!res.ok || !res.body) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail ?? `HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop();
        for (const part of parts) {
          const line = part.replace(/^data: /, "").trim();
          if (!line) continue;
          try {
            const msg = JSON.parse(line);
            if (msg.type === "progress") {
              setDownloads((d) => ({ ...d, [key]: { ...d[key], pct: msg.pct } }));
            } else if (msg.type === "done") {
              setDownloads((d) => ({ ...d, [key]: { ...d[key], pct: 100, done: true } }));
              showToast(`Saved to: ${msg.saved_to}`);
              setTimeout(() => setDownloads((d) => { const n = { ...d }; delete n[key]; return n; }), 4000);
            } else if (msg.type === "error") {
              throw new Error(msg.detail);
            }
          } catch {}
        }
      }
    } catch (e) {
      setDownloads((d) => ({ ...d, [key]: { ...d[key], error: e.message } }));
      setTimeout(() => setDownloads((d) => { const n = { ...d }; delete n[key]; return n; }), 6000);
    }
  }

  const connected = info?.coordinator_connected ?? false;
  const usedPct = info ? Math.min(100, Math.round((info.used_bytes / info.capacity_bytes) * 100)) : 0;
  const uploadEntries = Object.entries(uploads);
  const downloadEntries = Object.entries(downloads);

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b sticky top-0 z-10 bg-background">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-semibold tracking-tight">DSS Node</span>
            <ConnectionBadge connected={connected} />
          </div>
          <Button variant="ghost" size="sm" onClick={refresh}>Refresh</Button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-5">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {toast && (
          <Alert variant={toast.variant === "ok" ? "default" : "destructive"}>
            <AlertDescription>{toast.msg}</AlertDescription>
          </Alert>
        )}

        <Card className={!connected ? "border-amber-400/40 bg-amber-50/5" : ""}>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Coordinator Connection</CardTitle>
            <CardDescription>
              Enter the address the admin gave you (e.g. http://192.168.1.10:8000). Your address is saved automatically.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <Input
                placeholder="http://192.168.1.10:8000"
                value={coordinatorUrl}
                onChange={(e) => setCoordinatorUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                className="font-mono text-sm"
              />
              <Button onClick={handleConnect} disabled={connecting || !coordinatorUrl.trim()} className="shrink-0">
                {connecting ? "Connecting…" : connected ? "Reconnect" : "Connect"}
              </Button>
            </div>
            {info && (
              <p className="text-xs text-muted-foreground mt-2">
                Node ID: <span className="font-mono">{info.node_id.slice(0, 16)}…</span>
              </p>
            )}
          </CardContent>
        </Card>

        <div className="grid gap-5 lg:grid-cols-3">
          <div className="space-y-5">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Storage</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs text-muted-foreground mb-1.5">
                    <span>Disk used</span>
                    <span>{bytes(info?.used_bytes)} / {bytes(info?.capacity_bytes)}</span>
                  </div>
                  <Progress value={usedPct} className="h-2" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border p-3 text-center">
                    <p className="text-2xl font-semibold">{info?.shard_count ?? 0}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Shards</p>
                  </div>
                  <div className="rounded-lg border p-3 text-center">
                    <p className="text-2xl font-semibold">{files.length}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">Files</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Upload</CardTitle>
                <CardDescription>Files are encrypted automatically before upload.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <DropZone onFiles={handleFiles} disabled={!connected} />
                {uploadEntries.length > 0 && (
                  <div className="mt-2">
                    {uploadEntries.map(([id, u]) => (
                      <UploadItem key={id} name={u.name} pct={u.pct} done={u.done} error={u.error} />
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {downloadEntries.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Downloads</CardTitle>
                </CardHeader>
                <CardContent>
                  {downloadEntries.map(([id, d]) => (
                    <UploadItem key={id} name={d.filename} pct={d.pct} done={d.done} error={d.error} />
                  ))}
                </CardContent>
              </Card>
            )}
          </div>

          <div className="lg:col-span-2 space-y-5">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">My Files</CardTitle>
                <CardDescription>
                  {connected ? "Click Download to retrieve and decrypt any file." : "Connect to a coordinator to see your files."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-72">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Filename</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead>Shards</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {files.map((f) => (
                        <TableRow key={f.file_id}>
                          <TableCell className="font-medium max-w-[160px] truncate" title={f.filename}>
                            {f.filename}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">{bytes(f.size_bytes)}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{f.data_shards}/{f.total_shards}</TableCell>
                          <TableCell>
                            <Badge variant={f.status === "available" ? "default" : "destructive"} className="text-xs">
                              {f.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 text-xs"
                              onClick={() => handleDownload(f.file_id, f.filename)}
                              disabled={!connected || !!downloads[f.file_id]}
                            >
                              {downloads[f.file_id] && !downloads[f.file_id].done && !downloads[f.file_id].error
                                ? `${downloads[f.file_id].pct}%`
                                : "Download"}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                      {files.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={5} className="text-center text-muted-foreground py-12 text-sm">
                            {connected ? "No files yet — upload something above" : "Connect to a coordinator to see files"}
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Shard Inventory</CardTitle>
                <CardDescription>Encrypted data fragments stored on this machine</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-52">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Shard ID</TableHead>
                        <TableHead className="text-right">Size</TableHead>
                        <TableHead>Checksum (SHA-256)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {shards.map((s) => (
                        <TableRow key={s.shard_id}>
                          <TableCell className="font-mono text-xs">{s.shard_id}</TableCell>
                          <TableCell className="text-right text-xs text-muted-foreground">{bytes(s.size_bytes)}</TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground">{s.sha256?.slice(0, 16)}…</TableCell>
                        </TableRow>
                      ))}
                      {shards.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={3} className="text-center text-muted-foreground py-10 text-sm">
                            No shards stored on this machine yet
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
