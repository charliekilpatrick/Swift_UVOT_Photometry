.. _inputs:
###########
Input types
###########

The main photometry script (``Swift_photom_host.py``) expects:

1. **Region files** (DS9 format): source circle (e.g. ``sn.reg``) and background
   region (e.g. ``snbkg.reg``). Use ``-s`` and ``-b`` to specify paths; defaults
   are ``sn.reg`` and ``snbkg.reg``.
2. **Image list(s) or ObsID(s):** one or two positional arguments — object list
   (required) and optional template list for template subtraction.

Below are the supported input formats for the image/ObsID part.

====================
Swift Data Structure
====================

The package works on pre-processed files that can be downloaded directly from the `Swift archive <http://www.swift.ac.uk/archive/ql.php>`_. Data from the archive usually come in a single compressed file. Once unpacked, there will be a folder for each ObsID queried. An ``ObsID`` is an 11 digits unique number, composed by a 8 digits ``Target_ID`` and a 3 digits sequential ``Obs_segment``. As the name suggests, ``Target_IDs`` are unique to each Swift target (although one target can have multiple ``Target_IDs``), while the ``Obs_segment`` increase with the amount of data collected for a target. 

Each ``ObsID`` folder will have a structure similar to this:

.. code-block::

   [ObsID]
     |--auxil
     |--xrt
     |--uvot
       |--hk
       |--products
       |--images
         |--sw[ObsID]u[filter1]_ex.img.gz
         |--sw[ObsID]u[filter1]_rw.img.gz
         |--sw[ObsID]u[filter1]_sk.img.gz
         |--[...]
         |--sw[ObsID]u[filterN]_ex.img.gz
         |--sw[ObsID]u[filterN]_rw.img.gz
         |--sw[ObsID]u[filterN]_sk.img.gz
         
depending what files you downloaded from the Swift archive. The ``SwiftPhotom`` package works on the ``*_sk.img.gz`` files, so the User will have to isolate them. This can done in 2 ways, manually, or by providing the ``Target_ID``.

*WARNING - although it is not necessary to keep the tree structure described above, the scripts will work only on files that ends with ``_sk.img.gz`` (or ``_sk.img``), so be aware of this if the User plans to rename them.*

=========
Target_ID
=========

The ``Target_ID`` (8 digits) can be provided as the object input. Example:

.. code-block:: bash

	Swift_photom_host.py 13612 -s sn.reg -b snbkg.reg

The script searches the working directory and subdirectories for files matching
``sw[Target_ID]*_sk.img.gz`` (or ``_sk.img``). Leading zeros are added
automatically (e.g. ``13612`` or ``00013612``). Do not include the ``Obs_segment``
(11-digit ObsID); file renaming may prevent the script from finding the files. 

=============
List of files
=============

The User can list all the ``_sk.img.gz`` files into a text file, and use the name of this latter file as the input to the script. If the files are not in the current working directory, the relative path must be provided (or alternatively, the full path). If the User is running the script from a top folder with all the ObsID folder inside, and the Swift default tree structure is maintained, all the correct files can be quickly included in a text file by 

.. code-block:: bash

	ls */uvot/image/sw*_sk.img.gz > obj.lst


then all your images will be listed inside the ``obj.lst`` text file (the name and extension here are not important), which will look something like this

.. code-block::

	00013612001/uvot/image/sw00013612001uw1_sk.img.gz
    00013612001/uvot/image/sw00013612001uw2_sk.img.gz
    03105174001/uvot/image/sw03105174001uuu_sk.img.gz
    03105174001/uvot/image/sw03105174001uw1_sk.img.gz



Run the script with the list file and region files:

.. code-block:: bash

	Swift_photom_host.py obj.lst -s sn.reg -b snbkg.reg

For template subtraction, add a second list: ``Swift_photom_host.py obj.lst templ.lst -s sn.reg -b snbkg.reg``.

This method is more versatile than using the ``Target_ID``, as it allows selecting
epochs and filters by editing the list. Files can be renamed as long as the
``*_sk.img.gz`` (or ``*_sk.img``) suffix is kept.


===========================
List of files and Target_ID
===========================

The list file can also contain multiple ``Target_IDs``, or a combination of files and ``Target_IDs``. The following list file is a valid input.

.. code-block::

	00013612001/uvot/image/sw00013612001uw1_sk.img.gz
    00013612001/uvot/image/sw00013612001uw2_sk.img.gz
    3105174