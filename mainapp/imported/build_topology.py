# build_topology.py

print("DEBUG: build_topology.py is running")

from llm_agent import clean_version_in_input, get_yaml, deploy_and_graph, destroy_lab, is_delete_lab_intent

def main():
    print("Containerlab YAML ReAct Agent (type 'exit' to quit)")
    chat_history = []

    while True:
        user_input = input("\nDescribe your topology (or type 'exit' to quit): ")
        if user_input.strip().lower() == 'exit':
            break
        elif is_delete_lab_intent(user_input):
            destroy_lab()
            continue
        elif user_input.strip().lower() == 'deploy':
            deploy_and_graph()
            print("\nLab deployed.")
            print("To view the topology graph, open a NEW terminal and run:")
            print("  containerlab graph -t current_lab.yml")
            print("Then visit http://<your-server-ip>:50080 in your browser.\n")
            continue

        # Destroy any existing lab before creating a new topology
        print("[DEBUG] Destroying any existing lab before creating a new topology...")
        destroy_lab()

        user_input_cleaned = clean_version_in_input(user_input)
        messages = chat_history[:]
        messages.append({"role": "user", "content": user_input_cleaned})

        try:
            ai_reply = get_yaml(messages)
            print("\nYAML:\n")
            print(ai_reply)
            with open("current_lab.yml", "w") as f:
                f.write(ai_reply)
            print("\nYAML has been saved to current_lab.yml.")
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": ai_reply})
        except Exception as e:
            print(f"\n[ERROR] {str(e)}")

if __name__ == "__main__":
    main()