import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="GEO Research Copilot", layout="wide")
st.title("🧬 GEO Research Copilot")
st.caption("Paste a GEO accession — understand your dataset, discover research directions, and get a full computational pipeline.")

url_input = st.text_input("GEO Accession or URL", placeholder="GSE90496")

if st.button("Analyze Dataset") and url_input:
    st.session_state.clear()
    st.session_state["url_input"] = url_input

    # Step 1: dataset analysis
    with st.spinner("Fetching dataset metadata..."):
        resp = requests.post(
            f"{API_URL}/api/dataset/analyze",
            json={"url": url_input}
        )

    if resp.status_code != 200:
        st.error(f"Error: {resp.json().get('detail')}")
        st.stop()

    data = resp.json()
    st.session_state["metadata"] = data["metadata"]
    st.session_state["summary"] = data["summary"]

metadata = st.session_state.get("metadata")
summary = st.session_state.get("summary")

if metadata:
    accession = metadata["accession"]

    # dataset overview
    st.divider()
    st.subheader("Dataset Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Samples", metadata.get("sample_count", "N/A"))
    col2.metric("Organism", metadata.get("organism", "N/A"))
    col3.metric("Technology", metadata.get("technology", "N/A")[:25])
    col4.metric("Submitted", metadata.get("submission_date", "N/A"))

    st.write(f"**Title:** {metadata.get('title')}")

    if summary and "error" not in summary:
        with st.expander("AI Understanding", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Research Question:** {summary.get('research_question')}")
                st.write(f"**Biological Context:** {summary.get('biological_context')}")
                st.write(f"**Experimental Design:** {summary.get('experimental_design')}")
            with col2:
                st.write(f"**Data Type:** {summary.get('data_type')}")
                st.write(f"**Key Comparison:** {summary.get('key_comparison')}")
                st.write(f"**Scientific Value:** {summary.get('potential_value')}")

    if metadata.get("sample_conditions"):
        with st.expander(f"Sample Conditions ({len(metadata['sample_conditions'])} shown)"):
            for c in metadata["sample_conditions"]:
                st.write(f"• {c}")

    # Step 2: research options
    st.divider()
    st.subheader("Research Directions")

    if "research_options" not in st.session_state:
        with st.spinner("Generating research options..."):
            resp2 = requests.post(
                f"{API_URL}/api/research/options",
                json={"accession": accession}
            )
        if resp2.status_code != 200:
            st.error(f"Research options error: {resp2.json().get('detail')}")
            st.stop()

        research_data = resp2.json()
        st.session_state["research_options"] = research_data

    research_data = st.session_state["research_options"]
    feasible = research_data.get("feasible_analyses", [])
    infeasible = research_data.get("infeasible_analyses", [])

    st.write(f"Found **{len(feasible)}** feasible analyses for this dataset.")

    if feasible:
        st.markdown("### ✅ Feasible Analyses")
        cols = st.columns(min(len(feasible), 3))
        for i, option in enumerate(feasible):
            with cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"**{option.get('title')}**")
                    difficulty = option.get('difficulty', '')
                    color = {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(difficulty, "⚪")
                    st.caption(f"{color} {difficulty.capitalize()}")
                    st.write(option.get("question"))
                    st.caption("**Expected outputs:**")
                    for output in option.get("expected_outputs", []):
                        st.caption(f"• {output}")
                    if st.button("Generate Pipeline →", key=f"plan_{option.get('id')}_{i}"):
                        st.session_state["selected_analysis"] = option
                        st.session_state.pop("pipeline", None)

    if infeasible:
        with st.expander(f"❌ {len(infeasible)} analyses not supported by this dataset"):
            for option in infeasible:
                st.write(f"**{option.get('title')}** — {option.get('feasibility_reason')}")

    # custom objective
    st.divider()
    custom = st.text_input("Or describe your own research objective:", placeholder="I want to investigate whether promoter methylation correlates with tumor grade...")
    if st.button("Plan Custom Pipeline") and custom:
        st.session_state["selected_analysis"] = {
            "id": "custom",
            "title": "Custom Analysis",
            "question": custom,
            "required_data": [],
            "expected_outputs": []
        }
        st.session_state.pop("pipeline", None)

    # Step 3: pipeline
    if "selected_analysis" in st.session_state:
        selected = st.session_state["selected_analysis"]

        st.divider()
        st.subheader(f"Pipeline: {selected.get('title')}")
        st.write(f"**Objective:** {selected.get('question')}")

        if "pipeline" not in st.session_state:
            with st.spinner("Generating computational pipeline..."):
                resp3 = requests.post(
                    f"{API_URL}/api/pipeline/plan",
                    json={
                        "accession": accession,
                        "analysis_id": selected.get("id"),
                        "custom_objective": selected.get("question") if selected.get("id") == "custom" else None
                    }
                )

            if resp3.status_code != 200:
                st.error(f"Pipeline error: {resp3.json().get('detail')}")
                st.stop()

            st.session_state["pipeline"] = resp3.json()["pipeline"]

        pipeline = st.session_state["pipeline"]

        if "error" in pipeline:
            st.error(pipeline["error"])
        else:
            # hypothesis
            st.info(f"**Hypothesis:** {pipeline.get('hypothesis')}")

            # steps
            st.markdown("### Computational Steps")
            for step in pipeline.get("steps", []):
                is_decision = step.get("decision_point", False)
                icon = "🔀" if is_decision else "▶️"

                with st.expander(f"{icon} Step {step.get('step_id')}: {step.get('name')} — `{step.get('tool')}`", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Why:** {step.get('why')}")
                        st.write(f"**Input:** {step.get('input')}")
                        st.write(f"**Output:** {step.get('output')}")
                    with col2:
                        st.caption(f"⏱ {step.get('estimated_time', 'N/A')}")
                        if is_decision:
                            st.warning(f"**Decision:** {step.get('decision_logic')}")

            # provenance
            with st.expander("Provenance & Parameters"):
                prov = pipeline.get("provenance", {})
                st.json(prov)

            # expected outputs
            st.markdown("### Expected Outputs")
            for output in pipeline.get("expected_outputs", []):
                st.write(f"✓ {output}")
