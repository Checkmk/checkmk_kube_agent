.. highlight:: shell

============
Contributing
============

We currently do not accept pull requests because we do not have the capacity to
handle them, although this may change in the future.

Thank you for your understanding!

Get Started!
------------

Here's how to set up `checkmk_kube_agent` for local development.

Note that we target Python 3.14. You can set this up using, for example,
`pyenv`. The rest of these instructions assume you have this version.

1. Clone the `checkmk_kube_agent` repo.
2. Install your local copy into a virtualenv in editable mode, e.g.::

    $ cd checkmk_kube_agent/
    $ python3 -m venv /path/to/new/virtual/environment
    $ source /path/to/new/virtual/environment/bin/activate
    $ pip3 install -e .
    $ pip3 install -r requirements_dev.txt -r requirements_build.txt -r requirements_test.txt

3. When you're done making changes, check that your changes pass the tests::

    $ make test-unit

   You can also run individual make targets from the repository root. See all
   available targets and what they do by running ``make help``.

4. Verify that your commits is ready to be submitted::

    $ make gerrit-tests

   This command will run all targets, which are required to pass. A pull request cannot be approved
   until all errors are addressed.

5. Integration tests

   If you have ``kind`` on your system, you can run the integration tests like so::

    $ make kind-integration

   This will create a temporary Kind cluster, install the cluster collector in it,
   and run the integration tests against it. It will tear down the cluster afterwards
   iff the tests pass. If they fail, it will leave it up, for debugging.

   You can also use this command if you use kind for your normal dev environment
   and want to see your changes deployed. For example::

    $ make kind   # optionally with KIND_CLUSTER_NAME=foo at the end if your cluster isn't named ``kind``

6. Create the pull request!

7. Follow the instructions to sign the CLA_ as asked by the bot.

.. _CLA: https://github.com/checkmk/checkmk/blob/master/doc/cla/cla_readme.md
