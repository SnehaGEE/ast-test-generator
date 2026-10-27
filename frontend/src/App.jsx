import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  CheckCircle2,
  CircleAlert,
  Code2,
  FileCode2,
  FlaskConical,
  Gauge,
  GitBranch,
  Info,
  Lightbulb,
  LoaderCircle,
  Moon,
  Play,
  SlidersHorizontal,
  Sun,
  Terminal,
  XCircle,
} from "lucide-react";
import "./App.css";

// In development the API runs separately; a production build is served by the API itself.
const API_BASE =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
const API_URL = `${API_BASE}/api/run`;
const HEALTH_URL = `${API_BASE}/api/health`;
const HEALTH_INTERVAL_MS = 15000;
const THEME_STORAGE_KEY = "branchlab-theme";
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
  java: `import java.util.Scanner;

public class AgeCheck {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int age = in.nextInt();

        if (age >= 18) {
            System.out.println("Adult");
        } else {
            System.out.println("Minor");
        }
    }
}`,
  c: `#include <stdio.h>

int main(void) {
    int age;

    if (scanf("%d", &age) != 1) {
        printf("Please enter a number\\n");
        return 1;
    }

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

// Monaco's vs-dark with the page's indigo surface instead of charcoal.
function defineEditorThemes(monaco) {
  monaco.editor.defineTheme("branchlab-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [],
    colors: {
      "editor.background": "#181b31",
      "editor.lineHighlightBackground": "#20243f",
      "editor.lineHighlightBorder": "#20243f",
      "editorLineNumber.foreground": "#5d6390",
      "editorLineNumber.activeForeground": "#c9d0ff",
      "editorGutter.background": "#181b31",
    },
  });
}

const RESULT_TABS = [
  ["tests", "Generated tests", FlaskConical],
  ["output", "Execution output", Terminal],
  ["coverage", "Coverage", Gauge],
];

const CATEGORY_TONES = {
  targeted: "blue",
  invalid: "amber",
  fuzz: "violet",
};

// Chip colour for each describeStatus tone.
const STATUS_TONES = {
  success: "green",
  warning: "amber",
  failure: "rose",
};

function categoryTone(category) {
  return CATEGORY_TONES[category] ?? CATEGORY_TONES.targeted;
}

function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? CATEGORY_LABELS.targeted;
}

function outputLines(output) {
  return (output ?? "").split("\n").map((line) => line.trim()).filter(Boolean);
}

// Lines every test printed (a banner, a menu, a fixed prompt) say nothing
// about one test, so the table hides them and shows what differs.
function sharedLines(tests) {
  const outputs = tests.map((test) => new Set(outputLines(test.output)));
  if (outputs.length < 2) return new Set();
  return new Set([...outputs[0]].filter((line) => outputs.every((set) => set.has(line))));
}

function outputSummary(output, shared) {
  const lines = outputLines(output);
  const distinct = lines.filter((line) => !shared.has(line));
  return (distinct.length ? distinct : lines.slice(-2)).join(" · ");
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
  // index.html already chose the starting theme; read it back here.
  const [theme, setTheme] = useState(
    () => document.documentElement.dataset.theme || "light"
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Storage can be blocked; the theme still applies for this visit.
    }
  }, [theme]);
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
          include_invalid_inputs: invalidTests,
          include_fuzz_inputs: fuzzTests,
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
      setActiveTab("tests");
      requestAnimationFrame(() =>
        resultsRef.current?.scrollIntoView({ behavior: "smooth" })
      );
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        setApiError(
          timedOut
            ? "The analysis took longer than 3 minutes, so the browser stopped waiting. The backend may still be finishing it."
            : "Analysis cancelled. The backend may still be finishing the request."
        );
      } else if (error instanceof TypeError) {
        setApiError(
          "Cannot reach the backend. Make sure it is running (python -m uvicorn api:app)."
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
  const statementPercent = coverage.statement_coverage_percent;
  const statements = coverage.statements;
  const lineCount = source.split("\n").length;
  const commonOutput = sharedLines(testResults);

  // Prefer a useful backend message when no test cases are generated.
  const noTestsMessage =
    results?.message ||
    "No test cases were generated for this program.";

  const backendStatus =
    backendUp === null
      ? { tone: "checking", text: "Checking backend..." }
      : backendUp
        ? { tone: "online", text: "Backend connected" }
        : { tone: "offline", text: "Backend offline" };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <GitBranch size={18} />
          </div>
          <div className="brand-text">
            <strong>BranchLab</strong>
            <span>AST-based targeted test generation</span>
          </div>
        </div>

        <div className="topbar-actions">
          <div
            className={`backend-pill ${backendStatus.tone}`}
            title={API_BASE}
          >
            <span className="status-dot" />
            {backendStatus.text}
          </div>

          <button
            className="theme-toggle"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label={
              theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            }
            title={
              theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
            }
          >
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </div>
      </header>

      <main className="page">
        <section className="hero">
          <div className="hero-copy">
            <h1>Generate tests that reach every branch</h1>
            <p>
              Paste a Python, Java or C program. BranchLab reads its syntax
              tree, finds the conditions that choose each path, and runs
              boundary tests on both sides of every one.
            </p>
          </div>

          <div className="hero-actions">
            {running && (
              <button className="button ghost" onClick={cancelRun}>
                <XCircle size={16} />
                Cancel
              </button>
            )}
            <button
              className="button primary"
              onClick={runAnalysis}
              disabled={running || !maxCasesValid}
            >
              {running ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Play size={16} fill="currentColor" />
              )}
              {running ? "Running analysis..." : "Run analysis"}
            </button>
          </div>
        </section>

        <section className="workspace">
          <div className="card editor-card">
            <div className="editor-head">
              <div
                className="segmented"
                role="tablist"
                aria-label="Language"
              >
                {LANGUAGES.map((item) => (
                  <button
                    key={item.value}
                    role="tab"
                    aria-selected={item.value === language}
                    className={
                      item.value === language ? "segment active" : "segment"
                    }
                    onClick={() => changeLanguage(item.value)}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <span className="file-name">
                <FileCode2 size={15} />
                {selectedLanguage.extension}
              </span>
            </div>

            <div className="monaco-wrap">
              <Editor
                height="380px"
                language={language}
                value={source}
                onChange={(value) => setSource(value ?? "")}
                theme={theme === "dark" ? "branchlab-dark" : "vs"}
                beforeMount={defineEditorThemes}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineHeight: 22,
                  fontFamily:
                    "'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
                  lineNumbers: "on",
                  roundedSelection: true,
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 4,
                  padding: { top: 16, bottom: 16 },
                  wordWrap: "on",
                  renderLineHighlight: "line",
                  overviewRulerBorder: false,
                  hideCursorInOverviewRuler: true,
                  scrollbar: {
                    verticalScrollbarSize: 8,
                    horizontalScrollbarSize: 8,
                  },
                }}
              />
            </div>

            <div className="editor-foot">
              <span>
                {lineCount} {lineCount === 1 ? "line" : "lines"}
              </span>
              <span>Switching language loads its starter program</span>
            </div>
          </div>

          <aside className="card config-card">
            <div className="card-title">
              <span className="icon-bubble lavender">
                <SlidersHorizontal size={16} />
              </span>
              <div>
                <h2>Test settings</h2>
                <p>Choose how many tests to generate.</p>
              </div>
            </div>

            <label className="field" htmlFor="max-cases">
              <span className="field-label">Maximum test cases</span>
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
                <small>Between 1 and 100</small>
              ) : (
                <small className="field-error">
                  Enter a whole number from 1 to 100
                </small>
              )}
            </label>

            <div className="field">
              <span className="field-label">Extra strategies</span>
              <Toggle
                checked={invalidTests}
                onChange={setInvalidTests}
                title="Invalid-input tests"
                hint="Text, empty values, None and huge numbers"
              />
              <Toggle
                checked={fuzzTests}
                onChange={setFuzzTests}
                title="Fuzz tests"
                hint="Seeded random and extreme values"
              />
            </div>

            <p className="note">
              <Info size={15} />
              <span>
                Boundary tests come from the conditions found in your code.
                Each extra strategy uses about 20% of the maximum.
              </span>
            </p>
          </aside>
        </section>

        {apiError && (
          <div className="banner error" role="alert">
            <XCircle size={18} />
            <span>{apiError}</span>
          </div>
        )}

        <section className="results" ref={resultsRef}>
          <div className="section-head">
            <h2>Results</h2>
            {results && <span className="chip green">Run complete</span>}
          </div>

          <div className="metrics">
            <MetricCard
              tone="blue"
              label="Tests generated"
              value={results ? totalTests : "—"}
              icon={<FlaskConical size={18} />}
            />
            <MetricCard
              tone="green"
              label="Ran successfully"
              value={results ? executedTests : "—"}
              icon={<CheckCircle2 size={18} />}
            />
            <MetricCard
              tone="amber"
              label="Errors or rejected input"
              value={results ? failedTests : "—"}
              icon={<CircleAlert size={18} />}
            />
            <MetricCard
              tone="violet"
              label="Branch coverage"
              value={
                !results
                  ? "—"
                  : coveragePercent != null
                    ? `${Number(coveragePercent).toFixed(1)}%`
                    : "Not measured"
              }
              detail={
                statementPercent != null
                  ? `Statements: ${Number(statementPercent).toFixed(1)}%`
                  : null
              }
              icon={<Gauge size={18} />}
            />
          </div>

          {results?.message && testResults.length > 0 && (
            <div className="banner info">
              <Info size={17} />
              <span>{results.message}</span>
            </div>
          )}

          <div className="card results-card">
            <div className="tabs" role="tablist">
              {RESULT_TABS.map(([key, label, Icon]) => (
                <button
                  key={key}
                  role="tab"
                  aria-selected={activeTab === key}
                  className={activeTab === key ? "tab active" : "tab"}
                  onClick={() => setActiveTab(key)}
                >
                  <Icon size={15} />
                  {label}
                  {key === "tests" && results && (
                    <span className="tab-count">{totalTests}</span>
                  )}
                </button>
              ))}
            </div>

            <div className="tab-body">
              {activeTab === "tests" &&
                (results ? (
                  testResults.length > 0 ? (
                    <div className="table-scroll">
                      <table className="table">
                        <thead>
                          <tr>
                            <th>#</th>
                            <th>Type</th>
                            <th>Inputs</th>
                            <th>Status</th>
                            <th>Output</th>
                            <th>Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {testResults.map((test, index) => {
                            const status = describeStatus(test);
                            const output = test.output?.trim() || "";
                            return (
                              <tr key={index}>
                                <td className="muted mono">
                                  {String(index + 1).padStart(2, "0")}
                                </td>
                                <td>
                                  <span
                                    className={`chip ${categoryTone(test.category)}`}
                                  >
                                    {categoryLabel(test.category)}
                                  </span>
                                </td>
                                <td>
                                  <code
                                    className="clamp"
                                    title={JSON.stringify(test.inputs)}
                                  >
                                    {formatInputs(test.inputs)}
                                  </code>
                                </td>
                                <td>
                                  <span
                                    className={`chip ${STATUS_TONES[status.tone]}`}
                                  >
                                    {status.label}
                                  </span>
                                </td>
                                <td>
                                  <span className="clamp" title={output}>
                                    {outputSummary(output, commonOutput) || "—"}
                                  </span>
                                </td>
                                <td>
                                  <span
                                    className="clamp error-text"
                                    title={test.error || ""}
                                  >
                                    {test.error || "—"}
                                  </span>
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
                  <EmptyState message="Run an analysis to see the generated tests here." />
                ))}

              {activeTab === "output" &&
                (results ? (
                  testResults.length > 0 ? (
                    <div className="output-list">
                      {testResults.map((test, index) => {
                        const status = describeStatus(test);
                        return (
                          <div className="output-entry" key={index}>
                            <div className="output-entry-head">
                              <span className="output-title">
                                Test {index + 1}
                                <span
                                  className={`chip ${categoryTone(test.category)}`}
                                >
                                  {categoryLabel(test.category)}
                                </span>
                              </span>
                              <span
                                className={`chip ${STATUS_TONES[status.tone]}`}
                              >
                                {status.label}
                              </span>
                            </div>
                            <code className="output-inputs">
                              {formatInputs(test.inputs)}
                            </code>
                            <pre>{test.output?.trim() || "(no output)"}</pre>
                            {test.error && (
                              <pre className="error-pre">{test.error}</pre>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <EmptyState
                      message={
                        results.message ||
                        "There is no execution output because no tests were generated."
                      }
                    />
                  )
                ) : (
                  <EmptyState message="Execution output will appear here after a run." />
                ))}

              {activeTab === "coverage" &&
                (results ? (
                  coveragePercent != null ? (
                    <div className="coverage">
                      <div className="coverage-summary">
                        <div className="coverage-number">
                          {Number(coveragePercent).toFixed(1)}
                          <span>%</span>
                        </div>
                        <div className="coverage-bar-wrap">
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
                            Every tracked if/while condition has two outcomes,
                            true and false. This is the share of them the
                            generated tests actually produced when the
                            program ran.
                          </p>
                        </div>
                      </div>

                      {statementPercent != null && statements && (
                        <div className="statement-summary">
                          <div className="statement-number">
                            {Number(statementPercent).toFixed(1)}
                            <span>%</span>
                          </div>
                          <div>
                            <h3>Statement coverage</h3>
                            <p>
                              {statements.covered} of {statements.total}{" "}
                              statements ran at least once.
                              {statements.missed_lines.length > 0 &&
                                ` Never ran: line${
                                  statements.missed_lines.length === 1 ? "" : "s"
                                } ${statements.missed_lines.join(", ")}.`}
                            </p>
                          </div>
                        </div>
                      )}

                      {branches.length > 0 && (
                        <div className="table-scroll">
                          <table className="table">
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
                                  <td className="mono">{branch.line}</td>
                                  <td>
                                    <code>{branch.kind ?? "if"}</code>
                                  </td>
                                  <td>
                                    <OutcomeFlag seen={branch.true_covered} />
                                  </td>
                                  <td>
                                    <OutcomeFlag seen={branch.false_covered} />
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}

                      {suggestions.length > 0 && (
                        <div className="suggestions">
                          <div className="card-title">
                            <span className="icon-bubble amber">
                              <Lightbulb size={16} />
                            </span>
                            <div>
                              <h3>Suggested tests for missing outcomes</h3>
                              <p>
                                Each suggestion was run once. Verified means
                                it really produced the missing outcome; not
                                reached means other inputs must change too,
                                for example to get into a nested condition.
                              </p>
                            </div>
                          </div>
                          <div className="table-scroll">
                            <table className="table">
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
                                    <td className="mono">{item.line}</td>
                                    <td>
                                      <code>{item.target_outcome}</code>
                                    </td>
                                    <td>
                                      <code className="clamp">
                                        {formatInputs(item.inputs)}
                                      </code>
                                    </td>
                                    <td>
                                      <span
                                        className={
                                          item.verified
                                            ? "chip green"
                                            : "chip rose"
                                        }
                                      >
                                        {item.verified
                                          ? "Verified"
                                          : "Not reached"}
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
                        <div className="banner warning">
                          <CircleAlert size={17} />
                          <span>
                            Not counted in branch coverage: {unsupportedText}.
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
                  <EmptyState message="Run an analysis to see branch coverage." />
                ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="footer">
        BranchLab · AST-Based Targeted Test Case Generation · Compiler Design
        Project
      </footer>
    </div>
  );
}

function Toggle({ checked, onChange, title, hint }) {
  return (
    <label className={checked ? "toggle on" : "toggle"}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="toggle-copy">
        <strong>{title}</strong>
        <small>{hint}</small>
      </span>
      <span className="switch" aria-hidden="true" />
    </label>
  );
}

function OutcomeFlag({ seen }) {
  return (
    <span className={seen ? "chip green" : "chip rose"}>
      {seen ? "Seen" : "Not seen"}
    </span>
  );
}

function MetricCard({ label, value, icon, tone, detail }) {
  return (
    <div className={`metric ${tone}`}>
      <span className="metric-icon">{icon}</span>
      <div>
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
        {detail && <div className="metric-detail">{detail}</div>}
      </div>
    </div>
  );
}

function EmptyState({ message }) {
  return (
    <div className="empty-state">
      <span className="icon-bubble lavender">
        <Code2 size={20} />
      </span>
      <p>{message}</p>
    </div>
  );
}

export default App;
