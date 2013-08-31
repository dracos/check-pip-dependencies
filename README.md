check-pip-dependencies
======================

A script that does the same as `pip install --no-install` but also
highlights dependency conflict issues currently not otherwise caught.

The Problem
-----------

pip doesn't currently catch some obvious dependency issues, due to its
'whichever comes first' dependency downloading.

Consider the following example `requirements.txt` file, on a computer that
already has python-dateutil version 1.4.1 installed:

    python-dateutil
    django-tastypie
    django-app-1
    django-app-2

Note these packages have the following dependencies:

* django-tastypie requires python-dateutil >= 1.5, != 2.0
* django-app-1 requires Django >= 1.4
* django-app-2 requires Django >= 1.3, < 1.5

If you were to simply run `pip install -r requirements.txt` then the
following would be installed/ not touched:

    python-dateutil==1.4.1
    django-tastypie==0.10.0
    django-app-1==1.0.0
    django-app-2==1.0.0
    Django==1.5.2

Which conflicts both in django-tastypie (incompatible python-dateutil version)
and django-app-2 (incompatible Django version).

The Solution
------------

This script should be run  in a virtualenv, providing a requirements file as
the only argument. It outputs any conflicts that it finds; its output on the
above `requirements.txt` file (wrapped for clarity) is:

    (test)$ python check-pip-dependencies.py requirements.txt
    python-dateutil>=1.5,!=2.0 (from django-tastypie->-r requirements.txt (line 2))
        conflicts with installed python-dateutil 1.4.1
    django>=1.3,<1.5 (from django-app-2->-r requirements.txt (line 4)),
        but pip will install version 1.5.2 from Django>=1.4
        (from django-app-1->-r requirements.txt (line 3))

You can then adjust your `requirements.txt` file to work around these issues
(in this case, you could specify the version of python-dateutil to match
django-tastypie, and specify a Django version that fits, presumably 1.4.x).

Note that as this basically performs a `pip install --no-install -r <file>`,
a further `pip install -r <file>` will not have to redownload the packages.

There is a `--verbose` option to output the packages being downloaded
(but not installed) by pip as it goes.
