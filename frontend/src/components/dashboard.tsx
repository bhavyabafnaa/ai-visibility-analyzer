"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, apiRequest } from "@/lib/api";
import type {
  AnalysisBundle,
  AnalysisCitationResponse,
  AnalysisClaimResponse,
  AnalysisEntityResponse,
  AnalysisScoreResponse,
  AnalysisStartResponse,
  CrawlJobResponse,
  ProjectCreate,
  ProjectResponse,
  ProviderAvailabilityResponse,
} from "@/lib/api-types";
import {
  buildDashboardEvidence,
  displayPercent,
  isReservedExampleUrl,
  safeExternalUrl,
  type DashboardEvidence,
} from "@/lib/evidence";

import { Icon, type IconName } from "./icons";

const DEFAULT_PROMPTS = [
  "What are the best AI visibility platforms for B2B teams?",
  "Compare Acme Cloud with Northstar AI for citation monitoring.",
  "Which tools help marketing teams track brand mentions in AI answers?",
  "What should an enterprise look for in a generative search analytics platform?",
];
const ANALYSIS_POLL_INTERVAL_MS = 2_000;
const ANALYSIS_MAX_POLL_ATTEMPTS = 150;
const TERMINAL_ANALYSIS_STATUSES = new Set(["succeeded", "completed_with_errors", "failed"]);

type View = "overview" | "queries" | "citations" | "entities" | "claims" | "recommendations" | "setup";
type LoadState = "loading" | "ready" | "error";
type RunState = "idle" | "running" | "succeeded" | "partial" | "failed";

interface CompetitorDraft {
  name: string;
  domain: string;
  aliases: string;
}

interface SetupDraft {
  name: string;
  domain: string;
  aliases: string;
  competitors: CompetitorDraft[];
}

interface AttachedCrawlEvidence {
  crawlId: string;
  pageCount: number;
}

interface CrawlRecoveryResult {
  key: string;
  error: string;
}

const DEMO_SETUP: SetupDraft = {
  name: "Acme Cloud",
  domain: "https://acme.example",
  aliases: "Acme, AcmeCloud",
  competitors: [
    {
      name: "Northstar AI",
      domain: "https://northstar.example",
      aliases: "Northstar",
    },
    {
      name: "Summit Search",
      domain: "https://summit.example",
      aliases: "Summit",
    },
  ],
};

const NAV_ITEMS: Array<{ view: View; label: string; icon: IconName }> = [
  { view: "overview", label: "Overview", icon: "grid" },
  { view: "queries", label: "Query intelligence", icon: "search" },
  { view: "citations", label: "Citation sources", icon: "globe" },
  { view: "entities", label: "Entity gaps", icon: "users" },
  { view: "claims", label: "Claim risk", icon: "shield" },
  { view: "recommendations", label: "Recommendations", icon: "sparkles" },
];

function splitAliases(value: string) {
  return value
    .split(",")
    .map((alias) => alias.trim())
    .filter(Boolean);
}

function providerLabel(value: string) {
  return value === "openai"
    ? "OpenAI"
    : value === "gemini"
      ? "Gemini"
      : value === "perplexity"
        ? "Perplexity"
        : value === "mock"
          ? "MockProvider"
          : value;
}

function humanTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function duration(startedAt: string, completedAt: string) {
  const elapsed = Math.max(0, new Date(completedAt).getTime() - new Date(startedAt).getTime());
  if (elapsed < 1_000) return `${elapsed}ms`;
  return `${(elapsed / 1_000).toFixed(1)}s`;
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

function emptyBundle(analysis: AnalysisStartResponse): AnalysisBundle {
  return { analysis, citations: [], entities: [], scores: [], claims: [] };
}

function waitForAnalysisPoll() {
  return new Promise<void>((resolve) => window.setTimeout(resolve, ANALYSIS_POLL_INTERVAL_MS));
}

export function Dashboard() {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [projects, setProjects] = useState<ProjectResponse[]>([]);
  const [providers, setProviders] = useState<ProviderAvailabilityResponse[]>([]);
  const [activeProjectId, setActiveProjectId] = useState("");
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [prompts, setPrompts] = useState(DEFAULT_PROMPTS);
  const [view, setView] = useState<View>("overview");
  const [bundle, setBundle] = useState<AnalysisBundle | null>(null);
  const [runState, setRunState] = useState<RunState>("idle");
  const [error, setError] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [setupDraft, setSetupDraft] = useState<SetupDraft>(DEMO_SETUP);
  const [savingProject, setSavingProject] = useState(false);
  const [activeCrawl, setActiveCrawl] = useState<CrawlJobResponse | null>(null);
  const [crawlRecoveryAttempt, setCrawlRecoveryAttempt] = useState(0);
  const [crawlRecoveryResult, setCrawlRecoveryResult] = useState<CrawlRecoveryResult>({
    key: "",
    error: "",
  });
  const [crawlStarting, setCrawlStarting] = useState(false);
  const [crawlPollingError, setCrawlPollingError] = useState("");
  const [latestSuccessfulCrawlId, setLatestSuccessfulCrawlId] = useState<string | null>(null);
  const [crawlPollAttempt, setCrawlPollAttempt] = useState(0);
  const [analysisCrawlEvidence, setAnalysisCrawlEvidence] =
    useState<AttachedCrawlEvidence | null>(null);
  const projectScopeRef = useRef(0);
  const crawlStartInFlightRef = useRef(false);

  const activeProject = projects.find((project) => project.id === activeProjectId) ?? null;
  const activeSiteId = activeProject?.site?.id ?? null;
  const activeSiteUrl = activeProject?.site?.url ?? null;
  const crawlRecoveryKey = activeSiteId ? `${activeSiteId}:${crawlRecoveryAttempt}` : "";
  const canRecoverCrawl = Boolean(
    activeSiteId && activeSiteUrl && !isReservedExampleUrl(activeSiteUrl),
  );
  const crawlRecovering = canRecoverCrawl && crawlRecoveryResult.key !== crawlRecoveryKey;
  const crawlRecoveryError =
    crawlRecoveryResult.key === crawlRecoveryKey ? crawlRecoveryResult.error : "";
  const evidence = useMemo(
    () => (activeProject && bundle ? buildDashboardEvidence(activeProject, bundle) : null),
    [activeProject, bundle],
  );

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const [loadedProjects, loadedProviders] = await Promise.all([
          apiRequest<ProjectResponse[]>("/projects"),
          apiRequest<ProviderAvailabilityResponse[]>("/providers"),
        ]);
        if (!active) return;
        setProjects(loadedProjects);
        setProviders(loadedProviders);
        setActiveProjectId(loadedProjects[0]?.id ?? "");
        const enabled = loadedProviders.filter((provider) => provider.enabled);
        const mock = enabled.find((provider) => provider.name === "mock");
        setSelectedProviders(mock ? [mock.name] : enabled.slice(0, 1).map((provider) => provider.name));
        setView(loadedProjects.length ? "overview" : "setup");
        setLoadState("ready");
      } catch (requestError) {
        if (!active) return;
        setError(
          requestError instanceof Error
            ? requestError.message
            : "GeoLens could not load the workspace.",
        );
        setLoadState("error");
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  useEffect(
    () => () => {
      projectScopeRef.current += 1;
      crawlStartInFlightRef.current = false;
    },
    [],
  );

  useEffect(() => {
    if (!activeSiteId || !activeSiteUrl || isReservedExampleUrl(activeSiteUrl)) {
      return;
    }

    const siteId = activeSiteId;
    const recoveryKey = `${siteId}:${crawlRecoveryAttempt}`;
    const projectScope = projectScopeRef.current;
    let cancelled = false;

    async function recoverLatestCrawl() {
      try {
        const crawl = await apiRequest<CrawlJobResponse | null>(`/sites/${siteId}/crawls/latest`);
        if (cancelled || projectScope !== projectScopeRef.current) return;
        if (crawl && crawl.site_id !== siteId) {
          setCrawlRecoveryResult({
            key: recoveryKey,
            error: "The saved crawl did not match the active project's website.",
          });
          return;
        }
        setActiveCrawl(crawl);
        setLatestSuccessfulCrawlId(crawl?.status === "succeeded" ? crawl.id : null);
        setCrawlRecoveryResult({ key: recoveryKey, error: "" });
      } catch (requestError) {
        if (cancelled || projectScope !== projectScopeRef.current) return;
        setCrawlRecoveryResult({
          key: recoveryKey,
          error:
            requestError instanceof Error
              ? requestError.message
              : "The latest crawl status could not be loaded.",
        });
      }
    }

    void recoverLatestCrawl();
    return () => {
      cancelled = true;
    };
  }, [activeSiteId, activeSiteUrl, crawlRecoveryAttempt]);

  useEffect(() => {
    if (
      !activeCrawl ||
      !activeProject?.site ||
      crawlPollingError ||
      !["pending", "running"].includes(activeCrawl.status)
    ) {
      return;
    }

    const crawlId = activeCrawl.id;
    const siteId = activeProject.site.id;
    const projectScope = projectScopeRef.current;
    let cancelled = false;
    const timeoutId = window.setTimeout(async () => {
      try {
        const crawl = await apiRequest<CrawlJobResponse>(`/crawls/${crawlId}`);
        if (cancelled || projectScope !== projectScopeRef.current) return;
        if (crawl.site_id !== siteId) {
          setCrawlPollingError("The crawl status did not match the active project's website.");
          return;
        }
        setActiveCrawl(crawl);
        setCrawlPollingError("");
        if (crawl.status === "succeeded") {
          setLatestSuccessfulCrawlId(crawl.id);
        } else if (crawl.status === "failed") {
          setLatestSuccessfulCrawlId(null);
        }
      } catch (requestError) {
        if (cancelled || projectScope !== projectScopeRef.current) return;
        setCrawlPollingError(
          requestError instanceof Error
            ? requestError.message
            : "Crawl status could not be refreshed.",
        );
      }
    }, 2_000);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [activeCrawl, activeProject?.site, crawlPollAttempt, crawlPollingError]);

  function clearProjectScopedState() {
    projectScopeRef.current += 1;
    crawlStartInFlightRef.current = false;
    setActiveCrawl(null);
    setCrawlRecoveryAttempt(0);
    setCrawlRecoveryResult({ key: "", error: "" });
    setCrawlStarting(false);
    setCrawlPollingError("");
    setLatestSuccessfulCrawlId(null);
    setCrawlPollAttempt(0);
    setAnalysisCrawlEvidence(null);
  }

  async function createProject() {
    if (!setupDraft.name.trim() || !setupDraft.domain.trim()) {
      setError("Project name and target domain are required.");
      return;
    }
    const validCompetitors = setupDraft.competitors.filter(
      (competitor) => competitor.name.trim() && competitor.domain.trim(),
    );
    const payload: ProjectCreate = {
      name: setupDraft.name.trim(),
      aliases: splitAliases(setupDraft.aliases),
      site: { url: setupDraft.domain.trim() },
      competitors: validCompetitors.map((competitor) => ({
        name: competitor.name.trim(),
        url: competitor.domain.trim(),
        aliases: splitAliases(competitor.aliases),
      })),
    };
    setSavingProject(true);
    setError("");
    try {
      const project = await apiRequest<ProjectResponse>("/projects", {
        method: "POST",
        body: payload,
      });
      setProjects((current) => [project, ...current]);
      clearProjectScopedState();
      setActiveProjectId(project.id);
      setPrompts(DEFAULT_PROMPTS);
      setBundle(null);
      setRunState("idle");
      setView("overview");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Project creation failed.");
    } finally {
      setSavingProject(false);
    }
  }

  function selectProject(projectId: string) {
    clearProjectScopedState();
    setActiveProjectId(projectId);
    setBundle(null);
    setRunState("idle");
    setError("");
    setView("overview");
  }

  function toggleProvider(name: string) {
    setSelectedProviders((current) =>
      current.includes(name) ? current.filter((provider) => provider !== name) : [...current, name],
    );
  }

  async function startCrawl() {
    const project = activeProject;
    const site = project?.site;
    if (
      !project ||
      !site ||
      isReservedExampleUrl(site.url) ||
      crawlStartInFlightRef.current ||
      crawlRecovering ||
      crawlStarting ||
      activeCrawl?.status === "pending" ||
      activeCrawl?.status === "running"
    ) {
      return;
    }

    const projectScope = projectScopeRef.current;
    crawlStartInFlightRef.current = true;
    setCrawlStarting(true);
    setActiveCrawl(null);
    setLatestSuccessfulCrawlId(null);
    setCrawlPollingError("");
    try {
      const crawl = await apiRequest<CrawlJobResponse>(`/sites/${site.id}/crawls`, {
        method: "POST",
      });
      if (projectScope !== projectScopeRef.current) return;
      if (crawl.site_id !== site.id) {
        setCrawlPollingError("The crawl response did not match the active project's website.");
        return;
      }
      setActiveCrawl(crawl);
      if (crawl.status === "succeeded") {
        setLatestSuccessfulCrawlId(crawl.id);
      }
    } catch (requestError) {
      if (projectScope !== projectScopeRef.current) return;
      setCrawlPollingError(
        requestError instanceof Error ? requestError.message : "The website crawl could not start.",
      );
    } finally {
      if (projectScope === projectScopeRef.current) {
        crawlStartInFlightRef.current = false;
        setCrawlStarting(false);
      }
    }
  }

  function retryCrawlPolling() {
    setCrawlPollingError("");
    setCrawlPollAttempt((current) => current + 1);
  }

  function retryCrawlRecovery() {
    setCrawlRecoveryAttempt((current) => current + 1);
  }

  async function runAnalysis() {
    if (!activeProject) {
      setView("setup");
      return;
    }
    const cleanPrompts = prompts.map((prompt) => prompt.trim()).filter(Boolean);
    if (!selectedProviders.length || !cleanPrompts.length) {
      setError("Select at least one provider and add at least one query.");
      return;
    }
    setError("");
    setRunState("running");
    const projectScope = projectScopeRef.current;
    const attachedCrawl =
      activeCrawl?.status === "succeeded" &&
      activeCrawl.site_id === activeProject.site?.id &&
      activeCrawl.id === latestSuccessfulCrawlId
        ? { crawlId: activeCrawl.id, pageCount: activeCrawl.page_count }
        : null;
    try {
      let analysis = await apiRequest<AnalysisStartResponse>("/analyses", {
        method: "POST",
        body: {
          project_id: activeProject.id,
          ...(attachedCrawl ? { crawl_job_id: attachedCrawl.crawlId } : {}),
          providers: selectedProviders,
          prompts: cleanPrompts,
        },
      });
      if (projectScope !== projectScopeRef.current) return;
      for (
        let attempt = 0;
        !TERMINAL_ANALYSIS_STATUSES.has(analysis.status) &&
        attempt < ANALYSIS_MAX_POLL_ATTEMPTS;
        attempt += 1
      ) {
        await waitForAnalysisPoll();
        if (projectScope !== projectScopeRef.current) return;
        analysis = await apiRequest<AnalysisStartResponse>(
          `/analyses/${analysis.analysis_id}`,
        );
        if (analysis.project_id !== activeProject.id) {
          throw new Error("The analysis status did not match the active project.");
        }
      }
      if (!TERMINAL_ANALYSIS_STATUSES.has(analysis.status)) {
        throw new Error("Analysis status polling timed out. The worker may still be processing it.");
      }
      let nextBundle = emptyBundle(analysis);
      if (analysis.persisted) {
        const base = `/analyses/${analysis.analysis_id}`;
        try {
          const [citations, entities, scores, claims] = await Promise.all([
            apiRequest<AnalysisCitationResponse[]>(`${base}/citations`),
            apiRequest<AnalysisEntityResponse[]>(`${base}/entities`),
            apiRequest<AnalysisScoreResponse[]>(`${base}/scores`),
            apiRequest<AnalysisClaimResponse[]>(`${base}/claims`),
          ]);
          if (projectScope !== projectScopeRef.current) return;
          nextBundle = { analysis, citations, entities, scores, claims };
        } catch (requestError) {
          setError(
            requestError instanceof Error
              ? `Analysis completed, but persisted evidence could not be loaded: ${requestError.message}`
              : "Analysis completed, but persisted evidence could not be loaded.",
          );
        }
      }
      if (projectScope !== projectScopeRef.current) return;
      setBundle(nextBundle);
      setAnalysisCrawlEvidence(attachedCrawl);
      if (analysis.status === "failed") {
        setError(analysis.error_message ?? "Analysis processing failed.");
      }
      setRunState(
        analysis.status === "succeeded"
          ? "succeeded"
          : analysis.status === "completed_with_errors"
            ? "partial"
            : "failed",
      );
      setView("overview");
    } catch (requestError) {
      if (projectScope !== projectScopeRef.current) return;
      const message =
        requestError instanceof ApiError || requestError instanceof Error
          ? requestError.message
          : "Analysis failed to start.";
      setError(message);
      setRunState("failed");
    }
  }

  if (loadState === "loading") return <LoadingScreen />;
  if (loadState === "error") return <ErrorScreen message={error} />;

  const projectInitials = activeProject?.name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toLocaleUpperCase();

  return (
    <div className="app-shell">
      <button
        aria-label="Close navigation"
        className={`mobile-scrim ${sidebarOpen ? "is-visible" : ""}`}
        onClick={() => setSidebarOpen(false)}
        type="button"
      />
      <aside className={`sidebar ${sidebarOpen ? "is-open" : ""}`}>
        <div className="brand-lockup">
          <span className="brand-mark">
            <Icon name="layers" size={19} />
          </span>
          <span>GeoLens</span>
          <button
            aria-label="Close menu"
            className="icon-button mobile-only"
            onClick={() => setSidebarOpen(false)}
            type="button"
          >
            <Icon name="close" />
          </button>
        </div>

        <div className="project-switcher">
          {activeProject ? (
            <>
              <span className="project-avatar">{projectInitials}</span>
              <label>
                <span>Active project</span>
                <select
                  aria-label="Active project"
                  onChange={(event) => selectProject(event.target.value)}
                  value={activeProjectId}
                >
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <span className="muted-copy">No project configured</span>
          )}
        </div>

        <nav aria-label="Primary">
          <p className="nav-label">Workspace</p>
          {NAV_ITEMS.map((item) => (
            <button
              className={view === item.view ? "active" : ""}
              disabled={!activeProject}
              key={item.view}
              onClick={() => {
                setView(item.view);
                setSidebarOpen(false);
              }}
              type="button"
            >
              <Icon name={item.icon} />
              {item.label}
              {item.view === "recommendations" && evidence ? (
                <span className="nav-count">{evidence.recommendations.length}</span>
              ) : null}
            </button>
          ))}
          <p className="nav-label nav-label-spaced">Manage</p>
          <button
            className={view === "setup" ? "active" : ""}
            onClick={() => {
              setSetupDraft(DEMO_SETUP);
              setView("setup");
              setSidebarOpen(false);
            }}
            type="button"
          >
            <Icon name="settings" />
            Project setup
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="demo-indicator">
            <span className="status-dot" />
            <span>
              <strong>Deterministic demo</strong>
              <small>MockProvider · no API key</small>
            </span>
          </div>
          <a href="https://github.com/bhavyabafnaa/ai-visibility-analyzer" rel="noreferrer" target="_blank">
            <Icon name="help" />
            Documentation
          </a>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <button
            aria-label="Open navigation"
            className="icon-button mobile-only"
            onClick={() => setSidebarOpen(true)}
            type="button"
          >
            <Icon name="menu" />
          </button>
          <div className="breadcrumb">
            <span>{activeProject?.name ?? "Workspace"}</span>
            <Icon name="arrow" size={14} />
            <strong>{NAV_ITEMS.find((item) => item.view === view)?.label ?? "Project setup"}</strong>
          </div>
          <div className="topbar-actions">
            {bundle ? (
              <span className={`run-pill ${runState}`}>
                <span className="status-dot" />
                {runState === "partial" ? "Partial results" : statusLabel(runState)}
              </span>
            ) : null}
            <button
              className="button button-primary top-run"
              disabled={runState === "running" || !activeProject}
              onClick={() => void runAnalysis()}
              type="button"
            >
              <Icon name={runState === "running" ? "activity" : "sparkles"} />
              {runState === "running" ? "Analyzing…" : "Run analysis"}
            </button>
          </div>
        </header>

        <main className="main-content">
          {error ? (
            <div className="inline-alert" role="alert">
              <Icon name="warning" />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")} type="button">
                <Icon name="close" size={16} />
              </button>
            </div>
          ) : null}

          {view === "setup" ? (
            <SetupPanel
              draft={setupDraft}
              isFirstProject={!projects.length}
              onChange={setSetupDraft}
              onCreate={() => void createProject()}
              saving={savingProject}
            />
          ) : activeProject ? (
            <WorkspaceView
              bundle={bundle}
              activeCrawl={activeCrawl}
              analysisCrawlEvidence={analysisCrawlEvidence}
              crawlPollingError={crawlPollingError}
              crawlRecovering={crawlRecovering}
              crawlRecoveryError={crawlRecoveryError}
              crawlStarting={crawlStarting}
              evidence={evidence}
              onCrawl={() => void startCrawl()}
              onPromptChange={setPrompts}
              onRetryCrawlPolling={retryCrawlPolling}
              onRetryCrawlRecovery={retryCrawlRecovery}
              onRun={() => void runAnalysis()}
              onSelectView={setView}
              onToggleProvider={toggleProvider}
              project={activeProject}
              prompts={prompts}
              providers={providers}
              runState={runState}
              selectedProviders={selectedProviders}
              view={view}
            />
          ) : (
            <SetupPanel
              draft={setupDraft}
              isFirstProject
              onChange={setSetupDraft}
              onCreate={() => void createProject()}
              saving={savingProject}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="loading-shell" aria-label="Loading GeoLens">
      <aside className="loading-sidebar">
        <span className="skeleton skeleton-brand" />
        {Array.from({ length: 7 }).map((_, index) => (
          <span className="skeleton skeleton-nav" key={index} />
        ))}
      </aside>
      <main>
        <span className="skeleton skeleton-title" />
        <div className="loading-grid">
          {Array.from({ length: 5 }).map((_, index) => (
            <span className="skeleton skeleton-card" key={index} />
          ))}
        </div>
        <span className="skeleton skeleton-table" />
      </main>
    </div>
  );
}

function ErrorScreen({ message }: { message: string }) {
  return (
    <main className="state-screen">
      <span className="state-icon error">
        <Icon name="warning" size={26} />
      </span>
      <p className="eyebrow">Connection error</p>
      <h1>GeoLens could not load this workspace</h1>
      <p>{message}</p>
      <button className="button button-primary" onClick={() => window.location.reload()} type="button">
        Try again
      </button>
      <small>Confirm that the backend API and PostgreSQL are ready.</small>
    </main>
  );
}

interface SetupPanelProps {
  draft: SetupDraft;
  isFirstProject: boolean;
  saving: boolean;
  onChange: (draft: SetupDraft) => void;
  onCreate: () => void;
}

function SetupPanel({ draft, isFirstProject, saving, onChange, onCreate }: SetupPanelProps) {
  function updateCompetitor(index: number, change: Partial<CompetitorDraft>) {
    onChange({
      ...draft,
      competitors: draft.competitors.map((competitor, competitorIndex) =>
        competitorIndex === index ? { ...competitor, ...change } : competitor,
      ),
    });
  }

  return (
    <div className="setup-page">
      <section className="page-heading setup-heading">
        <div>
          <p className="eyebrow">{isFirstProject ? "Welcome to GeoLens" : "New project"}</p>
          <h1>{isFirstProject ? "Set up your first project" : "Configure another project"}</h1>
          <p>
            Define the exact brand and comparison set used by deterministic mention, citation,
            entity, and recommendation calculations.
          </p>
        </div>
        <span className="demo-badge">
          <Icon name="sparkles" />
          Pre-filled demo
        </span>
      </section>

      <div className="setup-layout">
        <div className="setup-steps" aria-label="Project setup progress">
          <div className="setup-step active">
            <span>1</span>
            <div>
              <strong>Target brand</strong>
              <small>Name, domain & aliases</small>
            </div>
          </div>
          <div className="setup-connector" />
          <div className="setup-step active">
            <span>2</span>
            <div>
              <strong>Comparison set</strong>
              <small>Tracked competitors</small>
            </div>
          </div>
          <div className="setup-connector" />
          <div className="setup-step">
            <span>3</span>
            <div>
              <strong>Run analysis</strong>
              <small>Queries & providers</small>
            </div>
          </div>
        </div>

        <div className="setup-form-stack">
          <section className="panel setup-card">
            <div className="panel-heading">
              <span className="number-mark">01</span>
              <div>
                <h2>Target brand</h2>
                <p>This entity anchors visibility and target-domain citation metrics.</p>
              </div>
            </div>
            <div className="form-grid">
              <label>
                <span>Project / brand name</span>
                <input
                  aria-label="Project / brand name"
                  onChange={(event) => onChange({ ...draft, name: event.target.value })}
                  placeholder="Acme Cloud"
                  value={draft.name}
                />
              </label>
              <label>
                <span>Primary domain</span>
                <div className="input-with-icon">
                  <Icon name="globe" />
                  <input
                    aria-label="Primary domain"
                    onChange={(event) => onChange({ ...draft, domain: event.target.value })}
                    placeholder="https://example.com"
                    type="url"
                    value={draft.domain}
                  />
                </div>
              </label>
              <label className="full-field">
                <span>
                  Brand aliases <small>Comma separated</small>
                </span>
                <input
                  aria-label="Brand aliases"
                  onChange={(event) => onChange({ ...draft, aliases: event.target.value })}
                  placeholder="Acme, AcmeCloud"
                  value={draft.aliases}
                />
                <small className="field-help">
                  Matching is case-insensitive and uses whole-term boundaries.
                </small>
              </label>
            </div>
          </section>

          <section className="panel setup-card">
            <div className="panel-heading panel-heading-row">
              <div className="heading-with-number">
                <span className="number-mark">02</span>
                <div>
                  <h2>Competitor configuration</h2>
                  <p>Track only entities that belong in the same answer comparison set.</p>
                </div>
              </div>
              <button
                className="button button-secondary button-small"
                onClick={() =>
                  onChange({
                    ...draft,
                    competitors: [
                      ...draft.competitors,
                      { name: "", domain: "", aliases: "" },
                    ],
                  })
                }
                type="button"
              >
                <Icon name="plus" />
                Add competitor
              </button>
            </div>
            <div className="competitor-list">
              {draft.competitors.map((competitor, index) => (
                <div className="competitor-row" key={index}>
                  <span className="competitor-index">{index + 1}</span>
                  <label>
                    <span>Name</span>
                    <input
                      aria-label={`Competitor ${index + 1} name`}
                      onChange={(event) => updateCompetitor(index, { name: event.target.value })}
                      placeholder="Competitor name"
                      value={competitor.name}
                    />
                  </label>
                  <label>
                    <span>Domain</span>
                    <input
                      aria-label={`Competitor ${index + 1} domain`}
                      onChange={(event) => updateCompetitor(index, { domain: event.target.value })}
                      placeholder="https://competitor.com"
                      type="url"
                      value={competitor.domain}
                    />
                  </label>
                  <label>
                    <span>Aliases</span>
                    <input
                      aria-label={`Competitor ${index + 1} aliases`}
                      onChange={(event) => updateCompetitor(index, { aliases: event.target.value })}
                      placeholder="Alias, Abbreviation"
                      value={competitor.aliases}
                    />
                  </label>
                  <button
                    aria-label={`Remove competitor ${index + 1}`}
                    className="icon-button danger"
                    onClick={() =>
                      onChange({
                        ...draft,
                        competitors: draft.competitors.filter(
                          (_, competitorIndex) => competitorIndex !== index,
                        ),
                      })
                    }
                    type="button"
                  >
                    <Icon name="trash" size={17} />
                  </button>
                </div>
              ))}
              {!draft.competitors.length ? (
                <div className="compact-empty">No competitors added yet.</div>
              ) : null}
            </div>
          </section>

          <div className="setup-actions">
            <p>
              <Icon name="shield" />
              Provider keys remain server-side. The default demo uses MockProvider.
            </p>
            <button
              className="button button-primary button-large"
              disabled={saving}
              onClick={onCreate}
              type="button"
            >
              {saving ? "Creating project…" : "Create project & continue"}
              <Icon name="arrow" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

interface WorkspaceViewProps {
  project: ProjectResponse;
  providers: ProviderAvailabilityResponse[];
  selectedProviders: string[];
  prompts: string[];
  bundle: AnalysisBundle | null;
  activeCrawl: CrawlJobResponse | null;
  analysisCrawlEvidence: AttachedCrawlEvidence | null;
  crawlPollingError: string;
  crawlRecovering: boolean;
  crawlRecoveryError: string;
  crawlStarting: boolean;
  evidence: DashboardEvidence | null;
  runState: RunState;
  view: View;
  onCrawl: () => void;
  onPromptChange: (prompts: string[]) => void;
  onRetryCrawlPolling: () => void;
  onRetryCrawlRecovery: () => void;
  onToggleProvider: (name: string) => void;
  onRun: () => void;
  onSelectView: (view: View) => void;
}

function WorkspaceView(props: WorkspaceViewProps) {
  const {
    project,
    bundle,
    activeCrawl,
    analysisCrawlEvidence,
    crawlPollingError,
    crawlRecovering,
    crawlRecoveryError,
    crawlStarting,
    evidence,
    runState,
    view,
    prompts,
    providers,
    selectedProviders,
    onCrawl,
    onPromptChange,
    onRetryCrawlPolling,
    onRetryCrawlRecovery,
    onToggleProvider,
    onRun,
    onSelectView,
  } = props;

  if (view !== "overview" && !bundle) {
    return (
      <EmptyAnalysis
        onRun={onRun}
        project={project}
        title={`Run an analysis to populate ${NAV_ITEMS.find((item) => item.view === view)?.label.toLocaleLowerCase()}.`}
      />
    );
  }

  if (view === "queries" && evidence) return <QueryTable evidence={evidence} expanded />;
  if (view === "citations" && evidence) return <CitationBreakdown evidence={evidence} expanded />;
  if (view === "entities" && evidence) return <EntityGapTable evidence={evidence} expanded />;
  if (view === "claims" && evidence) return <ClaimRisk evidence={evidence} expanded />;
  if (view === "recommendations" && evidence)
    return <Recommendations evidence={evidence} expanded />;

  return (
    <div className="overview-page">
      <section className="page-heading overview-heading">
        <div>
          <p className="eyebrow">AI visibility intelligence</p>
          <h1>{project.name} overview</h1>
          <p>
            Evidence calculated across your tracked query-provider matrix and persisted analysis
            rules.
          </p>
        </div>
        {bundle ? (
          <div className="run-meta">
            <span className="run-meta-icon">
              <Icon name="activity" />
            </span>
            <span>
              <small>Latest run</small>
              <strong>
                {bundle.analysis.completed_at ? humanTime(bundle.analysis.completed_at) : "Pending"}
              </strong>
            </span>
            <span className="run-meta-divider" />
            <span>
              <small>Duration</small>
              <strong>
                {bundle.analysis.started_at && bundle.analysis.completed_at
                  ? duration(bundle.analysis.started_at, bundle.analysis.completed_at)
                  : "Pending"}
              </strong>
            </span>
          </div>
        ) : null}
      </section>

      <WebsiteCrawlPanel
        crawl={activeCrawl}
        onCrawl={onCrawl}
        onRetryPolling={onRetryCrawlPolling}
        onRetryRecovery={onRetryCrawlRecovery}
        pollingError={crawlPollingError}
        project={project}
        recovering={crawlRecovering}
        recoveryError={crawlRecoveryError}
        starting={crawlStarting}
      />

      {runState === "running" ? (
        <RunningState prompts={prompts.length} providers={selectedProviders.length} />
      ) : null}
      {bundle && evidence ? (
        <JobStatus
          attachedCrawl={analysisCrawlEvidence}
          bundle={bundle}
          evidence={evidence}
          runState={runState}
        />
      ) : null}

      {!bundle && runState !== "running" ? (
        <div className="launch-grid">
          <PromptEditor prompts={prompts} onChange={onPromptChange} />
          <LaunchControls
            onRun={onRun}
            onToggleProvider={onToggleProvider}
            prompts={prompts}
            project={project}
            providers={providers}
            selectedProviders={selectedProviders}
          />
        </div>
      ) : null}

      {bundle && evidence ? (
        <>
          <MetricCards evidence={evidence} />
          <div className="dashboard-grid dashboard-grid-wide">
            <QueryTable
              evidence={evidence}
              onViewAll={() => onSelectView("queries")}
            />
            <CitationBreakdown
              evidence={evidence}
              onViewAll={() => onSelectView("citations")}
            />
          </div>
          <div className="dashboard-grid">
            <EntityGapTable
              evidence={evidence}
              onViewAll={() => onSelectView("entities")}
            />
            <ClaimRisk evidence={evidence} onViewAll={() => onSelectView("claims")} />
          </div>
          <Recommendations
            evidence={evidence}
            onViewAll={() => onSelectView("recommendations")}
          />
        </>
      ) : null}
    </div>
  );
}

function WebsiteCrawlPanel({
  crawl,
  onCrawl,
  onRetryPolling,
  onRetryRecovery,
  pollingError,
  project,
  recovering,
  recoveryError,
  starting,
}: {
  crawl: CrawlJobResponse | null;
  onCrawl: () => void;
  onRetryPolling: () => void;
  onRetryRecovery: () => void;
  pollingError: string;
  project: ProjectResponse;
  recovering: boolean;
  recoveryError: string;
  starting: boolean;
}) {
  const site = project.site;
  const isDemoSite = site ? isReservedExampleUrl(site.url) : false;
  const isQueued = starting || crawl?.status === "pending";
  const isRunning = crawl?.status === "running";
  const isBusy = isQueued || isRunning;

  return (
    <section className="panel crawl-panel" aria-labelledby="website-evidence-heading">
      <div className="crawl-panel-heading">
        <span className="crawl-panel-icon">
          <Icon name="globe" />
        </span>
        <div>
          <p className="eyebrow">Optional analysis input</p>
          <h2 id="website-evidence-heading">Website evidence</h2>
          <p>Website text from a completed crawl can be used as evidence for claim review.</p>
        </div>
        <span className="crawl-url">
          <small>Configured website</small>
          <strong>{site?.url ?? "No website configured"}</strong>
        </span>
      </div>

      {!site ? (
        <div className="crawl-state crawl-state-unavailable">
          <div>
            <strong>No website is configured for this project</strong>
            <p>Add a site to the project before starting a crawl. Analysis remains available.</p>
          </div>
          <button className="button button-secondary" disabled type="button">
            Crawl unavailable
          </button>
        </div>
      ) : isDemoSite ? (
        <div className="crawl-state crawl-state-unavailable">
          <div>
            <strong>Website crawl unavailable for this demo</strong>
            <p>
              The seeded demo uses a non-routable example domain. Create a project with a public
              website to test crawling.
            </p>
          </div>
          <button className="button button-secondary" disabled type="button">
            Crawl website
          </button>
        </div>
      ) : recovering ? (
        <div className="crawl-state crawl-state-progress" role="status">
          <span className="crawl-activity">
            <Icon name="activity" />
          </span>
          <div>
            <strong>Loading crawl status</strong>
            <p>Checking for the latest crawl saved for this website.</p>
          </div>
          <button className="button button-secondary" disabled type="button">
            Checking status
          </button>
        </div>
      ) : recoveryError ? (
        <div className="crawl-state crawl-state-error" role="alert">
          <span className="crawl-state-icon">
            <Icon name="warning" />
          </span>
          <div>
            <strong>Crawl status could not load</strong>
            <p>{recoveryError}</p>
          </div>
          <button className="button button-secondary" onClick={onRetryRecovery} type="button">
            Retry status check
          </button>
        </div>
      ) : pollingError ? (
        <div className="crawl-state crawl-state-error" role="alert">
          <span className="crawl-state-icon">
            <Icon name="warning" />
          </span>
          <div>
            <strong>{crawl && isBusy ? "Crawl status check paused" : "Crawl could not start"}</strong>
            <p>{pollingError}</p>
          </div>
          {crawl && isBusy ? (
            <button className="button button-secondary" onClick={onRetryPolling} type="button">
              Retry status check
            </button>
          ) : (
            <button className="button button-secondary" onClick={onCrawl} type="button">
              Retry crawl
            </button>
          )}
        </div>
      ) : isQueued ? (
        <div className="crawl-state crawl-state-progress" role="status">
          <span className="crawl-activity">
            <Icon name="activity" />
          </span>
          <div>
            <strong>Crawl queued</strong>
            <p>{starting ? "Submitting the crawl request…" : "Waiting for a crawl worker to begin."}</p>
          </div>
          <button className="button button-secondary" disabled type="button">
            Crawl in progress
          </button>
        </div>
      ) : isRunning ? (
        <div className="crawl-state crawl-state-progress" role="status">
          <span className="crawl-activity">
            <Icon name="activity" />
          </span>
          <div>
            <strong>Crawling website</strong>
            <p>The worker is collecting bounded website text and crawl errors.</p>
          </div>
          <button className="button button-secondary" disabled type="button">
            Crawl in progress
          </button>
        </div>
      ) : crawl?.status === "succeeded" ? (
        <div className="crawl-state crawl-state-success" role="status">
          <span className="crawl-state-icon">
            <Icon name="check" />
          </span>
          <div className="crawl-result-copy">
            <strong>Website crawl succeeded</strong>
            <p>This successful crawl will be attached to the next analysis.</p>
            <div className="crawl-stats">
              <span>
                <small>Pages crawled</small>
                <strong>{crawl.page_count}</strong>
              </span>
              <span>
                <small>Errors</small>
                <strong>{crawl.error_count}</strong>
              </span>
              {crawl.completed_at ? (
                <span>
                  <small>Completed</small>
                  <strong>{humanTime(crawl.completed_at)}</strong>
                </span>
              ) : null}
            </div>
            <details className="crawl-details">
              <summary>Crawl details</summary>
              <code>{crawl.id}</code>
            </details>
          </div>
          <button className="button button-secondary" onClick={onCrawl} type="button">
            Run crawl again
          </button>
        </div>
      ) : crawl?.status === "failed" ? (
        <div className="crawl-state crawl-state-error" role="alert">
          <span className="crawl-state-icon">
            <Icon name="warning" />
          </span>
          <div className="crawl-result-copy">
            <strong>Website crawl failed</strong>
            <p>{crawl.error_message ?? "The crawl worker could not complete this website."}</p>
            <div className="crawl-stats">
              <span>
                <small>Pages crawled</small>
                <strong>{crawl.page_count}</strong>
              </span>
              <span>
                <small>Errors</small>
                <strong>{crawl.error_count}</strong>
              </span>
            </div>
          </div>
          <button className="button button-secondary" onClick={onCrawl} type="button">
            Retry crawl
          </button>
        </div>
      ) : (
        <div className="crawl-state">
          <div>
            <strong>Use website text as optional evidence</strong>
            <p>Start a crawl, wait for success, then run an analysis to attach its page text.</p>
          </div>
          <button className="button button-secondary" onClick={onCrawl} type="button">
            Crawl website
          </button>
        </div>
      )}
    </section>
  );
}

function RunningState({ prompts, providers }: { prompts: number; providers: number }) {
  return (
    <section className="running-panel" aria-live="polite">
      <div className="spinner-ring">
        <Icon name="activity" />
      </div>
      <div>
        <p className="eyebrow">Analysis in progress</p>
        <h2>Evaluating {prompts * providers} provider-query executions</h2>
        <p>
          GeoLens is normalizing answers, extracting citations and entities, calculating metrics,
          and connecting recommendations to observed evidence.
        </p>
      </div>
      <div className="running-steps">
        <span className="complete">
          <Icon name="check" /> Request validated
        </span>
        <span className="active">
          <span className="pulse-dot" /> Provider execution
        </span>
        <span>Evidence calculation</span>
      </div>
    </section>
  );
}

function JobStatus({
  attachedCrawl,
  bundle,
  evidence,
  runState,
}: {
  attachedCrawl: AttachedCrawlEvidence | null;
  bundle: AnalysisBundle;
  evidence: DashboardEvidence;
  runState: RunState;
}) {
  return (
    <section className={`job-status ${runState}`}>
      <span className="job-icon">
        <Icon name={runState === "failed" ? "warning" : runState === "partial" ? "activity" : "check"} />
      </span>
      <div className="job-copy">
        <strong>
          {runState === "partial"
            ? "Analysis completed with partial provider coverage"
            : runState === "failed"
              ? "Analysis completed without eligible answers"
              : "Analysis completed and evidence is ready"}
        </strong>
        <span>
          Run {bundle.analysis.analysis_id.slice(0, 8)} · {evidence.eligibleCount} eligible ·{" "}
          {evidence.failedCount} failed · {bundle.claims.length} claims extracted
        </span>
        <span className="analysis-evidence-summary">
          {attachedCrawl
            ? `Website evidence attached · ${attachedCrawl.pageCount} pages`
            : "Analysis ran without website crawl evidence"}
        </span>
      </div>
      <div className="job-provider-status">
        {uniqueProviders(bundle.analysis.results).map((provider) => (
          <span className={provider.status === "succeeded" ? "ok" : "problem"} key={provider.name}>
            <span className="status-dot" />
            {providerLabel(provider.name)} · {statusLabel(provider.status)}
          </span>
        ))}
      </div>
    </section>
  );
}

function uniqueProviders(results: AnalysisStartResponse["results"]) {
  const seen = new Map<string, AnalysisStartResponse["results"][number]["status"]>();
  for (const result of results) {
    const current = seen.get(result.provider);
    if (!current || current === "succeeded") seen.set(result.provider, result.status);
  }
  return Array.from(seen, ([name, status]) => ({ name, status }));
}

function PromptEditor({
  prompts,
  onChange,
}: {
  prompts: string[];
  onChange: (prompts: string[]) => void;
}) {
  return (
    <section className="panel prompt-editor">
      <div className="panel-heading panel-heading-row">
        <div>
          <p className="eyebrow">Prompt set</p>
          <h2>Queries to analyze</h2>
          <p>Each query runs once against every selected provider.</p>
        </div>
        <span className="count-badge">{prompts.length} queries</span>
      </div>
      <div className="prompt-list">
        {prompts.map((prompt, index) => (
          <div className="prompt-row" key={index}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <textarea
              aria-label={`Query ${index + 1}`}
              onChange={(event) =>
                onChange(
                  prompts.map((current, promptIndex) =>
                    promptIndex === index ? event.target.value : current,
                  ),
                )
              }
              rows={2}
              value={prompt}
            />
            <button
              aria-label={`Remove query ${index + 1}`}
              className="icon-button"
              disabled={prompts.length === 1}
              onClick={() => onChange(prompts.filter((_, promptIndex) => promptIndex !== index))}
              type="button"
            >
              <Icon name="trash" size={16} />
            </button>
          </div>
        ))}
      </div>
      <button
        className="text-button"
        onClick={() => onChange([...prompts, ""])}
        type="button"
      >
        <Icon name="plus" />
        Add query
      </button>
    </section>
  );
}

function LaunchControls({
  project,
  providers,
  selectedProviders,
  prompts,
  onToggleProvider,
  onRun,
}: {
  project: ProjectResponse;
  providers: ProviderAvailabilityResponse[];
  selectedProviders: string[];
  prompts: string[];
  onToggleProvider: (name: string) => void;
  onRun: () => void;
}) {
  const enabledSelected = selectedProviders.length;
  return (
    <section className="panel launch-controls">
      <p className="eyebrow">Launch controls</p>
      <h2>Provider matrix</h2>
      <p>Select the answer engines to compare for this run.</p>
      <div className="provider-list">
        {providers.map((provider) => (
          <label className={`provider-option ${provider.enabled ? "" : "disabled"}`} key={provider.name}>
            <input
              checked={selectedProviders.includes(provider.name)}
              disabled={!provider.enabled}
              onChange={() => onToggleProvider(provider.name)}
              type="checkbox"
            />
            <span className={`provider-logo provider-${provider.name}`}>
              {provider.name.slice(0, 1).toLocaleUpperCase()}
            </span>
            <span>
              <strong>{providerLabel(provider.name)}</strong>
              <small>{provider.model_identifier}</small>
            </span>
            <span className={`availability ${provider.enabled ? "enabled" : ""}`}>
              {provider.enabled ? "Ready" : "Disabled"}
            </span>
            {!provider.enabled ? (
              <span className="provider-reason">{provider.disabled_reason}</span>
            ) : null}
          </label>
        ))}
      </div>
      <div className="run-summary">
        <span>
          <small>Target</small>
          <strong>{project.site ? new URL(project.site.url).hostname : "No domain"}</strong>
        </span>
        <span>
          <small>Execution matrix</small>
          <strong>
            {prompts.filter((prompt) => prompt.trim()).length} × {enabledSelected} ={" "}
            {prompts.filter((prompt) => prompt.trim()).length * enabledSelected}
          </strong>
        </span>
      </div>
      <button className="button button-primary button-full" onClick={onRun} type="button">
        <Icon name="sparkles" />
        Run evidence analysis
      </button>
      <p className="secure-note">
        <Icon name="shield" />
        Credentials are resolved by the backend only.
      </p>
    </section>
  );
}

function EmptyAnalysis({
  project,
  title,
  onRun,
}: {
  project: ProjectResponse;
  title: string;
  onRun: () => void;
}) {
  return (
    <section className="state-screen embedded">
      <span className="state-icon">
        <Icon name="chart" size={27} />
      </span>
      <p className="eyebrow">{project.name}</p>
      <h1>{title}</h1>
      <p>
        The demo prompt set and MockProvider are ready. No generic recommendations are shown before
        evidence has been calculated.
      </p>
      <button className="button button-primary" onClick={onRun} type="button">
        <Icon name="sparkles" />
        Run first analysis
      </button>
    </section>
  );
}

function MetricCards({ evidence }: { evidence: DashboardEvidence }) {
  return (
    <section>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Performance snapshot</p>
          <h2>Overview metrics</h2>
        </div>
        <span className="definition-note">
          <Icon name="database" />
          Eligible answers only
        </span>
      </div>
      <div className="metric-grid">
        {evidence.metrics.map((metric, index) => (
          <article className={`metric-card ${metric.tone}`} key={metric.name}>
            <div className="metric-topline">
              <span className="metric-icon">
                <Icon name={["target", "globe", "chart", "activity", "users"][index] as IconName} />
              </span>
              <span className={`trend-dot ${metric.tone}`} />
            </div>
            <p>{metric.shortName}</p>
            <strong>{displayPercent(metric.value)}</strong>
            <div className="meter" aria-hidden="true">
              <span style={{ width: `${Math.max(3, (metric.value ?? 0) * 100)}%` }} />
            </div>
            <small>{metric.detail}</small>
          </article>
        ))}
      </div>
    </section>
  );
}

function PanelHeader({
  eyebrow,
  title,
  detail,
  onViewAll,
}: {
  eyebrow: string;
  title: string;
  detail: string;
  onViewAll?: () => void;
}) {
  return (
    <div className="panel-heading panel-heading-row">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        <p>{detail}</p>
      </div>
      {onViewAll ? (
        <button className="text-button" onClick={onViewAll} type="button">
          View all <Icon name="arrow" />
        </button>
      ) : null}
    </div>
  );
}

function QueryTable({
  evidence,
  expanded = false,
  onViewAll,
}: {
  evidence: DashboardEvidence;
  expanded?: boolean;
  onViewAll?: () => void;
}) {
  const rows = expanded ? evidence.comparisons : evidence.comparisons.slice(0, 6);
  return (
    <section className={`panel data-panel query-panel ${expanded ? "full-view" : ""}`}>
      <PanelHeader
        detail="One auditable outcome for every provider and query."
        eyebrow="Answer-engine comparison"
        onViewAll={onViewAll}
        title="Provider by query"
      />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Query</th>
              <th>Provider</th>
              <th>Status</th>
              <th>Brand</th>
              <th>Target cited</th>
              <th>Domains</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <span className="query-cell" title={row.query}>
                    {row.query}
                  </span>
                </td>
                <td>
                  <span className="provider-cell">
                    <span className={`provider-logo provider-${row.provider}`}>
                      {row.provider.slice(0, 1).toLocaleUpperCase()}
                    </span>
                    <span>
                      <strong>{providerLabel(row.provider)}</strong>
                      <small>{Math.round(row.latencyMs)}ms</small>
                    </span>
                  </span>
                </td>
                <td>
                  <span className={`status-badge status-${row.status}`}>
                    <span className="status-dot" />
                    {statusLabel(row.status)}
                  </span>
                </td>
                <td>
                  <BooleanCell value={row.targetMentioned} />
                </td>
                <td>
                  <BooleanCell value={row.targetCited} />
                </td>
                <td>
                  <span className="domain-count">
                    {row.citationDomains.length}
                    <small>{row.citationDomains.slice(0, 2).join(", ") || "—"}</small>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length ? <CompactEmpty label="No provider executions were returned." /> : null}
    </section>
  );
}

function BooleanCell({ value }: { value: boolean }) {
  return value ? (
    <span className="boolean yes">
      <Icon name="check" size={14} /> Yes
    </span>
  ) : (
    <span className="boolean no">
      <Icon name="close" size={14} /> No
    </span>
  );
}

function CitationBreakdown({
  evidence,
  expanded = false,
  onViewAll,
}: {
  evidence: DashboardEvidence;
  expanded?: boolean;
  onViewAll?: () => void;
}) {
  const domains = expanded ? evidence.citationDomains : evidence.citationDomains.slice(0, 6);
  const max = Math.max(...domains.map((domain) => domain.citations), 1);
  return (
    <section className={`panel data-panel citation-panel ${expanded ? "full-view" : ""}`}>
      <PanelHeader
        detail="Normalized hostnames in eligible provider answers."
        eyebrow="Source intelligence"
        onViewAll={onViewAll}
        title="Citation-domain breakdown"
      />
      <div className="domain-list">
        {domains.map((domain, index) => (
          <div className="domain-row" key={domain.domain}>
            <span className="domain-rank">{String(index + 1).padStart(2, "0")}</span>
            <span className={`domain-favicon ${domain.isTarget ? "target" : ""}`}>
              {domain.domain[0].toLocaleUpperCase()}
            </span>
            <div className="domain-main">
              <div>
                <strong>{domain.domain}</strong>
                {domain.isTarget ? <span className="target-label">Target</span> : null}
                <small>
                  {domain.queryCount} quer{domain.queryCount === 1 ? "y" : "ies"} ·{" "}
                  {domain.providers.map(providerLabel).join(", ")}
                </small>
              </div>
              <div className="domain-bar">
                <span style={{ width: `${(domain.citations / max) * 100}%` }} />
              </div>
            </div>
            <span className="domain-stat">
              <strong>{domain.citations}</strong>
              <small>{Math.round(domain.share * 100)}% share</small>
            </span>
          </div>
        ))}
        {!domains.length ? <CompactEmpty label="No normalized citations in eligible answers." /> : null}
      </div>
    </section>
  );
}

function EntityGapTable({
  evidence,
  expanded = false,
  onViewAll,
}: {
  evidence: DashboardEvidence;
  expanded?: boolean;
  onViewAll?: () => void;
}) {
  return (
    <section className={`panel data-panel entity-panel ${expanded ? "full-view" : ""}`}>
      <PanelHeader
        detail="Where competitors appear without the target or lead its first mention."
        eyebrow="Competitive entities"
        onViewAll={onViewAll}
        title="Entity-gap table"
      />
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Tracked entity</th>
              <th>Mentioned queries</th>
              <th>Target absent</th>
              <th>Leads target</th>
              <th>Gap</th>
            </tr>
          </thead>
          <tbody>
            {evidence.entityGaps.map((gap) => (
              <tr key={gap.entity}>
                <td>
                  <span className="entity-name">
                    <span>{gap.entity.slice(0, 1)}</span>
                    <strong>{gap.entity}</strong>
                  </span>
                </td>
                <td>{gap.mentionQueries}</td>
                <td>{gap.targetMissingQueries}</td>
                <td>{gap.leadsTargetQueries}</td>
                <td>
                  <span
                    className={`gap-badge ${
                      gap.targetMissingQueries ? "attention" : "clear"
                    }`}
                  >
                    {gap.targetMissingQueries ? "Opportunity" : "Covered"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!evidence.entityGaps.length ? (
        <CompactEmpty label="Add competitors in project setup to calculate entity gaps." />
      ) : null}
      {expanded
        ? evidence.entityGaps
            .filter((gap) => gap.affectedQueries.length)
            .map((gap) => (
              <div className="entity-evidence" key={`${gap.entity}-evidence`}>
                <strong>{gap.entity} affected queries</strong>
                <div className="chip-list">
                  {gap.affectedQueries.map((query) => (
                    <span className="query-chip" key={query}>
                      {query}
                    </span>
                  ))}
                </div>
              </div>
            ))
        : null}
    </section>
  );
}

function ClaimRisk({
  evidence,
  expanded = false,
  onViewAll,
}: {
  evidence: DashboardEvidence;
  expanded?: boolean;
  onViewAll?: () => void;
}) {
  const claims = expanded ? evidence.claims : evidence.claims.slice(0, 3);
  const classifiedCount = evidence.claims.filter(
    (claim) => claim.classifier !== "not_configured",
  ).length;
  const riskMetric = evidence.metrics.find((metric) => metric.name === "Claim-support risk");
  return (
    <section className={`panel data-panel claim-panel ${expanded ? "full-view" : ""}`}>
      <PanelHeader
        detail={
          classifiedCount
            ? "Model-assisted prioritization grounded in stored evidence excerpts."
            : "Extracted claims are shown for review; no model classifier was requested."
        }
        eyebrow="Evidence review"
        onViewAll={onViewAll}
        title="Claim-risk drilldown"
      />
      <div className="risk-summary">
        <div className="risk-gauge">
          <span>
            {riskMetric?.value !== null && riskMetric?.value !== undefined
              ? displayPercent(riskMetric.value)
              : evidence.claims.length
                ? "Review"
                : "—"}
          </span>
        </div>
        <div>
          <strong>
            {classifiedCount
              ? `${classifiedCount} model-classified claims`
              : `${evidence.claims.length} extracted claims · classifier not configured`}
          </strong>
          <p>
            {classifiedCount
              ? "This is not objective truth. Risk depends on available evidence and classifier judgment."
              : "No claim-support risk score is calculated until a classifier is explicitly selected."}
          </p>
        </div>
      </div>
      <div className="claim-list">
        {claims.map((claim) => (
          <details className="claim-item" key={claim.id} open={expanded}>
            <summary>
              <span className={`claim-classification ${claim.classification}`}>
                {claim.classifier === "not_configured"
                  ? "Not classified"
                  : statusLabel(claim.classification)}
              </span>
              <span className="claim-text">{claim.claim_text}</span>
              <span className="claim-confidence">
                {claim.classifier === "not_configured"
                  ? "No score"
                  : `${Math.round(claim.confidence * 100)}%`}
                <Icon name="chevron" size={15} />
              </span>
            </summary>
            <div className="claim-details">
              <div className="claim-context">
                <span>
                  <small>Query</small>
                  <strong>{claim.query}</strong>
                </span>
                <span>
                  <small>Provider / classifier</small>
                  <strong>
                    {providerLabel(claim.provider)} · {claim.model_identifier ?? claim.classifier}
                  </strong>
                </span>
              </div>
              <p>{claim.explanation}</p>
              <strong className="evidence-title">Evidence</strong>
              {claim.evidence.length ? (
                claim.evidence.map((item) => {
                  const externalUrl = safeExternalUrl(item.url);
                  return (
                    <div className="evidence-excerpt" key={item.id}>
                      <span>
                        <Icon name="file" />
                      </span>
                      <div>
                        <strong>{item.source_reference}</strong>
                        <p>{item.excerpt}</p>
                        <small>{Math.round(item.relevance_score * 100)}% retrieval relevance</small>
                      </div>
                      {externalUrl ? (
                        <a
                          aria-label="Open evidence source"
                          href={externalUrl}
                          rel="noreferrer"
                          target="_blank"
                        >
                          <Icon name="external" />
                        </a>
                      ) : null}
                    </div>
                  );
                })
              ) : (
                <p className="no-evidence">No relevant stored evidence was retrieved.</p>
              )}
            </div>
          </details>
        ))}
        {!claims.length ? (
          <CompactEmpty label="No factual claims were segmented from this run." />
        ) : null}
      </div>
    </section>
  );
}

function Recommendations({
  evidence,
  expanded = false,
  onViewAll,
}: {
  evidence: DashboardEvidence;
  expanded?: boolean;
  onViewAll?: () => void;
}) {
  const recommendations = expanded
    ? evidence.recommendations
    : evidence.recommendations.slice(0, 3);
  return (
    <section className={`panel recommendation-panel ${expanded ? "full-view" : ""}`}>
      <PanelHeader
        detail="Ranked from measured provider, query, citation, entity, and claim evidence."
        eyebrow="Evidence-derived action plan"
        onViewAll={onViewAll}
        title="Ranked GEO recommendations"
      />
      <div className="recommendation-list">
        {recommendations.map((recommendation) => (
          <article className="recommendation-card" key={recommendation.id}>
            <div className="recommendation-rank">
              <span>{String(recommendation.rank).padStart(2, "0")}</span>
              <small>Rank</small>
            </div>
            <div className="recommendation-body">
              <div className="recommendation-tags">
                <span className={`priority priority-${recommendation.priority.toLocaleLowerCase()}`}>
                  {recommendation.priority} priority
                </span>
                <span className="confidence">
                  {recommendation.confidence} confidence
                </span>
              </div>
              <div className="recommendation-grid">
                <div>
                  <small>Observed problem</small>
                  <h3>{recommendation.observedProblem}</h3>
                </div>
                <div>
                  <small>Recommended action</small>
                  <p>{recommendation.recommendedAction}</p>
                </div>
              </div>
              <div className="recommendation-evidence">
                <div>
                  <small>Affected queries</small>
                  <div className="chip-list">
                    {recommendation.affectedQueries.map((query) => (
                      <span className="query-chip" key={query}>
                        {query}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <small>Provider evidence</small>
                  <ul>
                    {recommendation.providerEvidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
              <div className="expected-metric">
                <span className="metric-target-icon">
                  <Icon name="target" />
                </span>
                <span>
                  <small>Expected metric</small>
                  <strong>{recommendation.expectedMetric.name}</strong>
                </span>
                <span className="baseline">
                  <small>Current</small>
                  <strong>{recommendation.expectedMetric.baseline}</strong>
                </span>
                <Icon name="arrow" />
                <span className="target-value">
                  <small>Target</small>
                  <strong>{recommendation.expectedMetric.target}</strong>
                </span>
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function CompactEmpty({ label }: { label: string }) {
  return (
    <div className="compact-empty">
      <Icon name="database" />
      {label}
    </div>
  );
}
