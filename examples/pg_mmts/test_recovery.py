import unittest
import time
import subprocess
from banktest import *


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        #subprocess.check_call(['blockade','up'])
        self.clients = ClientCollection([
            "dbname=postgres host=127.0.0.1 user=postgres",
            "dbname=postgres host=127.0.0.1 user=postgres port=5433",
            "dbname=postgres host=127.0.0.1 user=postgres port=5434"
        ])
        self.clients.start()

    def tearDown(self):
        self.clients.stop()
        self.clients[0].cleanup()
        subprocess.check_call(['blockade','join'])

#    def test_0_normal_operation(self):
#        print('normalOpsTest')
#        time.sleep(5)
#        
#        for client in self.clients:
#            agg = client.history.aggregate()
#            print(agg)
#            self.assertTrue(agg['tx']['commit'] > 0)

    def test_1_node_disconnect(self):
        print('disconnectTest')
        time.sleep(3)

        subprocess.check_call(['blockade','partition','node3'])
        print('---node3 out---')
        
        time.sleep(5)

        # node1 should work
        agg = self.clients[0].history.aggregate()
        print(agg)
#        self.assertTrue(agg['tx']['commit'] > 0)

        # node3 shouldn't work
        agg = self.clients[2].history.aggregate()
        print(agg)
#        self.assertTrue(agg['tx']['commit'] == 0)

#        subprocess.check_call(['blockade','partition','node2'])
#        print('---node2 out---')
#        time.sleep(5)

        subprocess.check_call(['blockade','join'])
        print('---node2 and node3 are back---')
        time.sleep(5)

        #b1_agg = self.b1.history().aggregate()
        #self.assertTrue(b1_agg['commit']['count'] > 0)
        #self.assertTrue(
        #    float(b1_agg['rollback']['count'])/b1_agg['commit']['count'] < 0.2
        #)

if __name__ == '__main__':
    unittest.main()


