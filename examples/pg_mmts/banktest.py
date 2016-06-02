import psycopg2
import random
from multiprocessing import Process, Value, Queue
import time
import datetime
import uuid

class EventHistory():
    
    def __init__(self):
        self.queue = Queue()
        self.events = []
        self.running_events = {}
    
    def load_queue(self):
        while not self.queue.empty():
            event = self.queue.get()
            if 'name' in event:
                # start mark
                self.running_events[event['event_id']] = event
            else:
                # finish mark
                if event['event_id'] in self.running_events:
                    start_ev = self.running_events[event['event_id']]
                    self.events.append({
                        'name': start_ev['name'],
                        'started_at': start_ev['time'],
                        'finished_at': event['time'],
                        'status': event['status']
                    })
                else:
                    # found finish event without corresponding start
                    raise
        return

    def register_start(self, name):
        event_id = uuid.uuid4()
        self.queue.put({
            'name': name,
            'event_id': event_id,
            'time': datetime.datetime.now()
        })
        return event_id

    def register_finish(self, event_id, status):
        self.queue.put({
            'event_id': event_id,
            'status': status,
            'time': datetime.datetime.now()
        })

    def aggregate(self):
        self.load_queue()

        agg = {}
        for ev in self.events:
            if ev['name'] in agg:
                named_agg = agg[ev['name']]
                latency = (ev['finished_at'] - ev['started_at']).total_seconds()
                if ev['status'] in named_agg:
                    named_agg[ev['status']] += 1
                    if named_agg['max_latency'] < latency:
                        named_agg['max_latency'] = latency
                else:
                    named_agg[ev['status']] = 0
                    named_agg['max_latency'] = latency
            else:
                agg[ev['name']] = {}
        
        return agg

    def aggregate_by(self, period):
        return


class BankClient(object):

    def __init__(self, connstr):
        self.connstr = connstr
        self.run = Value('b', True)
        self._history = EventHistory()
        self.accounts = 100000

        # initialize database
        conn = psycopg2.connect(connstr)
        cur = conn.cursor()
        cur.execute('create table bank_test(uid int, amount int)')
        cur.execute('''
                insert into bank_test
                select *, 0 from generate_series(0, %s)''',
                (self.accounts,))
        conn.commit()
        cur.close()
        conn.close()

    @property
    def history(self):
        return self._history

    def check_total(self):
        conn = psycopg2.connect(self.connstr)
        cur = conn.cursor();
        while self.run.value:
            cur.execute('select sum(amount) from bank_test')
            res = cur.fetchone()
            if res[0] != 0:
                raise BaseException #"Isolation error, total = %d" % (res[0],)
            print("Check total ok")

        cur.close()
        conn.close()

    def transfer_money(self):
        print(self.connstr)
        conn = psycopg2.connect(self.connstr)
        cur = conn.cursor()
        
        i = 0
        while self.run.value:
            i += 1
            amount = 1
            from_uid = random.randrange(1, self.accounts + 1)
            to_uid = random.randrange(1, self.accounts + 1)

            event_id = self.history.register_start('tx')

            cur.execute('''update bank_test
                    set amount = amount - %s
                    where uid = %s''',
                    (amount, from_uid))
            cur.execute('''update bank_test
                    set amount = amount + %s
                    where uid = %s''',
                    (amount, to_uid))
            try:
                conn.commit()
            except:
                self.history.register_finish(event_id, 'rollback')
            else:
                self.history.register_finish(event_id, 'commit')
            
            print("Transfer", i)

        cur.close()
        conn.close()


    def start(self):
        p = Process(target=self.transfer_money, args=())
        p.start()
        
        p = Process(target=self.check_total, args=())
        p.start()
        return

    def stop(self):
        self.run.value = False
        return

    def cleanup(self):
        conn = psycopg2.connect(self.connstr)
        cur = conn.cursor()
        cur.execute('drop table bank_test')
        conn.commit()
        cur.close()
        conn.close()



b = BankClient("dbname=postgres host=127.0.0.1 user=postgres")
b.start()
time.sleep(5)
b.stop()

b.history.aggregate()

b.cleanup()

