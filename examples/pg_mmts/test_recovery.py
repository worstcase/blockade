import unittest
import time
import subprocess
from banktest import *

class RecoveryTest(unittest.TestCase):
    def setUp(self):
        # docker build
        # blockade up
        #subprocess.check_call(['blockade','up'])

        print('setUp')

        self.b1 = BankClient("dbname=postgres host=127.0.0.1 user=postgres")
        self.b1.start()

#        b2 = BankTest(cs2)
#        b2.start()
#
#        b3 = BankTest(cs3)
#        b3.start()
#
#        self.benchmarks = [b1, b2, b3]

    def tearDown(self):
        print('tearDown')

        self.b1.stop()
        self.b1.cleanup()
        subprocess.check_call(['blockade','join'])

    def test_normal_operation(self):
        print('normalOps')

        time.sleep(4)
        
        b1_agg = self.b1.history.aggregate()
        print(b1_agg)
        self.assertTrue(b1_agg['tx']['commit'] > 0)
    
    def test_node_disconnect(self):
        print('disconnect')

        time.sleep(5)

        subprocess.check_call(['blockade','partition','node3'])
        print('---node3 out---')
        time.sleep(5)

        subprocess.check_call(['blockade','join'])
        print('---node3 back---')
        time.sleep(5)

        #b1_agg = self.b1.history().aggregate()
        #self.assertTrue(b1_agg['commit']['count'] > 0)
        #self.assertTrue(
        #    float(b1_agg['rollback']['count'])/b1_agg['commit']['count'] < 0.2
        #)

if __name__ == '__main__':
    unittest.main()


