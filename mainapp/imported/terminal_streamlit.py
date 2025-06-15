import streamlit as st
import subprocess
import re
from llm_agent import clean_version_in_input, get_yaml, destroy_lab

def parse_clab_deploy_output(deploy_output):
    results = []
    pattern = r"clab-[\w\-]+-(R\d+)\s+\│[^\│]+\│[^\│]+\│\s+([\d\.]+)\s+\│"
    matches = re.findall(pattern, deploy_output)
    for node, ip in matches:
        results.append({'node': node, 'ip': ip})
    return results

def show_router_access_table(node_list):
    st.subheader("🔑 Router SSH Access")
    st.write("""
    **How to log in:**<br>
    1. Open a terminal on this server (or your jump host)<br>
    2. Run the SSH command below for your router<br>
    **Username:** `clab`  **Password:** `clab@123`
    """, unsafe_allow_html=True)
    for node in node_list:
        ssh_cmd = f"ssh clab@{node['ip']}"
        cols = st.columns([2, 2, 3, 1])
        cols[0].write(f"**{node['node']}**")
        cols[1].write(node['ip'])
        cols[2].code(ssh_cmd, language='bash')
        copy_id = f"copy_{node['node']}"
        if cols[3].button("Copy", key=copy_id):
            st.session_state['copied'] = ssh_cmd
            st.success(f"Copied: {ssh_cmd}")
    st.info("Copy the SSH command and paste it in your own terminal on the server or via your jump host.")

st.set_page_config(page_title="Containerlab LLM Topology Builder", layout="wide")
st.title("Containerlab LLM Topology Builder")

if "yaml" not in st.session_state:
    st.session_state.yaml = ""

if "node_list" not in st.session_state:
    st.session_state.node_list = []

col1, col2 = st.columns([2, 3])

with col1:
    st.header("📝 Topology Input")
    user_input = st.text_area("Describe your topology (e.g. R1--R2--R3, V7.11)", value="", height=80)
    gen_yaml = st.button("Generate YAML")
    deploy = st.button("Deploy Topology")
    destroy = st.button("Destroy Lab")

    if gen_yaml and user_input.strip():
        user_input_cleaned = clean_version_in_input(user_input)
        messages = [{"role": "user", "content": user_input_cleaned}]
        try:
            ai_reply = get_yaml(messages)
            st.session_state.yaml = ai_reply
            with open("current_lab.yml", "w") as f:
                f.write(ai_reply)
            st.success("YAML generated and saved to current_lab.yml.")
        except Exception as e:
            st.error(f"Error: {e}")

    if st.session_state.yaml:
        st.subheader("📄 Generated YAML")
        st.code(st.session_state.yaml, language="yaml")

    if deploy:
        try:
            with st.spinner("Destroying any existing lab..."):
                destroy_lab()
            with st.spinner("Deploying new topology..."):
                result = subprocess.run(
                    ["containerlab", "deploy", "-t", "current_lab.yml"],
                    capture_output=True, text=True, check=True
                )
                deploy_output = result.stdout
            st.success("Lab deployed.")
            st.text_area("Containerlab Deploy Output", deploy_output, height=200)
            node_list = parse_clab_deploy_output(deploy_output)
            if node_list:
                st.session_state.node_list = node_list
            else:
                st.warning("No routers found in deploy output!")
        except Exception as e:
            st.error(f"Deploy failed: {e}")

    if destroy:
        destroy_lab()
        st.success("Lab destroyed.")
        st.session_state.node_list = []

with col2:
    node_list = st.session_state.get('node_list', [])
    if node_list:
        show_router_access_table(node_list)
    else:
        st.info("No routers found. Deploy a topology to see access options.")