import unittest

from lab1.ir_system.presentation.gui.tasks import TaskRunner


class FakeScheduler:
    def __init__(self):
        self.callbacks = {}
        self.counter = 0

    def after(self, milliseconds, callback):
        self.counter += 1
        identifier = str(self.counter)
        self.callbacks[identifier] = callback
        return identifier

    def after_cancel(self, identifier):
        del self.callbacks[identifier]

    def tick(self):
        callbacks, self.callbacks = self.callbacks, {}
        for callback in callbacks.values():
            callback()


class TaskTests(unittest.TestCase):
    def test_success_is_delivered_by_scheduler(self):
        scheduler, jobs, results = FakeScheduler(), [], []
        runner = TaskRunner(scheduler, jobs.append)
        self.assertTrue(runner.start(lambda: 7, results.append, self.fail))
        self.assertFalse(runner.start(lambda: 8, results.append, self.fail))
        jobs[0]()
        self.assertEqual(results, [])
        scheduler.tick()
        self.assertEqual(results, [7])
        self.assertFalse(runner.running)

    def test_failure_is_delivered_by_scheduler(self):
        scheduler, jobs, errors = FakeScheduler(), [], []
        runner = TaskRunner(scheduler, jobs.append)

        def fail_job():
            raise OSError("offline")

        runner.start(fail_job, self.fail, errors.append)
        jobs[0]()
        scheduler.tick()
        self.assertEqual(str(errors[0]), "offline")
        self.assertFalse(runner.running)

    def test_close_cancels_polling_and_discards_late_result(self):
        scheduler, jobs, results = FakeScheduler(), [], []
        runner = TaskRunner(scheduler, jobs.append)
        runner.start(lambda: 7, results.append, self.fail)
        runner.close()
        jobs[0]()
        scheduler.tick()
        self.assertEqual(results, [])
        self.assertFalse(runner.start(lambda: 8, results.append, self.fail))
