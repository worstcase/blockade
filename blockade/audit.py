import json
import logging
import os
import time

from blockade import errors


_logger = logging.getLogger(__file__)


class _AuditIterator(object):
    def __init__(self, fptr, as_json):
        self._fptr = fptr
        self._as_json = as_json

    def __iter__(self):
        return self

    def __next__(self):
        l = self._fptr.readline()
        if l == "":
            self._fptr.close()
            raise StopIteration()
        if self._as_json:
            return json.loads(l)
        return l

    def next(self):
        return self.__next__()


class EventAuditor(object):
    def __init__(self, file_path):
        self._file_path = file_path
        try:
            with open(file_path, "a"):
                pass
        except IOError as ioe:
            raise errors.BlockadeError(
                    "Cannot open the audit file %s because %s" % (file_path,
                                                                  str(ioe)))

    def log_event(self, event, status, message, targets):
        normalized_target = []
        for l in targets:
            if isinstance(l, frozenset):
                normalized_target.append([str(i) for i in list(l)])
            else:
                normalized_target.append(str(l))

        line = {
            'timestamp': time.time(),
            'event': event.lower(),
            'status': status,
            'targets': normalized_target,
            'message': message
        }
        _logger.info("event=%(event)s status=%(status)s targets=%(targets)s "
                     "%(message)s" % line)
        try:
            with open(self._file_path, "a") as fptr:
                fptr.write(json.dumps(line))
                fptr.write(os.linesep)
        except Exception as ex:
            # swallow errors here and consider it a degradation of service
            _logger.error("Failed to record an audit line %s" % str(ex))

    def read_logs(self, as_json=False):
        return _AuditIterator(open(self._file_path, "r"), as_json)

    def clean(self):
        # XXX what happens when the interator is not fully walked?
        os.remove(self._file_path)
