import os
import subprocess
import json
from genie.testbed import load

def main(runtime):
    # Load testbed
    if not runtime.testbed:
        testbed_file = os.path.join('testbed.yaml')  # Update with your file if needed
        testbed = load(testbed_file)
    else:
        testbed = runtime.testbed

    results = []

    for device_name, device in testbed.devices.items():
        mgmt_ip = None

        # Try to get management IP from 'connections' -> 'defaults' or CLI
        if 'cli' in device.connections:
            cli_conn = device.connections['cli']
            mgmt_ip = cli_conn.get('ip') or cli_conn.get('host')

        if not mgmt_ip:
            print(f"[WARNING] No IP found for {device_name}. Skipping.")
            continue

        # Ping
        try:
            ping = subprocess.run(
                ['ping', '-c', '4', mgmt_ip],
                capture_output=True, text=True
            ).stdout
        except Exception as e:
            ping = f"Ping failed: {e}"

        # Traceroute
        try:
            trace = subprocess.run(
                ['traceroute', mgmt_ip],
                capture_output=True, text=True
            ).stdout
        except Exception as e:
            trace = f"Traceroute failed: {e}"

        results.append({
            "device": device_name,
            "ip": str(mgmt_ip),
            "ping_output": ping,
            "traceroute_output": trace
        })

    # Save JSON
    with open("ping_traceroute_results.json", "w") as f:
        json.dump(results, f, indent=4)

    # Create simple HTML report
    html = """
    <html><head><title>Ping & Traceroute Report</title></head>
    <body><h1>Ping & Traceroute Results</h1><table border="1">
    <tr><th>Device</th><th>IP</th><th>Ping Output</th><th>Traceroute Output</th></tr>
    """

    for r in results:
        html += f"<tr><td>{r['device']}</td><td>{r['ip']}</td>"
        html += f"<td><pre>{r['ping_output']}</pre></td>"
        html += f"<td><pre>{r['traceroute_output']}</pre></td></tr>"

    html += "</table></body></html>"

    with open("ping_traceroute_report.html", "w") as f:
        f.write(html)

    print("Ping & traceroute results saved to:")
    print(" - ping_traceroute_results.json")
    print(" - ping_traceroute_report.html")
