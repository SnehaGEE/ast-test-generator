import streamlit as st

st.set_page_config(
    page_title="AST Test Generator",
    page_icon="",
    layout="wide",
)

st.title("AST Test Generator")
st.caption(
    "Generate targeted test cases from source-code conditions."
)

st.divider()

left, right = st.columns([1.15, 1])

with left:
    st.subheader("Source Code")

    language = st.selectbox(
        "Programming language",
        ["Python", "Java", "C"],
    )

    default_code = '''age = int(input("Enter age: "))

if age >= 18:
    print("Adult")
else:
    print("Minor")
'''

    source_code = st.text_area(
        "Enter your program",
        value=default_code if language == "Python" else "",
        height=350,
        label_visibility="collapsed",
        placeholder="Enter your source code here...",
    )

    st.subheader("Test Options")

    col_a, col_b = st.columns(2)

    with col_a:
        include_invalid = st.checkbox(
            "Invalid-input tests",
            value=True,
        )

    with col_b:
        include_fuzz = st.checkbox(
            "Fuzz tests",
            value=True,
        )

    max_cases = st.number_input(
        "Maximum test cases",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )

    run_clicked = st.button(
        "Generate & Run",
        type="primary",
        use_container_width=True,
    )

with right:
    st.subheader("Test Results")

    st.info(
        "Your generated test cases, execution output, "
        "and coverage report will appear here."
    )

    st.markdown("**Test summary**")

    metric_a, metric_b, metric_c = st.columns(3)

    metric_a.metric("Total tests", "—")
    metric_b.metric("Executed", "—")
    metric_c.metric("Errors", "—")

    st.markdown("**Generated test cases**")

    st.caption(
        "Run your program to view generated inputs and results."
    )

    st.markdown("**Execution output**")

    st.code(
        "No execution results yet.",
        language="text",
    )

    st.markdown("**Branch coverage**")

    st.progress(0)
    st.caption("Coverage will be displayed after execution.")
