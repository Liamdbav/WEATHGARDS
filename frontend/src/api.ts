export interface HealthResponse {
  status: string;
  os: string;
  docker_available: boolean;
}

export interface ScanResult {
  id: string;
  name: string;
  type: "docker" | "process" | "service";
  status: string;
  metadata: Record<string, unknown>;
  os_origin: string;
}

export interface ToolParam {
  name: string;
  type: string;
  description: string;
  required: boolean;
  default?: string | number | null;
}

export interface ToolDefinition {
  name: string;
  description: string;
  target_type: "docker" | "process" | "service" | "any";
  parameters: ToolParam[];
  target_param: string | null;
}

export interface ActivatedTool {
  id: string;
  tool_name: string;
  target_name: string;
  enabled: boolean;
  activated_at: string;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const detail = await res.json().then((d: { detail?: string }) => d.detail).catch(() => `HTTP ${res.status}`);
    throw new Error(String(detail ?? `HTTP ${res.status}`));
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function fetchScan(): Promise<ScanResult[]> {
  return request<ScanResult[]>("/api/scan");
}

export async function fetchCatalog(): Promise<ToolDefinition[]> {
  return request<ToolDefinition[]>("/api/catalog");
}

export async function activateTool(
  tool_name: string,
  target_name: string,
): Promise<ActivatedTool> {
  return request<ActivatedTool>("/api/activate-tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_name, target_name }),
  });
}

export async function fetchActiveTools(): Promise<ActivatedTool[]> {
  return request<ActivatedTool[]>("/api/tools/active");
}

export async function deactivateTool(id: string): Promise<void> {
  const res = await fetch(`/api/tools/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
}

// ---------------------------------------------------------------------------
// MCP server control
// ---------------------------------------------------------------------------

export interface MCPStatus {
  running: boolean;
  host: string | null;
  port: number | null;
  tool_count: number;
  network_ip: string | null;
  token_configured: boolean;
  tls_enabled: boolean;
}

export interface MCPConnectionInfo {
  url: string;
  token: string;
  snippet: Record<string, unknown>;
}

export interface MCPSnippets {
  url: string;
  token: string;
  claude_desktop: Record<string, unknown>;
  opencode: Record<string, unknown>;
  curl: string;
}

export async function fetchMCPStatus(): Promise<MCPStatus> {
  return request<MCPStatus>("/api/mcp/status");
}

export async function startMCP(host: string, port: number): Promise<MCPStatus> {
  return request<MCPStatus>("/api/mcp/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, port }),
  });
}

export async function stopMCP(): Promise<MCPStatus> {
  return request<MCPStatus>("/api/mcp/stop", { method: "POST" });
}

export async function fetchMCPConnectionInfo(): Promise<MCPConnectionInfo> {
  return request<MCPConnectionInfo>("/api/mcp/connection-info");
}

export async function fetchMCPSnippets(): Promise<MCPSnippets> {
  return request<MCPSnippets>("/api/mcp/snippets");
}

// ---------------------------------------------------------------------------
// App settings
// ---------------------------------------------------------------------------

export interface ScannerToggles {
  docker: boolean;
  processes: boolean;
  services: boolean;
}

export interface AppSettings {
  mcp_host: string;
  mcp_port: number;
  mcp_transport: string;
  network_exposed: boolean;
  auto_scan_interval: number;
  scanner_toggles: ScannerToggles;
}

export async function fetchAppSettings(): Promise<AppSettings> {
  return request<AppSettings>("/api/settings");
}

export async function saveAppSettings(settings: AppSettings): Promise<AppSettings> {
  return request<AppSettings>("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export async function testTool(
  tool_name: string,
  target_name: string | null,
  params: Record<string, unknown> = {},
): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>("/api/test-tool", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tool_name, target_name, params }),
  });
}
