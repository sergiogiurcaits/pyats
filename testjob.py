from pyats.easypy import run
import os

def main(runtime):
    # Get the testscript path (update with your actual test script)
    testscript = os.path.join(os.path.dirname(__file__), 'testscript.py')

    # Optional: define testbed path if not passed via CLI or Xpresso
    testbed = runtime.testbed or os.path.join(os.path.dirname(__file__), 'testbed.yaml')

    # Run the testscript
    run(testscript=testscript, testbed=testbed)
