import { useState } from "react";
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
  Play,
  Settings2,
  Terminal,
  XCircle,
} from "lucide-react";
import "./App.css";

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
        printf("Adult\\\\n");
    } else {
        printf("Minor\\\\n");
    }

    return 0;
}`,
};

const LANGUAGES = [
  { value: "python", label: "Python", extension: "main.py" },
  { value: "java", label: "Java", extension: "AgeCheck.java" },
  { value: "c", label: "C", extension: "main.c" },
];

function App() {
  const [language, setLanguage] = useState("python");
  const [source, setSource] = useState(EXAMPLES.python);
  const [maxCases, setMaxCases] = useState(20);
  const [invalidTests, setInvalidTests] = useState(true);
  const [fuzzTests, setFuzzTests] = useState(true);
  const [activeTab, setActiveTab] = useState("tests");
  const [results, setResults] = useState(null);
  const [running, setRunning] = useState(false);
  const [apiError, setApiError] = useState("");

  const selectedLanguage = LANGUAGES.find(
    (item) => item.value === language
  );

  function changeLanguage(nextLanguage) {
    setLanguage(nextLanguage);
    setSource(EXAMPLES[nextLanguage]);
    setResults(null);
    setApiError("");
  }

  async function runAnalysis() {
    if (!source.trim()) {
      setApiError("Enter source code before running the analysis.");
      return;
    }

    setRunning(true);
    setApiError("");
    setResults(null);

    try {
      // API endpoint will be implemented in the next step.
      const response = await fetch("http://127.0.0.1:8000/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_code: source,
          language,
          max_cases: maxCases,
          include_invalid_inputs: language === "python" && invalidTests,
          include_fuzz_inputs: language === "python" && fuzzTests,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "The analysis request failed.");
      }

      setResults(data);
    } catch (error) {
      setApiError(
        error.message.includes("fetch")
          ? "Cannot reach the Python backend. We'll configure the API next."
          : error.message
      );
    } finally {
      setRunning(false);
    }
  }

  const testResults = results?.results ?? [];
  const totalTests = results?.total_tests ?? 0;
  const executedTests = results?.successful_executions ?? 0;
  const failedTests = results?.failed_executions ?? 0;
  const coverage = results?.coverage ?? {};
  const coveragePercent = coverage.branch_coverage_percent;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark"><Braces size={22} /></div>
          <span>BranchLab</span>
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>

        <button className="nav-item active">
          <Code2 size={18} />
          <span>Code workspace</span>
        </button>
        <button className="nav-item" onClick={() => setActiveTab("tests")}>
          <FlaskConical size={18} />
          <span>Test results</span>
        </button>
        <button className="nav-item" onClick={() => setActiveTab("coverage")}>
          <Gauge size={18} />
          <span>Coverage report</span>
        </button>

        <div className="sidebar-bottom">
          <div className="backend-status">
            <span className="status-dot" />
            <div>
              <strong>Local workspace</strong>
              <small>Development mode</small>
            </div>
          </div>
          <button className="nav-item">
            <Settings2 size={18} />
            <span>Settings</span>
          </button>
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
            <div className="eyebrow">SOURCE ANALYSIS / TEST GENERATION</div>
            <h1>Code workspace</h1>
            <p>
              Generate targeted test cases and inspect program behaviour.
            </p>
          </div>
          <button
            className="run-button heading-run"
            onClick={runAnalysis}
            disabled={running}
          >
            <Play size={16} fill="currentColor" />
            {running ? "Running analysis..." : "Run analysis"}
          </button>
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
              <span><CircleAlert size={14} /> Edit source before running</span>
              <span>{source.split("\n").length} lines</span>
            </div>
          </div>

          <aside className="config-panel panel">
            <div className="panel-heading">
              <div className="panel-icon"><Settings2 size={18} /></div>
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
                min="1"
                max="100"
                value={maxCases}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  if (value >= 1 && value <= 100) setMaxCases(value);
                }}
              />
              <small>Between 1 and 100 test cases</small>
            </div>

            <div className="config-divider" />

            <div className="strategy-heading">
              <h3>Testing strategies</h3>
              <span>PYTHON ONLY</span>
            </div>

            <label className={`strategy-option ${language !== "python" ? "disabled" : ""}`}>
              <input
                type="checkbox"
                checked={invalidTests}
                disabled={language !== "python"}
                onChange={(event) => setInvalidTests(event.target.checked)}
              />
              <span className="custom-check" />
              <span className="strategy-copy">
                <strong>Invalid-input tests</strong>
                <small>Try malformed and unexpected values</small>
              </span>
            </label>

            <label className={`strategy-option ${language !== "python" ? "disabled" : ""}`}>
              <input
                type="checkbox"
                checked={fuzzTests}
                disabled={language !== "python"}
                onChange={(event) => setFuzzTests(event.target.checked)}
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
                found during AST analysis.
              </p>
            </div>

            <button
              className="run-button config-run"
              onClick={runAnalysis}
              disabled={running}
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

        <section className="results-section">
          <div className="results-heading">
            <div>
              <div className="eyebrow">ANALYSIS REPORT</div>
              <h2>Execution results</h2>
            </div>
            {results && <span className="results-ready">Run complete</span>}
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

          <div className="results-panel panel">
            <div className="results-tabs">
              <button
                className={activeTab === "tests" ? "result-tab selected" : "result-tab"}
                onClick={() => setActiveTab("tests")}
              >
                <FlaskConical size={16} /> Generated tests
              </button>
              <button
                className={activeTab === "output" ? "result-tab selected" : "result-tab"}
                onClick={() => setActiveTab("output")}
              >
                <Terminal size={16} /> Execution output
              </button>
              <button
                className={activeTab === "coverage" ? "result-tab selected" : "result-tab"}
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
                            <th>Input values</th>
                            <th>Status</th>
                            <th>Output</th>
                            <th>Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {testResults.map((test, index) => (
                            <tr key={index}>
                              <td className="test-number">
                                {String(index + 1).padStart(2, "0")}
                              </td>
                              <td><code>{JSON.stringify(test.inputs)}</code></td>
                              <td>
                                <span className={test.executed ? "status-pill success" : "status-pill failure"}>
                                  {test.executed ? "Executed" : "Error"}
                                </span>
                              </td>
                              <td className="output-cell">
                                {test.output?.trim() || "—"}
                              </td>
                              <td className="error-cell">
                                {test.error || "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <EmptyState message="No test cases were generated for this program." />
                  )
                ) : (
                  <EmptyState message="Run your source code to see generated tests here." />
                )
              )}

              {activeTab === "output" && (
                results ? (
                  <div className="output-list">
                    {testResults.map((test, index) => (
                      <div className="output-entry" key={index}>
                        <div className="output-entry-heading">
                          <span>Test {index + 1}</span>
                          <span className={test.executed ? "mini-status success-text" : "mini-status error-text"}>
                            {test.executed ? "Executed" : "Error"}
                          </span>
                        </div>
                        <pre>{test.output?.trim() || "(no output)"}</pre>
                        {test.error && <pre className="error-pre">{test.error}</pre>}
                      </div>
                    ))}
                    {testResults.length === 0 && (
                      <EmptyState message="There is no execution output yet." />
                    )}
                  </div>
                ) : (
                  <EmptyState message="Execution output will appear here after a run." />
                )
              )}

              {activeTab === "coverage" && (
                results ? (
                  <div className="coverage-view">
                    {coveragePercent != null ? (
                      <>
                        <div className="coverage-number">
                          {Number(coveragePercent).toFixed(1)}%
                        </div>
                        <div className="coverage-track">
                          <div
                            className="coverage-fill"
                            style={{
                              width: `${Math.max(0, Math.min(100, Number(coveragePercent)))}%`,
                            }}
                          />
                        </div>
                        <p>
                          Reported branch coverage from the current backend.
                        </p>
                      </>
                    ) : (
                      <EmptyState
                        message={coverage.error || "Coverage is unavailable for this language."}
                      />
                    )}
                  </div>
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
      <div className="empty-icon"><Code2 size={22} /></div>
      <p>{message}</p>
    </div>
  );
}

export default App;