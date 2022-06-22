obs-package-update
------------------

``obs-package-update`` is a simple python library for updating packages in the
Open Build Service by wrapping the `osc <https://github.com/openSUSE/osc/>`_
command line client.

This package is intended for easing updating packages automatically from python
without having to mess with osc itself.


Usage
=====

The core functionality is provided by the
:py:class:`~obs_package_update.update.Updater` class, where you have to
implement the :py:meth:`~obs_package_update.update.Updater.add_files`
function. This asynchronous function obtains the destination to the checked out
package and should write the updated sources into that directory. To then
perform the actual update, execute
:py:meth:`~obs_package_update.update.Updater.update_package`.

A very simple (and rather dumb) example for such an updater would be the following:

.. code-block:: python

   class Eraser(Updater):

       async def add_files(self, destination: str) -> List[str]:
           await run_cmd(f"rm -rf {destination}")
           return []

Which could be used as follows in practice (please don't do that):

.. code-block:: python

   eraser = Eraser()
   await eraser.update_package(
       Package(
           project_name="Virtualization:vagrant",
           package_name="vagrant",
       ),
       commit_msg="🔥"
   )
