import multiprocessing as mp
import threading
import time
import sys


def padding(subject, target, char="0"):
    if type(target) == type(""):
        target = len(target)
    string = str(subject)
    while len(string) < target:
        string = char + string
    return string


def format(duration):
    seconds = int(duration)
    minutes = seconds // 60
    seconds -= 60 * minutes
    hours = minutes // 60
    minutes -= hours * 60
    string = ""
    if hours > 0:
        string += "{}h ".format(hours)
    if minutes > 0 or hours > 0:
        string += "{}min ".format(padding(minutes, 2))
    if hours == 0:
        string += "{}s".format(padding(seconds, 2))
    return string


def progress(current, final, start, last="", size=30):
    elapsed = time.time() - start
    speed = current / elapsed
    eta = (final - current) / speed
    string = "\r{0}/{1} [".format(padding(current, str(final)), final)
    for _ in range(int(size * current / final) - 1):
        string += "="
    if current == final:
        string += "="
    else:
        string += ">"
    for _ in range(size - int(size * current / final)):
        string += " "
    string += "] - {} tasks/s".format(round(speed, 2))
    string += " - elapsed: " + format(elapsed)
    string += " - eta: " + format(eta)
    whitespaces = ""
    for i in range(len(last) - len(string)):
        whitespaces += " "
    print(string + whitespaces, end="")
    sys.stdout.flush()
    return string


class Worker(mp.Process):

    def __init__(self, q_in, q_out, q_event, timeout, initializer):
        self.q_in = q_in
        self.q_out = q_out
        self.q_event = q_event
        self.timeout = timeout
        self.data = None
        if initializer is not None:
            self.data = initializer()
        super(Worker, self).__init__()

    def log(self, level, message):
        self.q_event.put((
            self.name,
            level,
            message
        ))

    def run(self):
        self.log(Factory.INFO, "Starting")
        while True:
            try:
                task = self.q_in.get(timeout=self.timeout)
                if task is None:
                    self.log(Factory.INFO, "Stopping")
                    self.q_in.task_done()
                    break
                result = None
                try:
                    result = task(self)
                except Exception as err:
                    self.log(Factory.ERROR, err)
                    break
                self.q_out.put(result)
                self.q_in.task_done()
            except Exception as err:
                self.log(Factory.WARNING, "Timeout")


class Task:

    KEY_ARGS = "args"
    KEY_RESULT = "result"
    KEY_WORKER = "worker"

    def __init__(self, args=None, func=None):
        self.args = args
        self.func = func

    def __call__(self, worker):
        if self.func is not None:
            return {
                self.KEY_WORKER: worker.name,
                self.KEY_ARGS: self.args,
                self.KEY_RESULT: self.func(self.args, worker)
            }
        return None


class Factory(threading.Thread):

    VERBOSE = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    PROGRESS = 5

    def __init__(self,
                 timeout=20,
                 verbosity=2,
                 stream=False,
                 callback=None,
                 store_results=True,
                 worker_initializer=None,
                 n_jobs=mp.cpu_count()):

        self.n_jobs = n_jobs
        self.stream = stream
        self.timeout = timeout
        self.callback = callback
        self.verbosity = verbosity
        self.store_results = store_results

        self.q_in = mp.JoinableQueue()
        self.q_out = mp.Queue()
        self.q_event = mp.Queue()
        self.results = []

        self.jobs = [
            Worker(self.q_in, self.q_out, self.q_event, self.timeout, worker_initializer)
            for _ in range(self.n_jobs)
        ]

        self.locked = False
        self.queued = 0
        self.complete = 0

        super(Factory, self).__init__()

    def assign(self, task):
        if not self.locked:
            self.q_in.put(task)
            if task is not None:
                self.queued += 1
        return not self.locked

    def lock(self):
        for _ in range(self.n_jobs):
            self.assign(None)
        self.locked = True

    def header(self, width=22):
        bar = "-" * width
        tasks = "tasks: {}".format(self.queued)
        if self.stream:
            tasks = "streaming"
        jobs = "jobs: {} ({} cpus)".format(self.n_jobs, mp.cpu_count())
        lines = [bar, "starting parallel jobs", bar, tasks, jobs, bar]
        for i in range(len(lines)):
            while len(lines[i]) < width:
                lines[i] += " "
        return "\n".join(map(lambda s: "# {} #".format(s), lines))

    def events(self, last):
        while not self.q_event.empty():
            worker, level, message = self.q_event.get()
            if self.verbosity <= level:
                print("\r", end="")
                for _ in range(len(last)):
                    print(" ", end="")
                print("\r", "{0}:\t{1}".format(worker, message))

    def run(self):
        if not self.stream:
            self.lock()
        start = time.time()
        for job in self.jobs:
            job.start()
        last = ""
        if self.verbosity <= Factory.INFO:
            print(self.header())
        while True:
            if self.locked and self.complete == self.queued:
                break
            try:
                result = self.q_out.get(timeout=self.timeout)
                self.complete += 1
                if self.callback is not None:
                    self.callback(result)
                if self.store_results:
                    self.results.append(result)
                self.events(last)
                if self.verbosity <= Factory.PROGRESS:
                    last = progress(self.complete, self.queued, start, last)
            except Exception as err:
                self.events(last)

        if self.verbosity <= Factory.PROGRESS:
            print()
