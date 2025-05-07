from pyats import aetest

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        for device in testbed.devices.values():
            device.connect()

class TestPing(aetest.Testcase):
    @aetest.test
    def sample_test(self):
        self.passed("Ping test placeholder")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect(self, testbed):
        for device in testbed.devices.values():
            device.disconnect()

if __name__ == '__main__':
    aetest.main()
