import multiprocessing
import uuid
from functools import partial
from time import sleep

from taipy.configuration import ConfigurationManager
from taipy.data.entity import EmbeddedDataSourceEntity
from taipy.data.scope import Scope
from taipy.task import TaskEntity
from taipy.task.scheduler import TaskScheduler


def mult(nb1: float, nb2: float):
    return nb1 * nb2


def lock_mult(lock, nb1: float, nb2: float):
    with lock:
        return mult(nb1, nb2)


def test_scheduled_task():
    task_scheduler = TaskScheduler()
    task = _create_task_entity(mult)

    task_scheduler.submit(task)
    assert task.output["output1"].get(None) == 42


def test_scheduled_task_that_return_multiple_outputs():
    def return_tuple(nb1, nb2):
        return mult(nb1, nb2), mult(nb1, nb2) / 2

    def return_list(nb1, nb2):
        return [mult(nb1, nb2), mult(nb1, nb2) / 2]

    task_scheduler = TaskScheduler()

    with_tuple = _create_task_entity(return_tuple, 2)
    with_list = _create_task_entity(return_list, 2)

    task_scheduler.submit(with_tuple)
    task_scheduler.submit(with_list)

    assert with_tuple.output["output0"].get(None) == with_list.output["output0"].get(None) == 42
    assert with_tuple.output["output1"].get(None) == with_list.output["output1"].get(None) == 21


def test_un_writing_data_source_due_difference_between_nb_results_and_nb_data_sources():
    task_scheduler = TaskScheduler()
    task = _create_task_entity(lambda nb1, nb2: (mult(nb1, nb2), mult(nb1, nb2) / 2))

    task_scheduler.submit(task)
    assert task.output["output0"].get(None) == 0


def test_error_during_writing_data_source_dont_stop_writing_on_other_data_source():
    task_scheduler = TaskScheduler()

    task = _create_task_entity(lambda nb1, nb2: (42, 21), 2)
    task.output["output0"].write = None
    task_scheduler.submit(task)

    assert task.output["output0"].get(None) == 0
    assert task.output["output1"].get(None) == 21


def test_scheduled_task_in_parallel():
    ConfigurationManager.task_scheduler_configuration.parallel_execution = True
    m = multiprocessing.Manager()
    lock = m.Lock()

    task_scheduler = TaskScheduler()
    task = _create_task_entity(partial(lock_mult, lock))

    with lock:
        task_scheduler.submit(task)
        assert task.output["output0"].get(None) == 0

    sleep(1)
    assert task.output["output0"].get(None) == 42


def test_scheduled_task_multithreading_multiple_task():
    ConfigurationManager.task_scheduler_configuration.parallel_execution = True

    task_scheduler = TaskScheduler()

    m = multiprocessing.Manager()
    lock_1 = m.Lock()
    lock_2 = m.Lock()

    task_1 = _create_task_entity(partial(lock_mult, lock_1))
    task_2 = _create_task_entity(partial(lock_mult, lock_2))

    with lock_1:
        with lock_2:
            task_scheduler.submit(task_1)
            task_scheduler.submit(task_2)

            assert task_1.output["output0"].get(None) == 0
            assert task_2.output["output0"].get(None) == 0

        sleep(1)
        assert task_1.output["output0"].get(None) == 0
        assert task_2.output["output0"].get(None) == 42

    sleep(1)
    assert task_1.output["output0"].get(None) == 42
    assert task_2.output["output0"].get(None) == 42


def _create_task_entity(function, nb_outputs=1):
    task_name = str(uuid.uuid4())
    input_ds = [
        EmbeddedDataSourceEntity.create("input1", Scope.PIPELINE, data=21),
        EmbeddedDataSourceEntity.create("input2", Scope.PIPELINE, data=2),
    ]
    output_ds = [
        EmbeddedDataSourceEntity.create(f"output{i}", Scope.PIPELINE, data=0)
        for i in range(nb_outputs)
    ]
    return TaskEntity(
        task_name,
        input=input_ds,
        function=function,
        output=output_ds,
    )
