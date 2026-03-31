"use client";

/**
 * DSS Admin Dashboard.
 * Purpose: Login gate + live coordinator overview — health, peer list, file inventory,
 *   shard distribution, and network policy controls.
 * Responsibilities:
 *   - Show a login form when no valid token is stored; call POST /admin/login.
 *   - Store the returned JWT in localStorage under dss_admin_token.
 *   - On 401 from any API call, clear the token and return to the login screen.
 *   - Poll coordinator endpoints every 10 s when authenticated.
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const COORD = process.env.NEXT_PUBLIC_COORDINATOR_URL ?? "http://localhost:8000";
const TOKEN_KEY = "dss_admin_token";

function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

function setToken(t) {
  if (typeof window !== "undefined") localStorage.setItem(TOKEN_KEY, t);
}

function clearToken() {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

function bytes(n) {
  if (!n) return "0 B";
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)} KB`;
  return `${n} B`;
}

function StatCard({ label, value, sub, accent }) {
  return (
    <Card className={accent ? "border-amber-400/40" : ""}>
      <CardContent className="pt-5 pb-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold mt-0.5 tabular-nums">{value ?? "—"}</p>
        {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
      </CardContent>
    </Card>
  );
}

function PeerBadge({ status }) {
  return (
    <Badge
      variant={status === "online" ? "default" : status === "degraded" ? "secondary" : "destructive"}
      className="text-xs"
    >
      {status}
    </Badge>
  );
}

function ShardBar({ nodeId, count, max }) {
  const pct = max > 0 ? Math.round((count / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span className="font-mono truncate max-w-[180px]" title={nodeId}>
          {nodeId.slice(0, 16)}…
        </span>
        <span className="shrink-0 ml-2">{count} shards</span>
      </div>
      <Progress value={pct} className="h-1.5" />
    </div>
  );
}

function LoginForm({ onLogin }) {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!password.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${COORD}/api/v1/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail ?? "Login failed.");
        return;
      }
      setToken(data.access_token);
      onLogin();
    } catch {
      setError("Cannot reach the DSS Coordinator. Make sure it is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center pb-4">
          <CardTitle className="text-2xl">DSS Admin</CardTitle>
          <CardDescription>Enter your admin password to access the dashboard.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Admin password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading || !password.trim()}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-xs text-muted-foreground text-center pt-1">
              If launched via the DSS app, any password works on first login.
            </p>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminDashboard() {
  const [authed, setAuthed] = useState(false);
  const [health, setHealth] = useState(null);
  const [peers, setPeers] = useState([]);
  const [files, setFiles] = useState([]);
  const [shardCounts, setShardCounts] = useState({});
  const [network, setNetwork] = useState({ mode: "global", allowed_ips: [] });
  const [newMode, setNewMode] = useState("global");
  const [newIps, setNewIps] = useState("");
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);
  const [coordOnline, setCoordOnline] = useState(false);
  const intervalRef = useRef(null);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  async function coordFetch(path, opts = {}) {
    const res = await fetch(`${COORD}${path}`, {
      headers: { Authorization: `Bearer ${getToken()}`, "Content-Type": "application/json" },
      ...opts,
    });
    if (res.status === 401) {
      clearToken();
      setAuthed(false);
      throw new Error("Session expired. Please sign in again.");
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? `HTTP ${res.status}`);
    }
    return res.json();
  }

  const refresh = useCallback(async () => {
    try {
      const [h, p, f, s, n] = await Promise.all([
        coordFetch("/api/v1/admin/health"),
        coordFetch("/api/v1/peers"),
        coordFetch("/api/v1/files"),
        coordFetch("/api/v1/admin/shards"),
        coordFetch("/api/v1/admin/network"),
      ]);
      setHealth(h);
      setPeers(p);
      setFiles(f);
      setShardCounts(s.shard_counts ?? {});
      setNetwork(n);
      setNewMode(n.mode);
      setCoordOnline(true);
      setError("");
    } catch (e) {
      if (e.message.includes("Session expired")) {
        setError(e.message);
      } else {
        setCoordOnline(false);
        setError("Cannot reach DSS Coordinator — is it still running?");
      }
    }
  }, []);

  useEffect(() => {
    if (getToken()) setAuthed(true);
  }, []);

  useEffect(() => {
    if (!authed) {
      clearInterval(intervalRef.current);
      return;
    }
    refresh();
    intervalRef.current = setInterval(refresh, 10000);
    return () => clearInterval(intervalRef.current);
  }, [authed, refresh]);

  function handleLogin() {
    setAuthed(true);
  }

  function handleLogout() {
    clearToken();
    setAuthed(false);
    setHealth(null);
    setPeers([]);
    setFiles([]);
    setShardCounts({});
    setError("");
  }

  async function applyMode() {
    try {
      await coordFetch("/api/v1/admin/network/mode", {
        method: "POST",
        body: JSON.stringify({ mode: newMode }),
      });
      showToast(`Network mode set to "${newMode}"`);
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  async function applyIps() {
    const ips = newIps
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    try {
      await coordFetch("/api/v1/admin/network/allowed-ips", {
        method: "POST",
        body: JSON.stringify({ ips }),
      });
      showToast("Allowed IP list updated");
      await refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  if (!authed) {
    return <LoginForm onLogin={handleLogin} />;
  }

  const maxShards = Math.max(...Object.values(shardCounts), 1);
  const degraded = health?.degraded_files ?? 0;

  return (
    <div className="min-h-screen bg-background">
      <div className="border-b sticky top-0 z-10 bg-background">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-semibold tracking-tight">DSS Admin</span>
            <Badge variant={coordOnline ? "default" : "destructive"} className="text-xs">
              {coordOnline ? "● Coordinator Online" : "○ Coordinator Offline"}
            </Badge>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={refresh}>
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {toast && (
          <Alert>
            <AlertDescription>{toast}</AlertDescription>
          </Alert>
        )}

        <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total Peers" value={health?.total_peers} sub="Registered nodes" />
          <StatCard
            label="Online Peers"
            value={health?.online_peers}
            sub="Responding to heartbeat"
          />
          <StatCard
            label="Total Files"
            value={health?.total_files}
            sub="Tracked by coordinator"
          />
          <StatCard
            label="Available Files"
            value={health?.available_files}
            sub={degraded > 0 ? `${degraded} degraded` : "All healthy"}
            accent={degraded > 0}
          />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Peer Nodes</CardTitle>
                <CardDescription>All registered DSS nodes and their status</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-60">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Node ID</TableHead>
                        <TableHead>Host</TableHead>
                        <TableHead>Port</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="text-right">Disk Used</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {peers.map((p) => (
                        <TableRow key={p.node_id}>
                          <TableCell className="font-mono text-xs" title={p.node_id}>
                            {p.node_id.slice(0, 12)}…
                          </TableCell>
                          <TableCell className="text-sm">{p.host}</TableCell>
                          <TableCell className="text-sm">{p.port}</TableCell>
                          <TableCell>
                            <PeerBadge status={p.status} />
                          </TableCell>
                          <TableCell className="text-right text-xs text-muted-foreground">
                            {bytes(p.used_bytes)} / {bytes(p.capacity_bytes)}
                          </TableCell>
                        </TableRow>
                      ))}
                      {peers.length === 0 && (
                        <TableRow>
                          <TableCell
                            colSpan={5}
                            className="text-center text-muted-foreground py-10 text-sm"
                          >
                            No peers registered yet — launch a Peer Node to join this coordinator
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
                <CardTitle className="text-base">Files</CardTitle>
                <CardDescription>All files stored in the DSS cluster</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-60">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Filename</TableHead>
                        <TableHead>Size</TableHead>
                        <TableHead>Shards (k/n)</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Owner</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {files.map((f) => (
                        <TableRow key={f.file_id}>
                          <TableCell
                            className="font-medium max-w-[140px] truncate"
                            title={f.filename}
                          >
                            {f.filename}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {bytes(f.size_bytes)}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {f.data_shards}/{f.total_shards}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant={f.status === "available" ? "default" : "destructive"}
                              className="text-xs"
                            >
                              {f.status}
                            </Badge>
                          </TableCell>
                          <TableCell
                            className="font-mono text-xs text-muted-foreground"
                            title={f.owner_node_id}
                          >
                            {f.owner_node_id.slice(0, 10)}…
                          </TableCell>
                        </TableRow>
                      ))}
                      {files.length === 0 && (
                        <TableRow>
                          <TableCell
                            colSpan={5}
                            className="text-center text-muted-foreground py-10 text-sm"
                          >
                            No files uploaded yet
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Shard Distribution</CardTitle>
                <CardDescription>Shards stored per node</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.keys(shardCounts).length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No shards distributed yet
                  </p>
                )}
                {Object.entries(shardCounts).map(([nodeId, count]) => (
                  <ShardBar key={nodeId} nodeId={nodeId} count={count} max={maxShards} />
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Network Policy</CardTitle>
                <CardDescription>
                  Mode:{" "}
                  <Badge variant="outline" className="text-xs ml-1">
                    {network.mode}
                  </Badge>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-xs">Access Mode</Label>
                  <Select value={newMode} onValueChange={setNewMode}>
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="global">Global (all IPs)</SelectItem>
                      <SelectItem value="lan">LAN Only</SelectItem>
                      <SelectItem value="allowlist">Allowlist</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button size="sm" className="w-full h-8 text-xs" onClick={applyMode}>
                    Apply
                  </Button>
                </div>
                <Separator />
                <div className="space-y-2">
                  <Label className="text-xs">Allowed IPs / CIDRs</Label>
                  <Input
                    placeholder="10.0.0.0/8, 203.0.113.5"
                    value={newIps}
                    onChange={(e) => setNewIps(e.target.value)}
                    className="h-8 text-xs font-mono"
                  />
                  <p className="text-xs text-muted-foreground">
                    Current:{" "}
                    {network.allowed_ips.length > 0 ? network.allowed_ips.join(", ") : "none"}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full h-8 text-xs"
                    onClick={applyIps}
                  >
                    Update List
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
