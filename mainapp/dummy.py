from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from .imported.llm_agent import clean_version_in_input, get_yaml, destroy_lab
import subprocess, os, signal, time
from django.views.decorators.csrf import csrf_exempt
import re
from .imported.webex_bot import WebexBot

GRAPH_URL = "http://10.77.92.106:50080/"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML_FILE = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', 'current_lab.yml')


# Initialize the Webex bot
webex_bot = WebexBot()


def parse_clab_deploy_output(deploy_output):
    results = []
    pattern = r"clab-[\w\-]+-([\w\d]+)\s+\│[^\│]+\│[^\│]+\│\s+([\d\.]+)\s+\│"
    matches = re.findall(pattern, deploy_output)
    
    # Read the YAML file to get interface information
    yaml_path = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', 'current_lab.yml')
    try:
        with open(yaml_path, 'r') as f:
            import yaml
            topo_data = yaml.safe_load(f)
            links = topo_data.get('topology', {}).get('links', [])
    except:
        links = []
    
    for node, ip in matches:
        # Find interfaces for this node
        node_interfaces = []
        for link in links:
            for endpoint in link['endpoints']:
                if endpoint.startswith(f"{node}:"):
                    interface = endpoint.split(':')[1]
                    if interface not in node_interfaces:
                        node_interfaces.append(interface)
        
        results.append({
            'node': node,
            'ip': ip,
            'interfaces': node_interfaces
        })
    return results


@csrf_exempt
def cleanup_sshx(request):
    """Clean up old SSHX session."""
    if request.method == 'POST':
        try:
            result = subprocess.run(
                ["docker", "rm", "-f", "clab-Cisco_Internal-sshx"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return JsonResponse({
                    'status': 'success',
                    'message': 'Old SSHX session cleaned up successfully'
                })
            return JsonResponse({
                'status': 'info',
                'message': 'No old SSHX session found'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error during cleanup: {str(e)}'
            }, status=500)
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def activate_sshx(request):
    """Activate SSHX session and return the connection link."""
    if request.method == 'POST':
        try:
            cmd = ["containerlab", "tools", "sshx", "attach", "-t", YAML_FILE]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            sshx_link = None
            output_lines = []
            start_time = time.time()
            max_wait = 120

            while True:
                line = proc.stdout.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                    continue

                output_lines.append(line)
                
                if "link=https://sshx.io/s/" in line:
                    sshx_link = line.split("link=")[-1].strip()
                    break
                    
                m = re.search(r'(https://sshx\.io/s/[A-Za-z0-9#]+)', line)
                if m:
                    sshx_link = m.group(1)
                    break
                    
                if time.time() - start_time > max_wait:
                    break

            remaining = proc.communicate()[0]
            if remaining:
                output_lines.append(remaining)
            full_output = "".join(output_lines)

            if sshx_link:
                return JsonResponse({
                    'status': 'success',
                    'sshx_link': sshx_link,
                    'output': full_output
                })
            return JsonResponse({
                'status': 'error',
                'message': 'Could not find SSHX link in output',
                'output': full_output
            }, status=500)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': f'Error activating SSHX: {str(e)}'
            }, status=500)
    return JsonResponse({'message': 'Method not allowed'}, status=405)


@csrf_exempt
def get_router_list(request):
    """Get the list of available routers and their access information."""
    try:
        # Get the deploy output from the last deployment
        result = subprocess.run(
            ["containerlab", "inspect", "-t", YAML_FILE],
            capture_output=True, text=True
        )
        routers = parse_clab_deploy_output(result.stdout)
        return JsonResponse({
            'status': 'success',
            'routers': routers
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Error getting router list: {str(e)}'
        }, status=500)


def restart_containerlab_graph(request, topology_file="current_lab.yml", port=50080):
    """Restarts the containerlab graph visualization server."""
    try:
        # Kill existing containerlab graph processes
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
        print(f"[ERROR] Killing old graph processes: {e}")

    try:
        # Start containerlab graph
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        yaml_path = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', topology_file)
        
        subprocess.Popen(
            ["containerlab", "graph", "-t", yaml_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'graph_url': GRAPH_URL,
                'message': 'Graph server started successfully'
            })
        return JsonResponse({'graph_url': GRAPH_URL})
    except Exception as e:
        print(f"[ERROR] Starting containerlab graph: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': f'Failed to start graph server: {str(e)}'
            }, status=400)
        return JsonResponse({'error': str(e)}, status=400)


def view_toplogy(request):
    """Django view to restart containerlab graph and render iframe."""
    success = restart_containerlab_graph(request, "current_lab.yml", port=50080)
    message = (
        "✅ Containerlab graph server started successfully."
        if success else
        "❌ Failed to start containerlab graph server."
    )
    return render(request, 'visualise.html', {
        'message': message,
        'graph_url': GRAPH_URL
    })



# def visualise_topology(request):
#     message = ""
#     try:
#         # Kill old graph processes
#         ps = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE)
#         grep = subprocess.Popen(['grep', 'containerlab graph'], stdin=ps.stdout, stdout=subprocess.PIPE)
#         awk = subprocess.Popen(['awk', '{print $2}'], stdin=grep.stdout, stdout=subprocess.PIPE)
#         ps.stdout.close()
#         grep.stdout.close()
#         pids = awk.communicate()[0].decode('utf-8').split()
#         for pid in pids:
#             if pid and pid != str(os.getpid()):
#                 try:
#                     os.kill(int(pid), signal.SIGKILL)
#                 except Exception:
#                     pass
#     except Exception as e:
#         print(f"Error killing old graph processes: {e}")


#     except Exception as e:
#         message = f"Error: {e}"

#     return render(request, 'visualise.html', {'message': message})


def home(request):
    return render(request, 'index.html')

def visualise_topology(request):
    return render(request, 'visualise.html')


def yaml_topology(request):
    if request.method == 'POST':
        try:
            user_input = request.POST.get('user_input', '')
            # Clean the version from the input
            cleaned_input = clean_version_in_input(user_input)
            # Generate YAML using the LLM agent
            yaml_content = get_yaml(cleaned_input)
            
            # Save the YAML to a file
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            file_path = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', 'current_lab.yml')
            with open(file_path, 'w') as f:
                f.write(yaml_content)
            
            return JsonResponse({
                'status': 'success',
                'yaml': yaml_content,
                'message': 'YAML configuration generated successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    # Handle GET request
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', 'current_lab.yml')
        
        with open(file_path, 'r') as f:
            yaml_content = f.read()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'yaml': yaml_content,
                'message': 'YAML Configuration'
            })
        return render(request, 'yaml_result.html', {
            'message': 'YAML Configuration',
            'yaml': yaml_content
        })
    except Exception as e:
        return render(request, 'yaml_result.html', {
            'message': f'Error: {str(e)}',
            'yaml': ''
        })

def user_input(request):
    print("[DEBUG] user_input view called with method:", request.method)
    if request.method == 'POST':
        user_input = request.POST.get('user_input')
        action = request.POST.get('action')
        print("[DEBUG] Received user input:", user_input)
        print("[DEBUG] Action:", action)    
        
        # Base directory for file operations
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(BASE_DIR, 'mainapp', 'static', 'data', 'current_lab.yml')
        
        if action == 'generate' and user_input and user_input.strip():
            cleaned_input = clean_version_in_input(user_input)
            messages = [{"role": "user", "content": cleaned_input}]
            try:
                yaml_output = get_yaml(messages)
                print("[DEBUG] YAML generated:", yaml_output)
                
                # Save YAML to file
                with open(file_path, "w") as f:
                    f.write(yaml_output)
                    print(f"[DEBUG] YAML written to file: {yaml_output}") 
                
                return JsonResponse({
                    'status': 'success',
                    'message': "YAML generated successfully",
                    'yaml': yaml_output
                })
            except Exception as e:
                return JsonResponse({
                    'status': 'error',
                    'message': f"Error generating YAML: {str(e)}"
                }, status=400)
                
        # elif action == 'deploy':
        #     try:
        #         # Check if YAML file exists
        #         if not os.path.exists(file_path):
        #             raise FileNotFoundError("No YAML configuration found. Please generate YAML first.")
                
        #         # Read the current YAML content
        #         with open(file_path, 'r') as f:
        #             yaml_content = f.read()
                
        #         # Deploy the lab
        #         result = subprocess.run(
        #             ["containerlab", "deploy", "-t", file_path],
        #             capture_output=True,
        #             text=True,
        #             check=True
        #         )
                
        #         return render(request, 'visualise.html', {
        #             'message': "Topology deployed successfully",
        #             'yaml': yaml_content,
        #             'deploy_output': result.stdout,
        #             'user_input': user_input
        #         })
                
        #     except FileNotFoundError as e:
        #         return render(request, 'visualise.html', {
        #             'message': str(e),
        #             'user_input': user_input
        #         })
        #     except subprocess.CalledProcessError as e:
        #         return render(request, 'visualise.html', {
        #             'message': f"Error deploying topology: {e.stderr}",
        #             'yaml': yaml_content if 'yaml_content' in locals() else '',
        #             'user_input': user_input
        #         })
        #     except Exception as e:
        #         return render(request, 'visualise.html', {
        #             'message': f"Error: {str(e)}",
        #             'user_input': user_input
        #         })

    

    # GET request - just show the main page
    return render(request, 'index.html')




# from django.shortcuts import render
# from django.http import HttpResponse
# # from .utils import get_yaml, clean_version_in_input  # Your custom functions
# from .imported.llm_agent import clean_version_in_input, get_yaml, destroy_lab
# import subprocess, os, signal

# from django.shortcuts import render

# GRAPH_URL = "http://10.77.92.106:50080/"


# def restart_containerlab_graph(topology_file="current_lab.yml", port=50080):
#     # Kill existing containerlab graph processes
#     try:
#         ps = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE)
#         grep = subprocess.Popen(['grep', 'containerlab graph'], stdin=ps.stdout, stdout=subprocess.PIPE)
#         awk = subprocess.Popen(['awk', '{print $2}'], stdin=grep.stdout, stdout=subprocess.PIPE)
#         ps.stdout.close()
#         grep.stdout.close()
#         pids = awk.communicate()[0].decode('utf-8').split()
#         for pid in pids:
#             if pid and pid != str(os.getpid()):
#                 try:
#                     os.kill(int(pid), signal.SIGKILL)
#                 except Exception:
#                     pass
#     except Exception as e:
#         print(f"[ERROR] Killing old graph processes: {e}")

#     # Start containerlab graph
#     try:
#         subprocess.Popen(
#             ["containerlab", "graph", "-t", topology_file],
#             stdout=subprocess.DEVNULL,
#             stderr=subprocess.DEVNULL
#         )
#         return True
#     except Exception as e:
#         print(f"[ERROR] Starting containerlab graph: {e}")
#         return False


# def view_toplogy(request):
#     """Django view to restart containerlab graph and render iframe."""
#     success = restart_containerlab_graph("current_lab.yml", port=50080)
#     message = (
#         "✅ Containerlab graph server started successfully."
#         if success else
#         "❌ Failed to start containerlab graph server."
#     )
#     return render(request, 'visualise.html', {
#         'message': message,
#         'graph_url': GRAPH_URL
#     })



# # def visualise_topology(request):
# #     message = ""
# #     try:
# #         # Kill old graph processes
# #         ps = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE)
# #         grep = subprocess.Popen(['grep', 'containerlab graph'], stdin=ps.stdout, stdout=subprocess.PIPE)
# #         awk = subprocess.Popen(['awk', '{print $2}'], stdin=grep.stdout, stdout=subprocess.PIPE)
# #         ps.stdout.close()
# #         grep.stdout.close()
# #         pids = awk.communicate()[0].decode('utf-8').split()
# #         for pid in pids:
# #             if pid and pid != str(os.getpid()):
# #                 try:
# #                     os.kill(int(pid), signal.SIGKILL)
# #                 except Exception:
# #                     pass
# #     except Exception as e:
# #         print(f"Error killing old graph processes: {e}")


# #     except Exception as e:
# #         message = f"Error: {e}"

# #     return render(request, 'visualise.html', {'message': message})


# def home(request):
#     return render(request, 'index.html')

# def visualise_topology(request):
#     return render(request, 'visualise.html')


# def yaml_topology(request):
#     return render(request, 'yaml_result.html')

# def user_input(request):
#     print("[DEBUG] user_input view called with method:", request.method)
#     if request.method == 'POST':
#         user_input = request.POST.get('user_input')
#         action = request.POST.get('action')
#         print("[DEBUG] Received user input:", user_input)
#         print("[DEBUG] Action:", action)    
#         if action == 'generate' and user_input and user_input.strip():
#             cleaned_input = clean_version_in_input(user_input)
#             messages = [{"role": "user", "content": cleaned_input}]
#             try:
#                 yaml_output = get_yaml(messages)
#                 print("[DEBUG] YAML generated:", yaml_output)
#                 BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # project root
#                 file_path = os.path.join(BASE_DIR, 'mainapp','static', 'data', 'current_lab.yml')
#                 with open(file_path, "w") as f:
#                     f.write(yaml_output)
#                     print(f"[DEBUG] YAML written to file: {yaml_output}") 
#                 return render(request, 'visualise.html', {
#                     'message': "YAML generated",
#                     'yaml': yaml_output
#                 })
#             except Exception as e:
#                 return render(request, 'visualise.html', {'message': f"Error: {e}"})

#         elif action == 'deploy':
#             # Your deploy logic here
#             return HttpResponse("Deploy clicked")

#         elif action == 'destroy':
#             # Your destroy logic here
#             return HttpResponse("Destroy clicked")

#     return render(request, 'visualise.html')

@csrf_exempt
def webex_webhook(request):
    """Handle incoming Webex webhooks"""
    if request.method == 'POST':
        try:
            webhook_data = json.loads(request.body)
            webex_bot.handle_message(webhook_data)
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)


