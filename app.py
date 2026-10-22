import streamlit as st

from src.core.multi_language_runner import run_test_suite
from src.core.test_runner import run_python_test_suite


st.set_page_config(
    page_title="BranchLab | AST Testing",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# DESIGN SYSTEM
# =========================================================

st.markdown(
    """
    <style>
    :root {
        color-scheme: light;
    }

    .stApp {
        background: #F5F7FA !important;
        color: #243247 !important;
        font-family: Arial, Helvetica, sans-serif;
    }

    [data-testid="stHeader"] {
        background: #F5F7FA !important;
    }

    .block-container {
        max-width: 1440px;
        padding: 1.2rem 2rem 3rem;
    }

    /* Consistent typography */
    h1 {
        font-size: 2rem !important;
        line-height: 1.2 !important;
        color: #1E2D42 !important;
        letter-spacing: -0.8px !important;
        font-weight: 700 !important;
    }

    h2 {
        font-size: 1.35rem !important;
        color: #1E2D42 !important;
        font-weight: 700 !important;
    }

    h3 {
        font-size: 1.05rem !important;
        color: #263B55 !important;
        font-weight: 650 !important;
    }

    p, label, li {
        color: #526176;
        font-size: 14px;
    }

    /* Brand strip */
    .brandbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #FFFFFF;
        border: 1px solid #E0E6EE;
        border-radius: 8px;
        padding: 13px 18px;
        margin-bottom: 27px;
    }

    .brand-name {
        color: #1E3552;
        font-size: 17px;
        font-weight: 750;
        letter-spacing: -0.3px;
    }

    .brand-tagline {
        color: #758399;
        font-size: 12px;
        margin-top: 3px;
    }

    .brand-status {
        color: #39766D;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    /* Section headers */
    .section-kicker {
        color: #66809F;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.1px;
        text-transform: uppercase;
        margin-bottom: 7px;
    }

    .section-subtitle {
        color: #758399;
        font-size: 13px;
        margin-top: -6px;
        margin-bottom: 17px;
    }

    /* Panel containers */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        border: 1px solid #E0E6EE;
        border-radius: 10px;
        padding: 17px;
    }

    /* Native inputs: don't force dark surfaces */
    [data-testid="stSelectbox"] [data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #243247 !important;
        border-color: #CBD5E1 !important;
        border-radius: 6px !important;
    }

    [data-testid="stSelectbox"] input {
        color: #243247 !important;
        -webkit-text-fill-color: #243247 !important;
        background: transparent !important;
    }

    [data-testid="stSelectbox"] svg {
        fill: #526176 !important;
    }

    [data-baseweb="popover"],
    [data-baseweb="menu"] {
        background: #FFFFFF !important;
    }

    [role="option"] {
        background: #FFFFFF !important;
        color: #243247 !important;
    }

    [role="option"]:hover {
        background: #EEF3F8 !important;
    }

    [data-testid="stNumberInput"] > div {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
    }

    [data-testid="stNumberInput"] input {
        background: #FFFFFF !important;
        color: #243247 !important;
        -webkit-text-fill-color: #243247 !important;
        border: none !important;
    }

    [data-testid="stNumberInput"] button {
        background: #F0F4F8 !important;
        color: #344A63 !important;
    }

    [data-testid="stCheckbox"] label {
        color: #34465D !important;
        font-size: 13px !important;
    }

    /* Source editor */
    [data-testid="stTextArea"] textarea {
        background: #FFFFFF !important;
        color: #243247 !important;
        -webkit-text-fill-color: #243247 !important;
        caret-color: #356FB5 !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 7px !important;
        box-shadow: none !important;
        font-family: Consolas, "Courier New", monospace !important;
        font-size: 13px !important;
        line-height: 1.7 !important;
    }

    [data-testid="stTextArea"] textarea::placeholder {
        color: #8794A5 !important;
        -webkit-text-fill-color: #8794A5 !important;
    }

    [data-testid="stTextArea"] textarea:focus {
        border-color: #5685B8 !important;
        box-shadow: 0 0 0 1px #5685B8 !important;
    }

    /* Primary action */
    .stButton > button[kind="primary"] {
        background: #315F91 !important;
        color: #FFFFFF !important;
        border: 1px solid #315F91 !important;
        border-radius: 6px !important;
        min-height: 43px;
        font-size: 14px !important;
        font-weight: 650 !important;
        box-shadow: none !important;
    }

    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: #254B74 !important;
        border-color: #254B74 !important;
    }

    .stButton > button:not([kind="primary"]) {
        background: #FFFFFF !important;
        color: #34465D !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 6px !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid #E0E6EE;
        border-radius: 8px;
        padding: 14px 16px;
    }

    [data-testid="stMetricLabel"] {
        color: #758399 !important;
        font-size: 12px !important;
    }

    [data-testid="stMetricValue"] {
        color: #254E79 !important;
        font-size: 27px !important;
        font-weight: 700 !important;
    }

    /* Tables and expanders */
    [data-testid="stDataFrame"] {
        background: #FFFFFF !important;
        border: 1px solid #E0E6EE;
        border-radius: 7px;
    }

    [data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E0E6EE;
        border-radius: 7px;
    }

    [data-testid="stAlert"] {
        border-radius: 7px;
    }

    /* Tabs */
    [data-baseweb="tab-list"] {
        gap: 8px;
        border-bottom: 1px solid #E0E6EE;
    }

    [data-baseweb="tab"] {
        padding: 9px 12px;
        font-size: 13px;
    }

    [data-baseweb="tab"][aria-selected="true"] {
        color: #315F91 !important;
        border-bottom-color: #315F91 !important;
    }

    hr {
        border-color: #E0E6EE;
    }

    .muted {
        color: #758399 !important;
        font-size: 12px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="brandbar">
        <div>
            <div class="brand-name">BranchLab</div>
            <div class="brand-tagline">
                AST-based targeted testing and input analysis
            </div>
        </div>
        <div class="brand-status">COMPILER DESIGN PROJECT</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-kicker">WORKSPACE</div>',
            unsafe_allow_html=True)
st.title("Source analysis")
st.markdown(
    '<div class="section-subtitle">'
    'Configure a run, inspect the generated test cases, and review '
    'execution outcomes.'
    '</div>',
    unsafe_allow_html=True,
)


# =========================================================
# EXAMPLE PROGRAMS
# =========================================================

EXAMPLES = {
    "Python": '''age = int(input("Enter age: "))

if age >= 18:
    print("Adult")
else:
    print("Minor")
''',
    "Java": '''public class AgeCheck {
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
}
''',
    "C": r'''#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        return 1;
    }

    int age = atoi(argv[1]);

    if (age >= 18) {
        printf("Adult\n");
    } else {
        printf("Minor\n");
    }

    return 0;
}
''',
}


# =========================================================
# WORKSPACE
# =========================================================

if "source_language" not in st.session_state:
    st.session_state["source_language"] = "Python"

if "source_code" not in st.session_state:
    st.session_state["source_code"] = EXAMPLES["Python"]


def change_language():
    selected = st.session_state["language_select"]
    previous = st.session_state["source_language"]

    if selected != previous:
        st.session_state["source_language"] = selected
        st.session_state["source_code"] = EXAMPLES[selected]


editor_col, config_col = st.columns([1.75, 1], gap="large")

with config_col:
    with st.container(border=True):
        st.markdown(
            '<div class="section-kicker">01 / CONFIGURATION</div>',
            unsafe_allow_html=True,
        )
        st.subheader("Test settings")

        language = st.selectbox(
            "Programming language",
            ["Python", "Java", "C"],
            key="language_select",
            index=["Python", "Java", "C"].index(
                st.session_state["source_language"]
            ),
            on_change=change_language,
        )

        max_cases = st.number_input(
            "Maximum total test cases",
            min_value=1,
            max_value=100,
            value=20,
            step=1,
        )

        st.markdown("**Test strategies**")

        include_invalid = st.checkbox(
            "Invalid-input tests",
            value=True,
            disabled=(language != "Python"),
        )

        include_fuzz = st.checkbox(
            "Fuzz tests",
            value=True,
            disabled=(language != "Python"),
        )

        if language != "Python":
            st.caption(
                "Invalid-input and fuzz options are currently available "
                "through the Python runner only."
            )

        st.divider()

        run_clicked = st.button(
            "Run analysis",
            type="primary",
            use_container_width=True,
        )

        st.markdown(
            '<div class="muted">'
            'Runs the configured analysis using the project backend.'
            '</div>',
            unsafe_allow_html=True,
        )


with editor_col:
    with st.container(border=True):
        st.markdown(
            '<div class="section-kicker">02 / SOURCE</div>',
            unsafe_allow_html=True,
        )
        st.subheader("Code editor")
        st.caption("Use the example or paste your own program.")

        source_code = st.text_area(
            "Program source",
            key="source_code",
            height=390,
            label_visibility="collapsed",
            placeholder="Write or paste source code here...",
        )

        st.markdown(
            '<div class="muted">'
            'The current prototype analyses supported conditions in '
            'your source code.'
            '</div>',
            unsafe_allow_html=True,
        )


# =========================================================
# RUN ANALYSIS
# =========================================================

if run_clicked:
    if not source_code.strip():
        st.session_state.pop("last_result", None)
        st.session_state.pop("last_language", None)
        st.warning("Please enter source code first.")
    else:
        try:
            with st.spinner("Analysing source and generating tests..."):
                if language == "Python":
                    result = run_python_test_suite(
                        source_code,
                        max_cases=int(max_cases),
                        include_invalid_inputs=include_invalid,
                        include_fuzz_inputs=include_fuzz,
                    )
                else:
                    result = run_test_suite(
                        source_code,
                        language=language.lower(),
                        max_cases=int(max_cases),
                    )

            st.session_state["last_result"] = result
            st.session_state["last_language"] = language
            st.session_state["last_source"] = source_code

        except Exception as exc:
            st.session_state.pop("last_result", None)
            st.session_state.pop("last_language", None)
            st.error(f"Analysis failed: {exc}")


# =========================================================
# RESULTS DASHBOARD
# =========================================================

st.write("")
st.divider()

st.markdown(
    '<div class="section-kicker">03 / REPORT</div>',
    unsafe_allow_html=True,
)
st.header("Execution report")

result = st.session_state.get("last_result")
result_language = st.session_state.get("last_language")

if result is None or result_language != language:
    st.info(
        "Run an analysis to view the generated tests, execution results, "
        "and available coverage information."
    )

else:
    tests = result.get("results", [])
    total = result.get("total_tests", len(tests))
    executed = result.get("successful_executions", 0)
    errors = result.get("failed_executions", 0)

    metric1, metric2, metric3 = st.columns(3)
    metric1.metric("Total tests", total)
    metric2.metric("Successful executions", executed)
    metric3.metric("Execution errors", errors)

    if result.get("message"):
        st.info(result["message"])

    coverage = result.get("coverage", {})
    percentage = coverage.get("branch_coverage_percent")

    with st.container(border=True):
        st.subheader("Branch coverage")

        if percentage is not None:
            percentage = float(percentage)
            st.progress(max(0.0, min(1.0, percentage / 100)))
            st.write(f"Reported coverage: **{percentage:.1f}%**")
            st.caption(
                "The current Python value is estimated from static "
                "condition analysis; it is not runtime-instrumented "
                "branch coverage."
            )
        else:
            st.caption(
                coverage.get(
                    "error",
                    "Branch coverage is unavailable for this language.",
                )
            )

    rows = []

    for index, test in enumerate(tests, start=1):
        error_text = test.error or ""

        if test.executed:
            status = "Executed"
        elif "timed out" in error_text.lower():
            status = "Timed out"
        elif "ValueError" in error_text or "TypeError" in error_text:
            status = "Input rejected"
        else:
            status = "Execution error"

        rows.append({
            "Test": index,
            "Inputs": str(test.inputs),
            "Status": status,
            "Output": test.output.strip() or "—",
            "Error": error_text or "—",
        })

    all_tab, successful_tab, errors_tab = st.tabs([
        f"All tests ({len(rows)})",
        f"Executed ({executed})",
        f"Errors ({errors})",
    ])

    with all_tab:
        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
                height=350,
            )
        else:
            st.caption("No test cases were generated.")

    with successful_tab:
        successful_rows = [
            row for row in rows if row["Status"] == "Executed"
        ]

        if successful_rows:
            st.dataframe(
                successful_rows,
                use_container_width=True,
                hide_index=True,
                height=300,
            )
        else:
            st.caption("No successful executions.")

    with errors_tab:
        error_rows = [
            row for row in rows if row["Status"] != "Executed"
        ]

        if error_rows:
            st.dataframe(
                error_rows,
                use_container_width=True,
                hide_index=True,
                height=300,
            )
        else:
            st.success("No execution errors.")

    st.subheader("Test details")

    for index, test in enumerate(tests, start=1):
        state = "Executed" if test.executed else "Error"

        with st.expander(f"Test {index} · {state}"):
            st.markdown("**Inputs**")
            st.code(str(test.inputs), language="python")

            st.markdown("**Output**")
            st.code(test.output or "(no output)", language="text")

            if test.error:
                st.markdown("**Error details**")
                st.code(test.error, language="text")


# =========================================================
# FOOTER
# =========================================================

st.write("")
st.divider()
st.caption(
    "BranchLab · Compiler Design Project · "
    "Execute trusted source code only; program execution is not sandboxed."
)
