===========
Pyrall
===========

Pyrall provides a framework for multiprocessing in Python. Typical usage
often looks like this::

    from pyrall import Factor, Task

    factory = Factory()
    for _ in range(100):
        factory.assign(Task())

    factory.start()
    factory.join()

    print(factory.results)
