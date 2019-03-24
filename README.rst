===========
forkpy
===========

**forkpy** provides a framework for multiprocessing in Python. Typical usage
might look like this:

.. code-block:: python

    from forkpy import Factory, Task

    def target_function(args, worker):
        a, b = args
        return a + b

    factory = Factory()
    for a in range(100):
        for b in range(100):
            args = (a, b)
            factory.assign(Task(args, target_function))

    factory.start()
    factory.join()

    print(factory.results)

Sources
-------

See the project on `GitHub <https://github.com/ychalier/forkpy>`_.
