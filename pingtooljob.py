import os
from pyats.easypy import run
from pyats import aetest
import re
import subprocess
import json
from ipaddress import ip_interface
from concurrent.futures import ThreadPoolExecutor
from genie.testbed import load
from genie.utils import Dq

# -----------------------
# AEtest Test Definitions
# -----------------------

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        self.parent.parameters['testbed'] = testbed
        self.parent.parameters['pattern'] = r"\w{1}\b"
        self.parent.parameters['results'] = []
        self.parent.parameters['output_dir'] = os.environ.get("XPRESSO_OUTPUT_DIR", "/xpresso/results")
        os.makedirs(self.parent.parameters['output_dir'], exist_ok=True)

        for device in testbed.devices.values():
            device.connect(init_exec_commands=[], init_config_commands=[], learn_hostname=True)


class PingTest(aetest.Testcase):
    @aetest.setup
    def setup(self, testbed, pattern):
        self.testbed = testbed
        self.pattern = pattern
        self.all_tasks = []

        for device_name, device in self.testbed.devices.items():
            self.all_tasks.extend(self.process_device(device_name, device))

    def get_bgp_neighbor_ip(self, interface_ip):
        try:
            interface = ip_interface(interface_ip)
            network = interface.network
            if network.prefixlen != 31:
                raise ValueError("The provided IP address is not in a /31 subnet.")
            hosts = list(network.hosts())
            return str(hosts[1]) if str(interface.ip) == str(hosts[0]) else str(hosts[0])
        except Exception as e:
            return f"Error: {e}"

    def process_device(self, device_name, device):
        interfaces_output = device.parse('show interfaces', timeout=3200)
        tasks = []

        for interface, details in interfaces_output.items():
            description = details.get('description', "")
            if re.search(self.pattern, description):
                ipv4 = details.get('ipv4', {})
                if not ipv4:
                    continue
                ip_addresses = Dq(ipv4).contains('ip').get_values('ip')
                for ip in ip_addresses:
                    neighbor_ip = self.get_bgp_neighbor_ip(ip)
                    if "Error" in neighbor_ip:
                        continue
                    tasks.append((device_name, interface, description, ipv4, neighbor_ip))
        return tasks

    def ping_neighbor(self, device_name, interface, description, ipv4, neighbor_ip):
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

    @aetest.test
    def run_ping_tests(self, results):
        with ThreadPoolExecutor() as executor:
            output = list(executor.map(lambda p: self.ping_neighbor(*p), self.all_tasks))
        results.extend(output)


class GenerateReport(aetest.Testcase):
    @aetest.test
    def generate(self, results, output_dir):
        json_path = os.path.join(output_dir, "ping_results.json")
        html_path = os.path.join(output_dir, "ping_report.html")

        # Save JSON
        with open(json_path, "w") as f:
            json.dump(results, f, indent=4)

        # Generate HTML
        html = """
        <html><head><title>Ping Report</title><style>
        table {width: 100%; border-collapse: collapse;}
        th, td {border: 1px solid #ddd; padding: 8px;}
        th {background-color: #f2f2f2;}
        .success {background-color: #d4edda;}
        .degraded {background-color: #fff3cd;}
        .fail {background-color: #f8d7da;}
        </style></head><body><h2>Ping Report</h2><table>
        <tr><th>Device</th><th>Interface</th><th>Description</th><th>IPv4</th><th>Neighbor</th><th>Status</th></tr>
        """

        for idx, entry in enumerate(results, 1):
            ping_out = entry['ping_output']
            loss = re.search(r'(\d+)% packet loss', ping_out)
            loss_pct = int(loss.group(1)) if loss else 100

            if loss_pct == 0:
                status, cls = "Success", "success"
            elif loss_pct < 100:
                status, cls = "Degraded", "degraded"
            else:
                status, cls = "Fail", "fail"

            html += f"<tr class='{cls}'><td>{entry['device']}</td><td>{entry['interface'][0]}</td><td>{entry['interface'][1]}</td><td>{entry['ipv4']}</td><td>{entry['neighbor_ip']}</td><td>{status}</td></tr>"

        html += "</table></body></html>"

        with open(html_path, "w") as f:
            f.write(html)

        print(f"Saved JSON to {json_path}")
        print(f"Saved HTML to {html_path}")


class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        for device in testbed.devices.values():
            device.disconnect()

# -----------------------
# Easypy Job Entry Point
# -----------------------

def main(runtime):
    # Optional override of testbed file
    testbed = runtime.testbed or os.path.join(os.path.dirname(__file__), "testbed29042025.yaml")

    run(testscript=__file__, testbed=testbed)
