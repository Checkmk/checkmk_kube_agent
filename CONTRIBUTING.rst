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

1. Clone the `checkmk_kube_agent` repo.
2. Install your local copy into a virtualenv in editable mode, e.g.::

    $ cd checkmk_kube_agent/
    $ python3 -m venv /path/to/new/virtual/environment
    $ pip3 install -e .

3. Create a branch for local development::

    $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

4. When you're done making changes, check that your changes pass the tests::

    $ pytest

   You can also run individual make targets from the repository root. See all
   available targets and what they do by running `make help`.

5. Commit and push your changes::

    $ git add .
    $ git commit -m "Your detailed description of your changes."
    $ git push origin HEAD:<remote>

6. Follow the instructions to sign the CLA_ as asked by the bot.

.. _CLA: https://github.com/checkmk/checkmk/blob/master/doc/cla/cla_readme.md
