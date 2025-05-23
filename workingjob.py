import re
import os
import json
import subprocess
from ipaddress import ip_interface
from concurrent.futures import ThreadPoolExecutor
from genie.testbed import load
from genie.utils import Dq

def main(runtime):
    # ----------------
    # Load the testbed
    # ----------------
    if not runtime.testbed:
        testbedfile = os.path.join('testbed29042025.yaml')
        testbed = load(testbedfile)
    else:
        testbed = runtime.testbed

    bgpsectestoutput = []
    pattern = r"\w{1}\b"
    output_dir = os.environ.get("XPRESSO_OUTPUT_DIR", "/xpresso/results")
    print("Writing outputs to:", output_dir)
    os.makedirs(output_dir, exist_ok=True)

    
    json_output_path = os.path.join(output_dir, "pingtest1.json")
    html_output_path = os.path.join(output_dir, "ping_test_report.html")

    def get_bgp_neighbor_ip(interface_ip):
        try:
            interface = ip_interface(interface_ip)
            network = interface.network

            if network.prefixlen != 31:
                raise ValueError("The provided IP address is not in a /31 subnet.")

            hosts = list(network.hosts())
            if len(hosts) != 2:
                raise ValueError("Invalid /31 subnet.")

            if str(interface.ip) == str(hosts[0]):
                neighbor_ip = str(hosts[1])
            else:
                neighbor_ip = str(hosts[0])

            return neighbor_ip

        except Exception as e:
            return f"Error: {e}"

    def ping_neighbor(device_name, interface, description, ipv4, neighbor_ip):
        try:
            result = subprocess.run(['ping', '-c', '4', neighbor_ip], capture_output=True, text=True)
            ping_output = result.stdout
        except Exception as e:
            ping_output = f"Error: {e}"

        return {
            "device": device_name,
            "interface": [interface, description],
            "ipv4": ipv4,
            "neighbor_ip": neighbor_ip,
            "ping_output": ping_output
        }

    def process_device(device_name, device):
        device.connect(init_exec_commands=[], init_config_commands=[], learn_hostname=True)
        print(f"Connected to {device_name}")

        interfaces_output = device.parse('show interfaces')
        tasks = []

        for interface, details in interfaces_output.items():
            description = details.get('description', "")
            if re.search(pattern, description):
                ipv4 = details.get('ipv4', {})
                if not ipv4:
                    print(f"No IPv4 details found for interface: {interface}")
                    continue

                ip_addresses = Dq(ipv4).contains('ip').get_values('ip')
                for ip in ipv4:
                    neighbor_ip = get_bgp_neighbor_ip(ip)
                    if "Error" in neighbor_ip:
                        print(neighbor_ip)
                        continue

                    tasks.append((device_name, interface, description, ipv4, neighbor_ip))

        return tasks

    # Collect tasks across all devices
    all_tasks = []
    for device_name, device in testbed.devices.items():
        all_tasks.extend(process_device(device_name, device))

    # Run ping tasks in parallel
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(lambda p: ping_neighbor(*p), all_tasks))

    bgpsectestoutput.extend(results)

    # Save to JSON file
    with open(json_output_path, "w") as json_file:
        json.dump(bgpsectestoutput, json_file, indent=5)

    print(f"Output has been saved to '{json_output_path}'")

    # Create HTML report
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ping Test Report</title>
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
            }
            table, th, td {
                border: 1px solid black;
            }
            th, td {
                padding: 15px;
                text-align: left;
            }
            th {
                background-color: #f2f2f2;
            }
            .success { background-color: #d4edda; color: #155724; }
            .degraded { background-color: #fff3cd; color: #856404; }
            .fail { background-color: #f8d7da; color: #721c24; }
            .collapsible {
                cursor: pointer;
            }
            .content {
                display: none;
                padding: 10px;
                background-color: #f9f9f9;
                white-space: pre-wrap;
            }
        </style>
        <script>
            function toggleContent(id) {
                var content = document.getElementById(id);
                if (content.style.display === "block") {
                    content.style.display = "none";
                } else {
                    content.style.display = "block";
                }
            }
        </script>
    </head>
    <body>
        <h1>Ping Test Report</h1>
        <table>
            <tr>
                <th>Device</th>
                <th>Interface</th>
                <th>Description</th>
                <th>IPv4</th>
                <th>Neighbor IP</th>
                <th>Status</th>
            </tr>
    """

    counter = 1
    for entry in bgpsectestoutput:
        ping_output = entry['ping_output']

        # Determine packet loss
        loss_match = re.search(r'(\d+)% packet loss', ping_output)
        loss_percent = int(loss_match.group(1)) if loss_match else 100

        if loss_percent == 0:
            status = "Success"
            css_class = "success"
        elif 0 < loss_percent < 100:
            status = "Service Degraded"
            css_class = "degraded"
        else:
            status = "Fail"
            css_class = "fail"

        content_id = f"content{counter}"

        html_content += f"""
            <tr class="{css_class}">
                <td>{entry['device']}</td>
                <td>{entry['interface'][0]}</td>
                <td>{entry['interface'][1]}</td>
                <td>{entry['ipv4']}</td>
                <td>{entry['neighbor_ip']}</td>
                <td>
                    {status}
                    <br>
                    <span class="collapsible" onclick="toggleContent('{content_id}')">
                        [Show/Hide Details]
                    </span>
                    <div class="content" id="{content_id}">{ping_output}</div>
                </td>
            </tr>
        """
        counter += 1

    html_content += """
        </table>
    </body>
    </html>
    """

    # Save HTML report
    with open(html_output_path, "w") as html_file:
        html_file.write(html_content)

    print(f"HTML report has been saved to '{html_output_path}'")
    print("XPRESSO_OUTPUT_DIR:", os.environ.get("XPRESSO_OUTPUT_DIR"))
    print("Writing files to:", output_dir)
    print("Output files expected:", json_output_path, html_output_path)

