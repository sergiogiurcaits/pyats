import os
import json
import subprocess
from genie.testbed import load
from concurrent.futures import ThreadPoolExecutor

def ping_device(name, ip):
    try:
        result = subprocess.run(['ping', '-c', '3', ip], capture_output=True, text=True, timeout=10)
        return {
            "device": name,
            "ip": ip,
            "ping_status": "success" if result.returncode == 0 else "fail",
            "ping_output": result.stdout
        }
    except Exception as e:
        return {"device": name, "ip": ip, "ping_status": "error", "ping_output": str(e)}

def traceroute_device(name, ip):
    try:
        result = subprocess.run(['traceroute', ip], capture_output=True, text=True, timeout=20)
        return {
            "device": name,
            "ip": ip,
            "traceroute_status": "success" if result.returncode == 0 else "fail",
            "traceroute_output": result.stdout
        }
    except Exception as e:
        return {"device": name, "ip": ip, "traceroute_status": "error", "traceroute_output": str(e)}

def main(runtime):
    testbed = runtime.testbed if runtime.testbed else load("testbed.yaml")

    tasks = []
    for device in testbed.devices.values():
        conn = device.connections.get("console", {})
        raw_ip = conn.get("ip") or conn.get("host")
        if raw_ip:
            tasks.append((device.name, str(raw_ip)))  # Convert to string to ensure JSON compatibility
        else:
            print(f"Skipping device {device.name} - no management IP defined.")

    with ThreadPoolExecutor() as executor:
        ping_results = list(executor.map(lambda x: ping_device(*x), tasks))
        traceroute_results = list(executor.map(lambda x: traceroute_device(*x), tasks))

    combined = []
    for ping, trace in zip(ping_results, traceroute_results):
        combined.append({
            **ping,
            **{k: v for k, v in trace.items() if k not in ("device", "ip")}
        })

    with open("connectivity_results.json", "w") as f:
        json.dump(combined, f, indent=2)

    with open("connectivity_report.html", "w") as f:
        f.write("<html><body><h1>Device Connectivity Report</h1><table border='1'>")
        f.write("<tr><th>Device</th><th>IP</th><th>Ping</th><th>Traceroute</th></tr>")
        for entry in combined:
            f.write(f"<tr><td>{entry['device']}</td><td>{entry['ip']}</td>"
                    f"<td>{entry['ping_status']}</td><td>{entry['traceroute_status']}</td></tr>")
        f.write("</table></body></html>")

    print("Connectivity check completed. Results saved to JSON and HTML.")
