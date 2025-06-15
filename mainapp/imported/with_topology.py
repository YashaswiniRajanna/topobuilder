import streamlit as st
import subprocess
import re
import os
import signal
from llm_agent import clean_version_in_input, get_yaml, destroy_lab

GRAPH_URL = "http://10.77.92.106:50080/"

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
    data = []
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

def restart_containerlab_graph(topology_file="current_lab.yml", port=50080):
    # Kill existing containerlab graph processes
    try:
        ps = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE)
        grep = subprocess.Popen(['grep', 'containerlab graph'], stdin=ps.stdout, stdout=subprocess.PIPE)
        awk = subprocess.Popen(['awk', '{print $2}'], stdin=grep.stdout, stdout=subprocess.PIPE)
        ps.stdout.close()
        grep.stdout.close()
        pids = awk.communicate()[0].decode('utf-8').split()
        for pid in pids:
            if pid and pid != str(os.getpid()):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except Exception:
                    pass
    except Exception as e:
        print(f"Error killing old graph processes: {e}")

    # Start a new containerlab graph server
    try:
        subprocess.Popen(
            ["containerlab", "graph", "-t", topology_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"Failed to start containerlab graph: {e}")
        return False

st.set_page_config(page_title="Bangalore CX Topology Builder", layout="wide")
st.title("Bangalore CX AI Topology Builder")

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

    st.markdown("---")
    topo_viz = st.button("Topology Visualization")
    if topo_viz:
        success = restart_containerlab_graph("current_lab.yml", port=50080)
        if success:
            st.success("Started/restarted containerlab graph server.")
        else:
            st.error("Failed to start containerlab graph server.")

    st.subheader("🖥️ Topology Graph Viewer")
    st.markdown(f"""
    <iframe src="{GRAPH_URL}" width="100%" height="600px" style="border:1px solid #ccc"></iframe>
    """, unsafe_allow_html=True)
    st.info(f"Topology graph will appear here if the server is running at {GRAPH_URL}")