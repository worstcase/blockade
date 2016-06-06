import psycopg2
import random
from multiprocessing import Process, Value, Queue
import time
import datetime
import uuid
import signal
import os
import traceback


class EventHistory():
    
    def __init__(self):
        self.queue = Queue()
        self.events = []
        self.running_events = {}

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
                    self.running_events.pop(event['event_id'], None)
                else:
                    # found finish event without corresponding start
                    raise
        return

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

        for value in self.running_events.itervalues():
            named_agg = agg[value['name']]
            latency = (datetime.datetime.now() - ev['started_at']).total_seconds()
            if 'started' in named_agg:
                named_agg['running'] += 1
                if latency > named_agg['running_latency']:
                    named_agg['running_latency'] = latency
            else:
                named_agg['running'] = 1
                named_agg['running_latency'] = latency

#        print(self.running_events)
        return agg

    def aggregate_by(self, period):
        return

# to handle SIGCHLD
# glob_clients = []
# 
# def on_sigchld(signum, frame):
#     print('Got SIGCHLD. Trying to stop clients.', os.getpid())
#     traceback.print_stack(frame)
#     for client in glob_clients:
#         client.stop()
# 
# signal.signal(signal.SIGCHLD, on_sigchld)

class ClientCollection(object):
    def __init__(self, connstrs):
        self._clients = []

        for cs in connstrs:
            b = BankClient(cs)
            self._clients.append(b)
            # glob_clients.append(b)

        self._clients[0].initialize()

    @property
    def clients(self):
        return self._clients

    def __getitem__(self, index):
        return self._clients[index]

    def start(self):
        for client in self._clients:
            client.start()

    def stop(self):
        for client in self._clients:
            client.stop()
#            client.cleanup()


class BankClient(object):

    def __init__(self, connstr):
        self.connstr = connstr
        self.run = Value('b', True)
        self._history = EventHistory()
        self.accounts = 10000

    def initialize(self):
        # initialize database
        conn = psycopg2.connect(self.connstr)
        cur = conn.cursor()
        cur.execute('create extension if not exists multimaster')
        conn.commit()

        cur.execute('create table bank_test(uid int primary key, amount int)')

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
                print("Isolation error, total = %d" % (res[0],))
                raise BaseException #

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

            #cur.execute('begin')
            cur.execute('''update bank_test
                    set amount = amount - %s
                    where uid = %s''',
                    (amount, from_uid))
            cur.execute('''update bank_test
                    set amount = amount + %s
                    where uid = %s''',
                    (amount, to_uid))
            #cur.execute('commit')

            try:
                conn.commit()
            except:
                self.history.register_finish(event_id, 'rollback')
            else:
                self.history.register_finish(event_id, 'commit')
            
            #print("T", i)

        cur.close()
        conn.close()

    def watchdog(self):
        while self.run.value:
            time.sleep(1)
            print('watchdog: ', self.history.aggregate())

    def start(self):
        self.transfer_process = Process(target=self.transfer_money, args=())
        self.transfer_process.start()
        
        self.total_process = Process(target=self.check_total, args=())
        self.total_process.start()

        self.total_process = Process(target=self.watchdog, args=())
        self.total_process.start()


        return

    def stop(self):
        self.run.value = False
#        self.total_process.join()
#        self.transfer_process.join()
        return

    def cleanup(self):
        conn = psycopg2.connect(self.connstr)
        cur = conn.cursor()
        cur.execute('drop table bank_test')
        conn.commit()
        cur.close()
        conn.close()

# b = BankClient("dbname=postgres host=127.0.0.1 user=postgres")
# b.start()
# time.sleep(5)
# b.stop()
# 
# b.history.aggregate()
# 
# b.cleanup()

