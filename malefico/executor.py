from __future__ import absolute_import, division, print_function

import logging
import multiprocessing
import sys
import threading
import traceback
from functools import partial

from  malefico.core.executor import MesosExecutorDriver
from  malefico.core.interface import Executor
from  malefico.messages import TaskStatus,PythonTaskStatus,TaskInfo,PythonTask
from  malefico.utils import Interruptable

log = logging.getLogger(__name__)

class ThreadExecutor(Executor):
    def __init__(self):
        self.tasks = {}

    def is_idle(self):
        return not len(self.tasks)

    def run(self, driver, task):

        status = PythonTaskStatus(task_id=task.task_id, state='TASK_RUNNING')
        driver.update(status)
        log.info('Sent TASK_RUNNING status update')
        try:
            log.info('Executing task...')
            result = task()
        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb = ''.join(traceback.format_tb(exc_traceback))
            log.exception('Task errored with {}'.format(e))
            status = PythonTaskStatus(task_id=task.task_id, state='TASK_FAILED',data=(tb,e),message=repr(e))
            driver.update(status)
            log.info('Sent TASK_RUNNING status update')
        else:
            status = PythonTaskStatus(task_id=task.task_id, state='TASK_FINISHED', data=result)
            driver.update(status)
            log.info('Sent TASK_FINISHED status update')
        finally:
            del self.tasks[task.task_id]
            if self.is_idle():  # no more tasks left
                log.info('Executor stops due to no more executing '
                             'tasks left')
                driver.stop()

    def on_launch(self, driver, task):
        log.info("Stuff")
        log.info(task)
        task = PythonTask(**task)
        thread = threading.Thread(target=self.run, args=(driver, task))
        self.tasks[task.task_id] = thread  # track tasks runned by this executor
        thread.start()

    def on_kill(self, driver, task_id):
        driver.stop()

    def on_shutdown(self, driver):
        driver.stop()


class ProcessExecutor(ThreadExecutor):
    def on_launch(self, driver, task):
        log.info("Stuff")
        log.info(task)
        task = PythonTask(**task)
        process = multiprocessing.Process(target=self.run, args=(driver, task))
        self.tasks[task.task_id] = process  # track tasks runned by this executor
        process.start()

    def on_kill(self, driver, task_id):

        self.tasks[task_id].terminate()
        del self.tasks[task_id]

        if self.is_idle():  # no more tasks left
            log.info('Executor stops due to no more executing '
                         'tasks left')
            driver.stop()


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    driver = MesosExecutorDriver(ThreadExecutor())
    driver.start(block=True)