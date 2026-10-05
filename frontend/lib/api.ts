"use client";

/** 后端 API 客户端：统一走 Next rewrites 代理 /api/backend/* → http://127.0.0.1:8000/api/* */

const BASE = "/api/backend";

export interface AuthUser {
  id: number;
  username: string;
  name: string;
  email: string;
  status: string;
  is_superuser: boolean;
  company: { id: number; name: string; code: string } | null;
  department: { id: number; name: string } | null;
  roles: { id: number; code: string; name: string }[];
  permissions: string[];
  scopes: Record<string, string[]>;
}

const TOKEN_KEY = "furui_aios_token";
const USER_KEY = "furui_aios_user";

// ---------------- Token 存储 ----------------

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/** 为裸 fetch 调用附加 Authorization 头（登录态下自动携带，供 admin 页等使用）。 */
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { ...(extra || {}) };
  const t = getToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

export function setSession(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getCachedUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

// ---------------- 请求封装 ----------------

export class ApiError extends Error {
  code: number;
  status: number;
  constructor(message: string, code: number, status: number) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  const json = await res.json().catch(() => null);

  // 统一返回格式 { code, message, data }
  // 宽松兼容：响应无 code 字段视为裸对象（如低代码 pages API），仅在有 code 且非 0 时判失败
  if (!res.ok || (json && typeof json.code === "number" && json.code !== 0)) {
    const message = json?.message || `请求失败 (${res.status})`;
    if (res.status === 401) clearSession();
    throw new ApiError(message, json?.code ?? res.status, res.status);
  }
  return (json?.data ?? json) as T;
}

export const api = {
  get: <T>(p: string) => request<T>(p),
  post: <T>(p: string, body?: unknown) => request<T>(p, { method: "POST", body }),
  put: <T>(p: string, body?: unknown) => request<T>(p, { method: "PUT", body }),
  del: <T>(p: string) => request<T>(p, { method: "DELETE" }),
  /** 无需登录的接口（如登录本身） */
  publicPost: <T>(p: string, body?: unknown) =>
    request<T>(p, { method: "POST", body, auth: false }),
};

// ---------------- 认证 API ----------------

export async function login(username: string, password: string): Promise<AuthUser> {
  const data = await api.publicPost<{ token: string; user: AuthUser }>(
    "/auth/login",
    { username, password },
  );
  setSession(data.token, data.user);
  return data.user;
}

export async function logout() {
  try {
    await api.post("/auth/logout");
  } catch {
    /* 退出失败也要清本地 */
  }
  clearSession();
}

export async function fetchMe(): Promise<AuthUser> {
  return api.get<AuthUser>("/auth/me");
}

// ---------------- SSE 流式请求 ----------------
/** EventSource 不能带 Authorization 头，所以用 fetch + ReadableStream 手撕 SSE。 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (event: string, data: any) => void,
  signal?: AbortSignal,
) {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
    cache: "no-store",
  });

  if (!res.ok || !res.body) {
    throw new ApiError(`流式请求失败 (${res.status})`, res.status, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buf = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    // 后端 sse_starlette 返回 CRLF（\r\n\r\n）分隔事件块，统一归一化为 LF，避免 indexOf("\n\n") 匹配失败导致收不到任何事件
    buf = buf.replace(/\r\n/g, "\n");

    // SSE 以空行分隔事件块
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (!dataLines.length) continue;
      const raw = dataLines.join("\n");
      let parsed: any = raw;
      try {
        parsed = JSON.parse(raw);
      } catch {
        /* 保留原始字符串 */
      }
      onEvent(event, parsed);
    }
  }
}

// ---------------- 主线 / 任务 / 审批 API ----------------

export interface MainlineStep {
  seq: number;
  title: string;
  status: string;
}

export interface TaskBrief {
  id: number;
  title: string;
  status: string;
  mode: string;
  progress: number;
  agent: string;
  user: string;
  created_at: string;
  step_count: number;
  steps_done: number;
}

export function fetchTasks(status?: string, limit = 30) {
  const qs = new URLSearchParams({ limit: String(limit) });
  if (status) qs.set("status", status);
  return api.get<{ total: number; items: TaskBrief[] }>(`/tasks?${qs}`);
}

export function fetchTaskDetail(id: number) {
  return api.get<any>(`/tasks/${id}`);
}

export interface ApprovalItem {
  id: number;
  title: string;
  action: string;
  level: number;
  status: string;
  ai_reason: string;
  agent: string;
  agent_avatar: string;
  task_id: number | null;
  decided_by: string;
  decided_at: string;
  comment: string;
  created_at: string;
}

export function fetchApprovals(status = "Pending") {
  return api.get<{ total: number; items: ApprovalItem[] }>(`/approvals?status=${status}`);
}

export function fetchApprovalDetail(id: number) {
  return api.get<
    ApprovalItem & {
      data_evidence: Record<string, any>;
      plan: any[];
      payload: Record<string, any>;
      decision_lineage: Record<string, any>;
      receipts: Array<{
        id: number;
        tool_name: string;
        params_hash: string;
        result_hash: string;
        actor_type: string;
        actor_id: number | null;
        created_at: string;
      }>;
    }
  >(`/approvals/${id}`);
}

export function approveApproval(
  id: number,
  comment = "",
  modifiedPayload?: Record<string, unknown>,
) {
  return api.post<any>(`/approvals/${id}/approve`, {
    comment,
    modified_payload: modifiedPayload ?? null,
  });
}

export function rejectApproval(id: number, comment = "") {
  return api.post<any>(`/approvals/${id}/reject`, { comment });
}

export function fetchSalesTasks(limit = 30) {
  return api.get<{ total: number; items: any[] }>(`/sales-tasks?limit=${limit}`);
}

// ---------------- 知识中心 API ----------------

export interface KnowledgeOverview {
  title: string;
  subtitle: string;
  kpis: { label: string; value: string; unit: string }[];
  health: {
    score: number;
    level: string;
    delta: number;
    dimensions: { label: string; value: number }[];
    basis: Record<string, number>;
  };
  reminders: { id: number; tag: string; tagCls: string; text: string }[];
  categories: { name: string; value: number; icon: string; color: string }[];
}

export interface KnowledgeDoc {
  id: number;
  kb_id: number;
  kb_name: string;
  title: string;
  file_type: string;
  source: string;
  version: number;
  status: string;
  author: string;
  chunk_count: number;
  char_count: number;
  valid_to: string;
  created_at: string;
}

export function fetchKnowledgeOverview() {
  return api.get<KnowledgeOverview>("/knowledge");
}

export function fetchKnowledgeBases() {
  return api.get<{ items: { id: number; name: string; category: string; doc_count: number }[] }>(
    "/knowledge/bases",
  );
}

export function fetchKnowledgeDocuments(kbId?: number) {
  const qs = kbId ? `?kb_id=${kbId}` : "";
  return api.get<{ items: KnowledgeDoc[] }>(`/knowledge/documents${qs}`);
}

export function uploadKnowledgeDoc(payload: {
  kb_id: number;
  title: string;
  content: string;
  source?: string;
  file_type?: string;
  valid_days?: number | null;
}) {
  return api.post<{ id: number; title: string; chunk_count: number; char_count: number }>(
    "/knowledge/documents",
    payload,
  );
}

export function submitKnowledgeDoc(docId: number) {
  return api.post<{ id: number; status: string }>(
    `/knowledge/documents/${docId}/submit`,
    {},
  );
}

export function publishKnowledgeDoc(docId: number) {
  return api.post<{ id: number; status: string }>(
    `/knowledge/documents/${docId}/publish`,
    {},
  );
}

export function searchKnowledge(query: string, topK = 5) {
  return api.post<{ hits: { doc_title: string; score: number; content: string }[] }>(
    "/knowledge/search",
    { query, top_k: topK },
  );
}

export function hasPerm(user: AuthUser | null, code: string): boolean {
  return !!user && user.permissions.includes(code);
}

// ---------------- 智能化中心 API ----------------

export interface SystemMeta {
  system_name: string;
  version: string;
  llm_enabled: boolean;
  llm_mode: string;
  embedding_enabled: boolean;
  ontology_mode: string;
  agent_count: number;
  skill_count: number;
  multi_agent: boolean;
}

export interface SkillInfo {
  name: string;
  description: string;
  write: boolean;
  param_count: number;
}

export function fetchMeta() {
  return api.get<SystemMeta>("/meta");
}

export function fetchSkills() {
  return api.get<{ items: SkillInfo[] }>("/skills");
}

// ---------------- 本体图 / 对象中心 API（P0 接线）----------------

export interface OntologyNode {
  type: string;
  id: string;
}

export interface OntologyEdge {
  type: string;
  source: string;
  target: string;
  direction?: "in" | "out";
}

export interface OntologySnapshot {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
  node_count: number;
  link_count: number;
  revision: string;
  pending: number;
  projected_at: string | null;
}

export interface RelatedGraph {
  root: { type: string; id: string };
  nodes: OntologyNode[];
  edges: OntologyEdge[];
  depth: number;
}

export function fetchOntologySnapshot() {
  return api.get<OntologySnapshot>("/ontology/snapshot");
}

export function fetchRelated(type: string, id: string, depth = 2) {
  return api.get<RelatedGraph>(`/ontology/related?type=${encodeURIComponent(type)}&id=${encodeURIComponent(id)}&depth=${depth}`);
}

export interface ObjectActionParam {
  name: string;
  label: string;
  type: string;
  required: boolean;
}

export interface ObjectAction {
  action: string;
  label: string;
  params: ObjectActionParam[];
  level: number;
  required_permission: string;
  tool: string;
}

export interface ObjectView {
  object: {
    id: string;
    type: string;
    name: string;
    properties: Record<string, any>;
  };
  actions: ObjectAction[];
}

export function fetchObjectView(type: string, id: string) {
  return api.get<ObjectView>(`/objects/${encodeURIComponent(type)}/${encodeURIComponent(id)}`);
}

export function runObjectAction(
  type: string,
  id: string,
  action: string,
  params: Record<string, unknown>,
) {
  return api.post<any>(`/objects/${encodeURIComponent(type)}/${encodeURIComponent(id)}/actions/${encodeURIComponent(action)}`, { params });
}

// ---------------- 数据资产 API（P0 接线）----------------

export interface DataAsset {
  id: number;
  source_id: string;
  source_name: string;
  source_status: string;
  name: string;
  kind: string;
  entity: string;
  row_count: number;
  version: string;
  fields: string[];
  lineage: { upstream: string[]; downstream: string[] };
  health_status: string;
  last_sync_at: string;
  status: string;
  created_at: string;
}

export function fetchDataAssets() {
  return api.get<{ items: DataAsset[]; total: number }>("/data-assets");
}

export function fetchDataAssetsLineage() {
  return api.get<{ items: Array<{ source_id: string; source_name: string; source_status: string; datasets: DataAsset[] }>; total: number }>("/data-assets/lineage");
}

export function createDataAsset(payload: {
  name: string;
  source_id: string;
  kind?: string;
  entity?: string;
  row_count?: number;
  version?: string;
  fields?: string[];
}) {
  return api.post<DataAsset>("/data-assets", payload);
}

export function syncDataAsset(id: number) {
  return api.post<any>(`/data-assets/${id}/sync`);
}

export function deleteDataAsset(id: number) {
  return api.del<any>(`/data-assets/${id}`);
}

// ---------------- 数据源 API（对象/资产页复用）----------------

export interface DataSourceItem {
  id: string;
  name: string;
  icon: string;
  tone: string;
  category: string;
  type: string;
  status: string;
  desc: string;
}

export function fetchDataSources() {
  return api.get<{ items: DataSourceItem[] }>("/data-sources");
}


// ---------------- Logic 决策编排画布（TASK-014 / 30-03）----------------

export interface LogicNode {
  id: number;
  seq: number;
  key: string;
  title: string;
  kind: string;
  tool: string;
  label: string;
  params: Record<string, unknown>;
  depends: number[];
}

export interface LogicGraphBrief {
  id: number;
  code: string;
  name: string;
  version: string;
  description: string;
  status: string;
  node_count: number;
  updated_at: string;
}

export interface LogicGraphDetail {
  id: number;
  code: string;
  name: string;
  version: string;
  description: string;
  status: string;
  nodes: LogicNode[];
}

export function fetchLogicGraphs() {
  return api.get<{ items: LogicGraphBrief[] }>("/logic/graphs");
}

export function fetchLogicGraph(id: number) {
  return api.get<LogicGraphDetail>(`/logic/graphs/${id}`);
}

export function updateLogicNode(
  graphId: number,
  nodeId: number,
  patch: Partial<Pick<LogicNode, "title" | "kind" | "tool" | "label" | "params" | "depends">>,
) {
  return api.post<LogicGraphDetail>(`/logic/graphs/${graphId}/nodes`, { node_id: nodeId, ...patch });
}

export function activateLogicGraph(id: number) {
  return api.post<LogicGraphDetail>(`/logic/graphs/${id}/activate`);
}


// ---------------- 低代码页面 API（TASK-015 / 40-03）----------------

export interface PageWidget {
  widget: string;
  title: string;
  params: Record<string, any>;
}

export interface AppPageBrief {
  id: number;
  code: string;
  title: string;
  description: string;
  status: string;
  version: string;
  widget_count: number;
  updated_at: string;
}

export interface AppPage extends AppPageBrief {
  layout: PageWidget[];
  created_at: string;
}

export interface WidgetTypeInfo {
  type: string;
  label: string;
  desc: string;
  default_params: Record<string, any>;
}

export function fetchWidgetTypes() {
  return api.get<{ items: WidgetTypeInfo[] }>("/pages/widget-types");
}

export function fetchPages() {
  return api.get<{ items: AppPageBrief[] }>("/pages");
}

export function fetchPageByCode(code: string) {
  return api.get<AppPage>(`/pages/by-code/${encodeURIComponent(code)}`);
}

export function createPage(payload: {
  code: string;
  title: string;
  description?: string;
  layout?: PageWidget[];
}) {
  return api.post<AppPage>("/pages", payload);
}

export function updatePage(
  id: number,
  patch: { title?: string; description?: string; layout?: PageWidget[] },
) {
  return api.put<AppPage>(`/pages/${id}`, patch);
}

export function publishPage(id: number) {
  return api.post<AppPage>(`/pages/${id}/publish`);
}

export function draftPage(id: number) {
  return api.post<AppPage>(`/pages/${id}/draft`);
}

export function deletePage(id: number) {
  return api.del<{ ok: boolean }>(`/pages/${id}`);
}

// ---------------- 平台资产中心 API（TASK-016 / 50 全系）----------------

export interface AssetBundleItem {
  id: number;
  code: string;
  name: string;
  description: string;
  version: string;
  kind: string;
  status: string;
  manifest: { requires: string[]; nav_entry: { title?: string; href?: string; icon?: string; label?: string; perm?: string } | null };
  nav_entry: { title?: string; href?: string; icon?: string; label?: string; perm?: string } | null;
  page_codes: string[];
  graph_codes: string[];
  created_by_company_id: number | null;
  created_at: string;
  installed: boolean;
  installation: {
    id: number;
    status: string;
    bundle_version: string;
    derived_pages: { code: string; page_id: number; title: string; reused: boolean }[];
    derived_graphs: { code: string; graph_id: number; name: string; reused: boolean }[];
    installed_at: string;
  } | null;
}

export interface AssetInstallResult {
  installation_id: number;
  bundle: { id: number; code: string; name: string; version: string };
  status: string;
  created: boolean;
  derived_pages: { code: string; page_id: number; title: string; reused: boolean }[];
  derived_graphs: { code: string; graph_id: number; name: string; reused: boolean }[];
}

export interface InstalledNavItem {
  href: string;
  icon: string;
  label: string;
  perm: string;
  bundle: string;
}

export function fetchAssetBundles() {
  return api.get<{ items: AssetBundleItem[] }>("/assets/bundles");
}

export function fetchInstalledNav() {
  return api.get<{ items: InstalledNavItem[] }>("/assets/installed-nav");
}

export function installAssetBundle(bundleId: number) {
  return api.post<AssetInstallResult>("/assets/install", { bundle_id: bundleId });
}

export function rederiveAsset(installationId: number) {
  return api.post<any>(`/assets/installations/${installationId}/rederive`, {});
}

export function uninstallAsset(installationId: number) {
  return api.post<any>(`/assets/installations/${installationId}/uninstall`, {});
}

export function resolveAssetBundle(bundleCode: string) {
  return api.get<{ bundle: { id: number; code: string; name: string; version: string }; derived_pages: { code: string; page_id: number; title: string }[]; derived_graphs: { code: string; graph_id: number; name: string }[] }>(
    `/assets/resolve/${encodeURIComponent(bundleCode)}`,
  );
}

// ---------------- 交付发布 / 边缘协同 API（TASK-017 / 70-03 + 80-01 + 80-02）----------------

export interface ReleaseChangeItem {
  kind: string;
  summary: string;
}

export interface ReleaseItem {
  id: number;
  version: string;
  channel: string; // draft | staging | production
  status: string; // draft | promoted | recalled | superseded
  manifest: Record<string, unknown>;
  sbom: unknown[];
  changes: ReleaseChangeItem[];
  signature: string;
  signature_valid: boolean;
  notes: string;
  promoted_to: string;
  released_by_company_id: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface EdgeSiteItem {
  id: number;
  site_code: string;
  name: string;
  site_type: string;
  endpoint: string;
  company_id: number | null;
  release_id: number;
  status: string; // registered | online | offline | syncing
  version: string;
  last_heartbeat_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

/** 注册站点响应：token 明文**只在这里出现一次**，库里只存 sha256。 */
export interface SiteRegisterResult extends EdgeSiteItem {
  token: string;
}

export interface SiteSyncTarget {
  site_code: string;
  company_id: number | null;
  from_version: string;
  to_version: string;
  upgrade_needed: boolean;
  release: ReleaseItem | null;
  served_at: string | null;
}

export function fetchReleases(channel?: string) {
  const qs = channel ? "?channel=" + encodeURIComponent(channel) : "";
  return api.get<{ items: ReleaseItem[] }>("/releases" + qs);
}

export function createRelease(payload: {
  version: string;
  channel?: string;
  notes?: string;
  manifest?: Record<string, unknown>;
  sbom?: unknown[];
  changes?: { kind?: string; summary?: string }[];
}) {
  return api.post<ReleaseItem>("/releases", payload);
}

export function fetchRelease(id: number) {
  return api.get<ReleaseItem>("/releases/" + id);
}

export function promoteRelease(id: number) {
  return api.post<ReleaseItem>("/releases/" + id + "/promote");
}

export function recallRelease(id: number) {
  return api.post<ReleaseItem>("/releases/" + id + "/recall");
}

export function fetchEdgeSites() {
  return api.get<{ items: EdgeSiteItem[] }>("/edge-sites");
}

export function registerEdgeSite(payload: {
  site_code: string;
  name?: string;
  site_type?: string;
  endpoint?: string;
  metadata?: Record<string, unknown>;
}) {
  return api.post<SiteRegisterResult>("/edge-sites/register", payload);
}

export function heartbeatEdgeSite(
  siteCode: string,
  payload: { token?: string; version?: string; status?: string },
) {
  return api.post<EdgeSiteItem>(
    "/edge-sites/" + encodeURIComponent(siteCode) + "/heartbeat",
    payload,
  );
}

export function fetchSiteSync(siteCode: string) {
  return api.get<SiteSyncTarget>(
    "/edge-sites/" + encodeURIComponent(siteCode) + "/sync",
  );
}

export function unregisterEdgeSite(siteCode: string) {
  return api.del<{ ok: boolean }>("/edge-sites/" + encodeURIComponent(siteCode));
}
