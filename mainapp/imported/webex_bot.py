"""Webex Bot Handler for Topology Builder"""

import requests
import json
from .webex_config import *
from .llm_agent import clean_version_in_input, get_yaml
import subprocess
import os
from pyngrok import ngrok


class WebexBot:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {BOT_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        self.yaml_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'data', 'current_lab.yml')

    def send_message(self, room_id, message, markdown=None):
        """Send a message to a Webex room"""
        payload = {
            "roomId": room_id,
            "text": message
        }
        if markdown:
            payload["markdown"] = markdown

        response = requests.post(MESSAGES_URL, headers=self.headers, json=payload)
        return response.json() if response.ok else None

    def handle_message(self, webhook_data):
        """Handle incoming messages from Webex"""
        # Ignore messages from the bot itself
        if webhook_data.get('data', {}).get('personId') == BOT_ID:
            return

        message_id = webhook_data.get('data', {}).get('id')
        room_id = webhook_data.get('data', {}).get('roomId')

        # Get message details
        response = requests.get(
            f"{MESSAGES_URL}/{message_id}",
            headers=self.headers
        )
        
        if not response.ok:
            return

        message_data = response.json()
        message_text = message_data.get('text', '').strip()

        # Handle commands
        if message_text.lower().startswith('help'):
            self._send_help(room_id)
        elif message_text.lower().startswith('create'):
            self._handle_create_topology(room_id, message_text[6:].strip())
        elif message_text.lower().startswith('deploy'):
            self._handle_deploy(room_id)
        elif message_text.lower().startswith('status'):
            self._handle_status(room_id)
        elif message_text.lower().startswith('destroy'):
            self._handle_destroy(room_id)
        else:
            self.send_message(room_id, "I don't understand that command. Type 'help' to see available commands.")

    def _send_help(self, room_id):
        """Send help information"""
        help_text = """
Available commands:
- **help**: Show this help message
- **create** [topology]: Create a new topology (e.g., 'create R1--R2--R3')
- **deploy**: Deploy the current topology
- **status**: Check the status of the current deployment
- **destroy**: Destroy the current topology

Example:
```
create R1--R2--R3
deploy
status
```
"""
        self.send_message(room_id, "Help Information", help_text)

    def _handle_create_topology(self, room_id, topology_desc):
        """Handle topology creation request"""
        try:
            # Clean input and generate YAML
            cleaned_input = clean_version_in_input(topology_desc)
            yaml_content = get_yaml([{"role": "user", "content": cleaned_input}])
            
            # Save YAML
            with open(self.yaml_file, 'w') as f:
                f.write(yaml_content)

            response = f"✅ Topology created successfully!\n```yaml\n{yaml_content}\n```\nUse 'deploy' to deploy this topology."
            self.send_message(room_id, "Topology created", response)
        except Exception as e:
            self.send_message(room_id, f"❌ Error creating topology: {str(e)}")

    def _handle_deploy(self, room_id):
        """Handle topology deployment request"""
        try:
            result = subprocess.run(
                ["containerlab", "deploy", "-t", self.yaml_file],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.send_message(room_id, "✅ Topology deployed successfully!")
            else:
                self.send_message(room_id, f"❌ Deployment failed:\n```\n{result.stderr}\n```")
        except Exception as e:
            self.send_message(room_id, f"❌ Error during deployment: {str(e)}")

    def _handle_status(self, room_id):
        """Handle status check request"""
        try:
            result = subprocess.run(
                ["containerlab", "inspect", "-t", self.yaml_file],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.send_message(room_id, f"Current Status:\n```\n{result.stdout}\n```")
            else:
                self.send_message(room_id, f"❌ Error checking status:\n```\n{result.stderr}\n```")
        except Exception as e:
            self.send_message(room_id, f"❌ Error checking status: {str(e)}")

    def _handle_destroy(self, room_id):
        """Handle topology destruction request"""
        try:
            result = subprocess.run(
                ["containerlab", "destroy", "-t", self.yaml_file, "--cleanup"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                self.send_message(room_id, "✅ Topology destroyed successfully!")
            else:
                self.send_message(room_id, f"❌ Error destroying topology:\n```\n{result.stderr}\n```")
        except Exception as e:
            self.send_message(room_id, f"❌ Error destroying topology: {str(e)}")
