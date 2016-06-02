import unittest

class RecoveryTest(unittest.TestCase):
    def setUp(self):
        # docker build
        # blockade up

        self.b1 = BankTest(cs1)
        self.b1.start()

#        b2 = BankTest(cs2)
#        b2.start()
#
#        b3 = BankTest(cs3)
#        b3.start()
#
#        self.benchmarks = [b1, b2, b3]

    def test_normal_operation(self):
        
        b1_agg = self.b1.history().aggregate()
        self.assertTrue(b1_agg['commit']['count'] > 0)
        self.assertTrue(
            float(b1_agg['rollback']['count'])/b1_agg['commit']['count'] < 0.2
        )
    
    def test_node_disconnect(self):
        t1
        # blockade split
        t2
        # blockade join

        b1_agg = self.b1.history().aggregate()
        self.assertTrue(b1_agg['commit']['count'] > 0)
        self.assertTrue(
            float(b1_agg['rollback']['count'])/b1_agg['commit']['count'] < 0.2
        )






