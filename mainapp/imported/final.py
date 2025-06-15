import streamlit as st
from llm_agent import clean_version_in_input, get_yaml, deploy_and_graph, destroy_lab, is_delete_lab_intent

GRAPH_URL = "http://10.77.92.106:50080/"

st.set_page_config(page_title="Containerlab LLM Topology Builder", layout="wide")

# --- Session state for chat history ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "system", "content": 
            "👋 Welcome to the Containerlab LLM Topology Builder!\n\n"
            "**How to use:**\n"
            "- Describe your topology in the chat (e.g. `R1--R2--R3, V7.11`)\n"
            "- Click **Deploy** to deploy the topology\n"
            "- To delete the lab, type `delete the lab` and press Send\n"
            "- To view the graph, click **Generate Graph** and follow the instructions\n"
            "- The live topology graph will appear on the right when available"
        }
    ]

st.title("Containerlab LLM Topology Builder")

col1, col2 = st.columns([2, 3])

with col1:
    st.subheader("💬 Chat with Topology Builder")
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"<div style='color:blue'><b>You:</b> {msg['content']}</div>", unsafe_allow_html=True)
        elif msg["role"] == "assistant":
            st.markdown(f"<div style='color:green'><b>Bot:</b> <pre>{msg['content']}</pre></div>", unsafe_allow_html=True)
        else:  # system
            st.info(msg["content"])
    
    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your topology description or command:")
        submit = st.form_submit_button("Send")

    deploy = st.button("Deploy")
    gen_graph = st.button("Generate Graph")

    if submit and user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        if is_delete_lab_intent(user_input):
            destroy_lab()
            st.session_state.chat_history.append({"role": "assistant", "content": "Lab destroyed."})
        else:
            user_input_cleaned = clean_version_in_input(user_input)
            messages = [msg for msg in st.session_state.chat_history if msg["role"] in ["user"]]
            messages = [{"role": "user", "content": m["content"]} for m in messages]
            messages = [{"role": "user", "content": clean_version_in_input(m["content"])} for m in messages]
            try:
                ai_reply = get_yaml([{"role": "user", "content": user_input_cleaned}])
                with open("current_lab.yml", "w") as f:
                    f.write(ai_reply)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                st.success("YAML generated and saved to current_lab.yml.")
            except Exception as e:
                st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {e}"})
                st.error(f"Error: {e}")

    if deploy:
        with st.spinner("Deploying..."):
            deploy_and_graph()
        st.session_state.chat_history.append({"role": "assistant", "content": "Lab deployed. To view the graph, click 'Generate Graph' and follow the instructions."})
        st.success("Lab deployed.")

    if gen_graph:
        st.session_state.chat_history.append({
            "role": "assistant", 
            "content": (
                "To generate and view the topology graph:\n"
                "1. **Open a new terminal on your server.**\n"
                "2. Run:\n"
                "   `containerlab graph -t current_lab.yml`\n"
                "3. Then, view the graph below or at: "
                f"{GRAPH_URL}"
            )
        })
        st.info("Open a new terminal and run: `containerlab graph -t current_lab.yml`.\nThen return to this page and the graph will appear on the right.")

with col2:
    st.subheader("🖥️ Topology Graph Viewer")
    st.markdown(f"""
    <iframe src="{GRAPH_URL}" width="100%" height="600px" style="border:1px solid #ccc"></iframe>
    """, unsafe_allow_html=True)
    st.info(f"Topology graph will appear here if the server is running at {GRAPH_URL}")