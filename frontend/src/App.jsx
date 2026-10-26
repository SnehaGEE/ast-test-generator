import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  Activity,
  Braces,
  CheckCircle2,
  ChevronDown,
  CircleAlert,
  Code2,
  FileCode2,
  FlaskConical,
  FolderOpen,
  Gauge,
  Info,
  Lightbulb,
  Play,
  Settings2,
  Terminal,
  XCircle,
} from "lucide-react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";
const API_URL = `${API_BASE}/api/run`;
const HEALTH_URL = `${API_BASE}/api/health`;
const HEALTH_INTERVAL_MS = 15000;
const REQUEST_TIMEOUT_MS = 180000;
const MIN_CASES = 1;
const MAX_CASES = 100;

const EXAMPLES = {
  python: `age = int(input("Enter age: "))

if age >= 18:
    print("Adult")
else:
    print("Minor")
`,
  java: `public class AgeCheck {
    public static void main(String[] args) {
        int age = Integer.parseInt(
            System.getProperty("age", "0")
        );

        if (age >= 18) {
            System.out.println("Adult");
        } else {
            System.out.println("Minor");
        }
    }
}`,
  c: `#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        return 1;
    }

    int age = atoi(argv[1]);

    if (age >= 18) {
        printf("Adult\\n");
    } else {
        printf("Minor\\n");
    }

    return 0;
}`,
};

const LANGUAGES = [
  { value: "python", label: "Python", extension: "main.py" },
  { value: "java", label: "Java", extension: "AgeCheck.java" },
  { value: "c", label: "C", extension: "main.c" },
];

const CATEGORY_LABELS = {
  targeted: "Boundary",
  invalid: "Invalid input",
  fuzz: "Fuzz",
};

// ---- helpers (kept free of React so they can be tested on their own) ----

function describeStatus(test) {
  if (test.executed) {
    return { label: "Executed", tone: "success" };
  }

  const errorText = test.error || "";
  const lowered = errorText.toLowerCase();

  if (lowered.includes("timed out")) {
    return { label: "Timed out", tone: "warning" };
  }

  const exitMatch = /exited with code (\d+)/i.exec(errorText);
  if (exitMatch) {
    return { label: `Exit code ${exitMatch[1]}`, tone: "warning" };
  }

  if (lowered.includes("valueerror") || lowered.includes("typeerror")) {
    return { label: "Input rejected", tone: "warning" };
  }

  return { label: "Error", tone: "failure" };
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? CATEGORY_LABELS.targeted;
}

function formatInputs(inputs) {
  const text = JSON.stringify(inputs ?? {});
  return text.length > 120 ? `${text.slice(0, 117)}...` : text;
}

function parseMaxCases(text) {
  const trimmed = String(text).trim();
  if (!/^\d+$/.test(trimmed)) {
    return null;
  }
  const value = Number(trimmed);
  return value >= MIN_CASES && value <= MAX_CASES ? value : null;
}

function describeUnsupported(unsupported) {
  const parts = [];
  for (const item of unsupported ?? []) {
    const text = `${item.construct} (line ${item.line})`;
    if (!parts.includes(text)) {
      parts.push(text);
    }
  }
  return parts.join("; ");
}

function errorDetailText(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) {
    return detail;
  }
  if (detail) {
    return JSON.stringify(detail);
  }
  return `The analysis request failed (HTTP ${status}).`;
}

// ---- component ----

function App() {
  const [language, setLanguage] = useState("python");
  const [source, setSource] = useState(EXAMPLES.python);
  const [maxCasesText, setMaxCasesText] = useState("20");
  const [invalidTests, setInvalidTests] = useState(true);
  const [fuzzTests, setFuzzTests] = useState(true);
  const [activeTab, setActiveTab] = useState("tests");
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [apiError, setApiError] = useState("");
  const [backendUp, setBackendUp] = useState(null);
  const abortRef = useRef(null);
  const resultsRef = useRef(null);

  useEffect(() => {
    let active = true;

    async function checkHealth() {
      try {
        const response = await fetch(HEALTH_URL);
        if (active) setBackendUp(response.ok);
      } catch {
        if (active) setBackendUp(false);
      }
    }

    checkHealth();
    const timer = setInterval(checkHealth, HEALTH_INTERVAL_MS);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  function showTab(tab) {
    setActiveTab(tab);
    resultsRef.current?.scrollIntoView({ behavior: "smooth" });
  }

  const maxCases = parseMaxCases(maxCasesText);
  const maxCasesValid = maxCases !== null;

  const selectedLanguage = LANGUAGES.find(
    (item) => item.value === language
  );

  function changeLanguage(nextLanguage) {
    setLanguage(nextLanguage);
    setSource(EXAMPLES[nextLanguage]);
    setResults(null);
    setApiError("");
  }

  function cancelRun() {
    abortRef.current?.abort();
  }

  async function runAnalysis() {
    if (running) {
      return;
    }

    if (!source.trim()) {
      setApiError("Enter source code before running the analysis.");
      return;
    }

    if (!maxCasesValid) {
      setApiError(
        `Maximum test cases must be a whole number from ${MIN_CASES} to ${MAX_CASES}.`
      );
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;

    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);

    setRunning(true);
    setApiError("");
    setResults(null);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_code: source,
          language,
          max_cases: maxCases,
          include_invalid_inputs: language === "python" && invalidTests,
          include_fuzz_inputs: language === "python" && fuzzTests,
        }),
        signal: controller.signal,
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(errorDetailText(data, response.status));
      }

      if (!data) {
        throw new Error("The backend returned an unreadable response.");
      }

      setResults(data);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setApiError(
          timedOut
            ? "The analysis took longer than 3 minutes, so the browser stopped waiting. The backend may still be finishing it."
            : "Analysis cancelled. The backend may still be finishing the request."
        );
      } else if (error instanceof TypeError) {
        setApiError(
          "Cannot reach the Python backend. Make sure the backend is running."
        );
      } else {
        setApiError(
          error instanceof Error
            ? error.message
            : "An unexpected error occurred."
        );
      }
    } finally {
      clearTimeout(timer);
      abortRef.current = null;
      setRunning(false);
    }
  }

  const testResults = results?.results ?? [];
  const totalTests = results?.total_tests ?? 0;
  const executedTests = results?.successful_executions ?? 0;
  const failedTests = results?.failed_executions ?? 0;
  const coverage = results?.coverage ?? {};
  const coveragePercent = coverage.branch_coverage_percent;
  const branches = coverage.branches ?? [];
  const unsupportedText = describeUnsupported(coverage.unsupported);
  const suggestions = coverage.suggestions ?? [];

  // Prefer a useful backend message when no test cases are generated.
  const noTestsMessage =
    results?.message ||
    "No test cases were generated for this program.";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">
            <Braces size={22} />
          </div>
          <span>BranchLab</span>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>

        <button
          className="nav-item active"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        >
          <Code2 size={18} />
          <span>Code workspace</span>
        </button>

        <button className="nav-item" onClick={() => showTab("tests")}>
          <FlaskConical size={18} />
          <span>Test results</span>
        </button>

        <button className="nav-item" onClick={() => showTab("coverage")}>
          <Gauge size={18} />
          <span>Coverage report</span>
        </button>

        <div className="sidebar-bottom">
          <div className="backend-status">
            <span
              className={`status-dot ${
                backendUp === false ? "offline" : backendUp ? "" : "checking"
              }`}
            />
            <div>
              <strong>
                {backendUp === null
                  ? "Checking backend..."
                  : backendUp
                    ? "Backend connected"
                    : "Backend offline"}
              </strong>
              <small>{API_BASE.replace(/^https?:\/\//, "")}</small>
            </div>
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs">
            <FolderOpen size={16} />
            <span>Projects</span>
            <span className="crumb-divider">/</span>
            <strong>AST Test Generator</strong>
          </div>

          <div className="topbar-right">
            <span className="project-badge">COMPILER DESIGN</span>
          </div>
        </header>

        <section className="page-heading">
          <div>
            <div className="eyebrow">
              SOURCE ANALYSIS / TEST GENERATION
            </div>
            <h1>Code workspace</h1>
            <p>
              Generate targeted test cases and inspect program behaviour.
            </p>
          </div>

          <div className="heading-actions">
            {running && (
              <button className="cancel-button" onClick={cancelRun}>
                <XCircle size={16} />
                Cancel
              </button>
            )}
            <button
              className="run-button heading-run"
              onClick={runAnalysis}
              disabled={running || !maxCasesValid}
            >
              <Play size={16} fill="currentColor" />
              {running ? "Running analysis..." : "Run analysis"}
            </button>
          </div>
        </section>

        <section className="workspace-grid">
          <div className="editor-panel panel">
            <div className="panel-titlebar">
              <div className="file-tab">
                <FileCode2 size={16} />
                <span>{selectedLanguage.extension}</span>
                <span className="unsaved-dot" />
              </div>

              <div className="editor-tools">
                <span>UTF-8</span>
                <span>Spaces: 4</span>
              </div>
            </div>

            <div className="editor-controls">
              <label htmlFor="language-select">Language</label>
              <div className="select-wrap">
                <select
                  id="language-select"
                  value={language}
                  onChange={(event) => changeLanguage(event.target.value)}
                >
                  {LANGUAGES.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={15} />
              </div>
            </div>

            <div className="monaco-wrap">
              <Editor
                height="420px"
                language={language}
                value={source}
                onChange={(value) => setSource(value ?? "")}
                theme="vs"
                options={{
                  minimap: { enabled: false },
                  fontSize: 13,
                  lineHeight: 22,
                  fontFamily: "'Cascadia Code', Consolas, monospace",
                  lineNumbers: "on",
                  roundedSelection: false,
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 4,
                  padding: { top: 16, bottom: 16 },
                  wordWrap: "on",
                  renderLineHighlight: "line",
                  overviewRulerBorder: false,
                  hideCursorInOverviewRuler: true,
                  scrollbar: {
                    verticalScrollbarSize: 9,
                    horizontalScrollbarSize: 9,
                  },
                }}
              />
            </div>

            <div className="editor-footer">
              <span>
                <CircleAlert size={14} />
                Edit source before running
              </span>
              <span>{source.split("\n").length} lines</span>
            </div>
          </div>

          <aside className="config-panel panel">
            <div className="panel-heading">
              <div className="panel-icon">
                <Settings2 size={18} />
              </div>
              <div>
                <h2>Test configuration</h2>
                <p>Choose how tests are generated.</p>
              </div>
            </div>

            <div className="form-field">
              <label htmlFor="max-cases">Maximum test cases</label>
              <input
                id="max-cases"
                type="number"
                min={MIN_CASES}
                max={MAX_CASES}
                step="1"
                inputMode="numeric"
                value={maxCasesText}
                aria-invalid={!maxCasesValid}
                onChange={(event) => setMaxCasesText(event.target.value)}
              />
              {maxCasesValid ? (
                <small>Between 1 and 100 test cases</small>
              ) : (
                <small className="field-error">
                  Enter a whole number from 1 to 100
                </small>
              )}
            </div>

            <div className="config-divider" />

            <div className="strategy-heading">
              <h3>Testing strategies</h3>
              <span>PYTHON ONLY</span>
            </div>

            <label
              className={`strategy-option ${
                language !== "python" ? "disabled" : ""
              }`}
            >
              <input
                type="checkbox"
                checked={invalidTests}
                disabled={language !== "python"}
                onChange={(event) =>
                  setInvalidTests(event.target.checked)
                }
              />
              <span className="custom-check" />
              <span className="strategy-copy">
                <strong>Invalid-input tests</strong>
                <small>Try malformed and unexpected values</small>
              </span>
            </label>

            <label
              className={`strategy-option ${
                language !== "python" ? "disabled" : ""
              }`}
            >
              <input
                type="checkbox"
                checked={fuzzTests}
                disabled={language !== "python"}
                onChange={(event) =>
                  setFuzzTests(event.target.checked)
                }
              />
              <span className="custom-check" />
              <span className="strategy-copy">
                <strong>Fuzz testing</strong>
                <small>Explore unusual input combinations</small>
              </span>
            </label>

            <div className="config-divider" />

            <div className="strategy-note">
              <Activity size={17} />
              <p>
                Targeted tests are generated from supported conditions
                found during AST analysis. Each extra strategy you turn
                on reserves about 20% of the maximum.
              </p>
            </div>

            <button
              className="run-button config-run"
              onClick={runAnalysis}
              disabled={running || !maxCasesValid}
            >
              <Play size={16} fill="currentColor" />
              {running ? "Running..." : "Generate & Run"}
            </button>

            <div className="config-footnote">
              <span className="status-dot" />
              Runs against your local project backend
            </div>
          </aside>
        </section>

        {apiError && (
          <div className="error-banner">
            <XCircle size={18} />
            <span>{apiError}</span>
          </div>
        )}

        <section className="results-section" ref={resultsRef}>
          <div className="results-heading">
            <div>
              <div className="eyebrow">ANALYSIS REPORT</div>
              <h2>Execution results</h2>
            </div>
            {results && (
              <span className="results-ready">Run complete</span>
            )}
          </div>

          <div className="metrics-grid">
            <MetricCard
              label="Total test cases"
              value={results ? totalTests : "—"}
              icon={<FlaskConical size={18} />}
            />
            <MetricCard
              label="Successful executions"
              value={results ? executedTests : "—"}
              icon={<CheckCircle2 size={18} />}
            />
            <MetricCard
              label="Execution errors"
              value={results ? failedTests : "—"}
              icon={<CircleAlert size={18} />}
            />
          </div>

          {results?.message && testResults.length > 0 && (
            <div className="info-banner">
              <Info size={16} />
              <span>{results.message}</span>
            </div>
          )}

          <div className="results-panel panel">
            <div className="results-tabs">
              <button
                className={
                  activeTab === "tests"
                    ? "result-tab selected"
                    : "result-tab"
                }
                onClick={() => setActiveTab("tests")}
              >
                <FlaskConical size={16} /> Generated tests
              </button>

              <button
                className={
                  activeTab === "output"
                    ? "result-tab selected"
                    : "result-tab"
                }
                onClick={() => setActiveTab("output")}
              >
                <Terminal size={16} /> Execution output
              </button>

              <button
                className={
                  activeTab === "coverage"
                    ? "result-tab selected"
                    : "result-tab"
                }
                onClick={() => setActiveTab("coverage")}
              >
                <Gauge size={16} /> Coverage
              </button>
            </div>

            <div className="results-content">
              {activeTab === "tests" && (
                results ? (
                  testResults.length > 0 ? (
                    <div className="table-scroll">
                      <table className="results-table">
                        <thead>
                          <tr>
                            <th>Test</th>
                            <th>Type</th>
                            <th>Input values</th>
                            <th>Status</th>
                            <th>Output</th>
                            <th>Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {testResults.map((test, index) => {
                            const status = describeStatus(test);
                            return (
                              <tr key={index}>
                                <td className="test-number">
                                  {String(index + 1).padStart(2, "0")}
                                </td>
                                <td>
                                  <span className="type-pill">
                                    {categoryLabel(test.category)}
                                  </span>
                                </td>
                                <td>
                                  <code
                                    title={JSON.stringify(test.inputs)}
                                  >
                                    {formatInputs(test.inputs)}
                                  </code>
                                </td>
                                <td>
                                  <span
                                    className={`status-pill ${status.tone}`}
                                  >
                                    {status.label}
                                  </span>
                                </td>
                                <td className="output-cell">
                                  {test.output?.trim() || "—"}
                                </td>
                                <td className="error-cell">
                                  {test.error || "—"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState message={noTestsMessage} />
                  )
                ) : (
                  <EmptyState message="Run your source code to see generated tests here." />
                )
              )}

              {activeTab === "output" && (
                results ? (
                  <div className="output-list">
                    {testResults.map((test, index) => {
                      const status = describeStatus(test);
                      return (
                        <div className="output-entry" key={index}>
                          <div className="output-entry-heading">
                            <span>
                              Test {index + 1} ·{" "}
                              {categoryLabel(test.category)}
                            </span>
                            <span
                              className={
                                status.tone === "success"
                                  ? "mini-status success-text"
                                  : status.tone === "warning"
                                    ? "mini-status warning-text"
                                    : "mini-status error-text"
                              }
                            >
                              {status.label}
                            </span>
                          </div>
                          <pre>{test.output?.trim() || "(no output)"}</pre>
                          {test.error && (
                            <pre className="error-pre">{test.error}</pre>
                          )}
                        </div>
                      );
                    })}
                    {testResults.length === 0 && (
                      <EmptyState
                        message={
                          results.message ||
                          "There is no execution output because no tests were generated."
                        }
                      />
                    )}
                  </div>
                ) : (
                  <EmptyState message="Execution output will appear here after a run." />
                )
              )}

              {activeTab === "coverage" && (
                results ? (
                  coveragePercent != null ? (
                    <div className="coverage-view">
                      <div className="coverage-number">
                        {Number(coveragePercent).toFixed(1)}%
                      </div>
                      <div className="coverage-track">
                        <div
                          className="coverage-fill"
                          style={{
                            width: `${Math.max(
                              0,
                              Math.min(100, Number(coveragePercent))
                            )}%`,
                          }}
                        />
                      </div>
                      <p>
                        Each tracked if/while condition has two outcomes,
                        true and false. The percentage is the share of
                        those outcomes the generated tests actually
                        produced when the program ran. The table shows
                        exactly which ones were seen.
                      </p>

                      {branches.length > 0 && (
                        <div className="table-scroll coverage-table">
                          <table className="results-table">
                            <thead>
                              <tr>
                                <th>Line</th>
                                <th>Kind</th>
                                <th>True outcome</th>
                                <th>False outcome</th>
                              </tr>
                            </thead>
                            <tbody>
                              {branches.map((branch, index) => (
                                <tr key={index}>
                                  <td className="test-number">
                                    {branch.line}
                                  </td>
                                  <td>{branch.kind ?? "if"}</td>
                                  <td>
                                    <OutcomeFlag
                                      seen={branch.true_covered}
                                    />
                                  </td>
                                  <td>
                                    <OutcomeFlag
                                      seen={branch.false_covered}
                                    />
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {suggestions.length > 0 && (
                        <div className="suggestions">
                          <h3>
                            <Lightbulb size={16} /> Suggested tests for
                            missing outcomes
                          </h3>
                          <p>
                            Each suggestion was run once. "Verified" means
                            it really produced the missing outcome; an
                            unverified one needs other inputs changed too,
                            for example to reach a nested condition.
                          </p>
                          <div className="table-scroll">
                            <table className="results-table">
                              <thead>
                                <tr>
                                  <th>Line</th>
                                  <th>Missing outcome</th>
                                  <th>Suggested inputs</th>
                                  <th>Check</th>
                                </tr>
                              </thead>
                              <tbody>
                                {suggestions.map((item, index) => (
                                  <tr key={index}>
                                    <td className="test-number">
                                      {item.line}
                                    </td>
                                    <td>{item.target_outcome}</td>
                                    <td>
                                      <code>{formatInputs(item.inputs)}</code>
                                    </td>
                                    <td>
                                      <span
                                        className={
                                          item.verified
                                            ? "outcome-flag seen"
                                            : "outcome-flag missed"
                                        }
                                      >
                                        {item.verified
                                          ? "✓ verified"
                                          : "✗ not reached"}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {unsupportedText && (
                        <div className="warn-note">
                          <CircleAlert size={15} />
                          <span>
                            Not tracked by branch coverage:{" "}
                            {unsupportedText}.
                          </span>
                        </div>
                      )}
                    </div>
                  ) : (
                    <EmptyState
                      message={
                        coverage.error ||
                        results.message ||
                        "Coverage is unavailable for this program."
                      }
                    />
                  )
                ) : (
                  <EmptyState message="Run an analysis to view coverage information." />
                )
              )}
            </div>
          </div>
        </section>

        <footer className="app-footer">
          <span>BranchLab · Compiler Design Project</span>
          <span>Local development environment</span>
        </footer>
      </main>
    </div>
  );
}

function OutcomeFlag({ seen }) {
  return (
    <span className={seen ? "outcome-flag seen" : "outcome-flag missed"}>
      {seen ? "✓ seen" : "✗ not seen"}
    </span>
  );
}

function MetricCard({ label, value, icon }) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div>
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
      </div>
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Code2 size={22} />
      </div>
      <p>{message}</p>
    </div>
  );
}

export default App;