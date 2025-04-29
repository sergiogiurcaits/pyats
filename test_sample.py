from pyats.aetest import Testcase, test, main

class SimpleTest(Testcase):

    @test
    def say_hello(self):
        self.passed("Hello from pyATS!")

if __name__ == '__main__':
    main()

