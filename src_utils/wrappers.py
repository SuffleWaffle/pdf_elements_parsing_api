# >>>> </> STANDARD IMPORTS </>
# >>>> ********************************************************************************
import logging
from functools import wraps
from typing import Callable
# import multiprocessing
# from multiprocessing import Process, Queue, Pipe
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
from pathos.helpers import mp as pathos_mp
from pathos.multiprocessing import ProcessPool
# >>>> ********************************************************************************

# >>>> </> LOCAL IMPORTS </>
# >>>> ********************************************************************************
import settings
from src_logging import log_config
# >>>> ********************************************************************************

# ________________________________________________________________________________
# --- INIT CONFIG - LOGGER SETUP ---
logger = log_config.setup_logger(__name__, logging_level=logging.DEBUG)


# --- PRODUCTION READY ---
def parallel_task_with_timeout(func_obj: Callable,
                               proc_timeout: int = settings.PARALLEL_TASK_PROC_TIMEOUT,
                               **kwargs):
    """ --- PRODUCTION READY ---\n
        - A decorator function that wraps a parameter function in a separate parallel process.
        - Parallel process runs with timeout (user-defined or default settings.NN_PROC_TIMEOUT value).

        Args:
            func_obj(Callable): Function to be processed in parallel.
            proc_timeout(int): Number of seconds to wait before the process is terminated.
            **kwargs: Keyword arguments to be passed to the function

        Returns:
            Function execution result or None if the process timed out.
    """

    pool = ProcessPool(nodes=1)
    result = pool.apipe(func_obj, **kwargs)

    try:
        return result.get(timeout=proc_timeout)

    except pathos_mp.TimeoutError:
        logger.warning(f">>> Process - PID: {result.pool[0].pid}\n"
                       f">>> Timed out after {proc_timeout} seconds.")
        pool.terminate()
        return None


# def parallel_task_with_timeout(func_obj: Callable,
#                                func_args: tuple,
#                                proc_timeout: int = settings.NN_PROC_TIMEOUT):
#     """ --- PRODUCTION READY ---\n
#         - A decorator function that wraps a parameter function in a separate parallel process.
#         - Parallel process runs with a chosen timeout.
#
#         Args:
#             func_obj(Callable): Function to be processed in parallel.
#             func_args(tuple): Function arguments.
#             proc_timeout(int): Number of seconds to wait before the process is terminated.
#
#         Returns:
#             Function execution result or None if the process timed out.
#     """
#
#     pool = ProcessPool(nodes=1)
#     result = pool.apipe(func_obj, *func_args)
#
#     try:
#         return result.get(timeout=proc_timeout)
#
#     except pathos_mp.TimeoutError:
#         logger.warning(f"--- Process - PID: {result.pool[0].pid} "
#                        f"--- Timed out after {proc_timeout} seconds.")
#         pool.terminate()
#         return None


# --- PRODUCTION READY ---
def parallel_task_v1(func: Callable):
    """ --- PRODUCTION READY ---\n

        A decorator that wraps a function in a separate multiprocessing.Process object and
        runs it with a fixed settings.NN_PROC_TIMEOUT timeout.

        Returns:
            wrapper_function: A decorator function that wraps the decorated function.
    """

    @wraps(func)
    def wrapper_function(*args, **kwargs):
        process_timeout: int = settings.NN_PROC_TIMEOUT

        pool = ProcessPool(nodes=1)
        result = pool.apipe(func, *args, **kwargs)

        try:
            return result.get(timeout=process_timeout)
        except pathos_mp.TimeoutError:
            logger.warning(f"--- Process - PID: {result.pool[0].pid} "
                           f"--- Timed out after {process_timeout} seconds.")
            pool.terminate()
            return None

    return wrapper_function

# TODO: Fix in the future updates.
# TODO: The parallel_task_with_timeout Decorator Func with Decorator Arg is not picklable (PicklingError)
# --- __NOT__ PRODUCTION READY ---
# def parallel_task_v1(func: Callable):
#     """ --- __NOT__ PRODUCTION READY ---\n
#
#         A decorator that wraps a function in a separate multiprocessing.Process object and
#         runs it with a fixed settings.NN_PROC_TIMEOUT timeout.
#
#         Returns:
#             wrapper_function: A decorator function that wraps the decorated function.
#     """
#     # @wraps(func)
#     def wrapper_function(*args, **kwargs):
#         process_timeout: int = settings.NN_PROC_TIMEOUT
#
#         result_queue: Queue = multiprocessing.Queue()
#
#         process: Process = multiprocessing.Process(target=func,
#                                                    args=(*args, result_queue),
#                                                    kwargs=kwargs,
#                                                    daemon=True)
#
#         process.start()
#         process.join(process_timeout)
#
#         if process.is_alive():
#             logger.warning(f"--- Process - PID: {process.pid} - Timed out after {process_timeout} seconds.")
#             process.terminate()
#             return None
#
#         if not result_queue.empty():
#             return result_queue.get()
#
#         return None
#     return wrapper_function


# TODO: Fix in the future updates.
# TODO: The parallel_task_with_timeout Decorator Func with Decorator Arg is not picklable (PicklingError)
# --- __NOT__ PRODUCTION READY ---
# def parallel_task_with_timeout(proc_timeout_seconds: int = settings.NN_PROC_TIMEOUT):
#     """ --- __NOT__ PRODUCTION READY ---\n
#         A decorator that wraps a function in a separate multiprocessing.Process object and
#         runs it with a chosen timeout.
#
#         Args:
#             proc_timeout_seconds(int): Number of seconds to wait before terminating the process.
#
#         Returns:
#             decorator: A decorator function that wraps the algorithm function.
#     """
#
#     def decorator(func: Callable):
#         @wraps(func)
#         def wrapper_function(*args, **kwargs):
#             result_queue: Queue = multiprocessing.Queue()
#
#             process: Process = multiprocessing.Process(target=func,
#                                                        args=(*args, result_queue),
#                                                        kwargs=kwargs,
#                                                        daemon=True)
#             # # Define a new target function to capture the function's output and put it into the Queue
#             # def target_func(f, args, kwargs, result_queue):
#             #     result_queue.put(f(*args, **kwargs))
#             # process: Process = multiprocessing.Process(target=target_func,
#             #                                            args=(func, args, kwargs, result_queue))
#
#             process.start()
#             process.join(proc_timeout_seconds)
#
#             if process.is_alive():
#                 print(f"Process timed out after {proc_timeout_seconds} seconds.")
#                 process.terminate()
#                 return None
#
#             if not result_queue.empty():
#                 return result_queue.get()
#
#             return None
#         return wrapper_function
#     return decorator


# def child_process(func):
#     """Makes the function run as a separate process. Needed for
#     keras classifier with gridsearchcv to work on multiple datasets"""
#     def wrapper(*args, **kwargs):
#         def worker(conn, func, args, kwargs):
#             conn.send(func(*args, **kwargs))
#             conn.close()
#         parent_conn, child_conn = Pipe()
#         p = Process(target=worker, args=(child_conn, func, args, kwargs))
#         p.start()
#         ret = parent_conn.recv()
#         p.join()
#         return ret
#     return wrapper


# def task_with_timeout_and_cancellation(timeout_seconds: int):
#     def decorator(func: Callable):
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             # Use a Manager dict to allow communication between processes.
#             manager = Manager()
#             result_dict = manager.dict()
#             error_dict = manager.dict()
#
#             # Define a new function that includes error handling and stores the result in result_dict.
#             def func_wrapper(*args, **kwargs):
#                 try:
#                     result = func(*args, **kwargs)
#                     result_dict['result'] = result
#                 except Exception as e:
#                     error_dict['error'] = str(e)
#
#             process = Process(target=func_wrapper, args=args, kwargs=kwargs)
#             process.start()
#
#             process.join(timeout=timeout_seconds)
#
#             if process.is_alive():
#                 # The process did not complete within timeout_seconds. Terminate it.
#                 os.kill(process.pid, signal.SIGTERM)  # send sigterm signal
#                 process.join()  # wait for the process to terminate
#                 return {"error": f"Task timed out after {timeout_seconds} seconds"}
#
#             if 'error' in error_dict:
#                 return {"error": error_dict['error']}
#
#             return result_dict['result']
#
#         return wrapper
#
#     return decorator


# def parallel_task_with_timeout(proc_timeout: int = settings.NN_PROC_TIMEOUT):
#     """ --- PRODUCTION READY ---\n
#         - A decorator function that wraps a parameter function in a separate parallel process.
#         - Parallel process runs with a chosen timeout.
#
#         Args:
#             func_obj(Callable): Function to be processed in parallel.
#             proc_timeout(int): Number of seconds to wait before the process is terminated.
#
#         Returns:
#             decorator: A decorator function that wraps the real function in parameter.
#     """
#
#     def decorator(func_obj: Callable):
#         @wraps(func_obj)
#         def wrapper_function(*args, **kwargs):
#             pool = ProcessPool(nodes=1)
#             result = pool.apipe(func_obj, *args, **kwargs)
#
#             try:
#                 return result.get(timeout=proc_timeout)
#
#             except pathos_mp.TimeoutError:
#                 logger.warning(f"--- Process - PID: {result.pool[0].pid} "
#                                f"--- Timed out after {proc_timeout} seconds.")
#                 pool.terminate()
#                 return None
#
#         return wrapper_function
#
#     return decorator
