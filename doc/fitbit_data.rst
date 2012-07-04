
====================
 FitBit Data Format
====================

:author: Benoît Allard <benoit.allard@gmx.de>
:date: July 4th, 2012

Introduction
============

This document is part of the `libfitbit project`_.

This document aims at describing the data flow between the *fitbit
service* and the *tracker* itself. We will try to abstract as much as
possible the underlying protocol, and focus on the structure of the
data, and the way it is transfered.

Data from this document has been gathered through reverse in depth
analyse of logs of communication between the *tracker* and the
*service*. See `method of operation`_.

The motivation behind this analyse is at first the intelectual process
of

Device Description
==================

The *fitbit tracker* comes with a USB base and a software to be
installed on the host computer. The software will run in *daemon mode*
and request periodically the data from the *tracker*. This is done
through the air, and of course, only if the tracer is near to the
base. The software on the computer is not *tracker* dependent, and
every *tracker* can use any base to synchronise its data with the
fitbit service.

Communication
=============

A dialog between the software and the fitbit service always starts
with a web-request from the software containing the identifier of the
*tracker* found at the moment in the proximity of the base. The fitbit
service then answer with a serie of commands to be sent to the
*tracker*. Once those commands are executed on the *tracker*, the
software sends the raw answers to the fitbit service. This one answers
again with a serie of commands, which are to be executed on the
*tracker*. This go on until the fitbit service has nothing to ask
anymore. This are four round trips most of the time. The software then
put the *tracker* in sleep mode, indicating that he is not interested
in its data for the next 15 minutes.

Method of operation
===================

The ``fitbit_client.py`` script of the original `libfitbit project`_
has been modified to record on disc every transfered bits from and to
the *tracker*. This allow statistical analysis of days of data
transfer.

Communication with the tracker
==============================

The communication with the *tracker* is done through the *base* using
the `ANT protocol`_.

The tracker receives one *opcode* at a time, optionally followed with
*payload*, and sends its *response*. One request from the *fitbit
service* contains from zero to eight requests for the *tracker*. Those
are read, write, erase and a few others yet to be enciphered.

Opcodes
=======

Memory banks
============

bank0
-----

.. note:: Because the timestamp ``0x80000000`` correspond to the 19th
          of January 2038, we might expect the fitbit team to change
          their data format before this date. Until this date, every
          timestamps will not have their MSB set, and the distinction
          between record and timestamps themselves will be easy. 

bank1
-----

bank2
-----

bank3
-----

bank4
-----

bank5
-----

bank6
-----

This bank contains data about **floors climbed**.

Data format
...........

This information is transfered on two bytes, the first byte having its
MSB set. There is one record per minute, and the records are prefixed
by a timestamp on four bytes in LSB format (see also `bank0`_). In
case where more than one minute separates two floor climbing record,
instead of an empty record, a new timestamp will be inserted before
the next climbing record. 

The number of floors climbed during the recorded minute is equal to
the value of the second byte divided by ten. 

Example:
........

::

  4F F0 4A 4B 80 0A 4F F0 4A FF 80 0A 80 14 4F F0 4B EF 80 14 80 14 4F
  F0 4C DF 80 14 

First we have a timestamp 0x4ff04a4b, then a record 0x800a, then a
timestamp 0x4ff04aff, then two records 0x800a and 0x8014, a timestamp
again 0x4ff04bef, two records 0x8014 and 0x8014, a timestamp 4ff04cdf
and one record 0x8014. 

We decode this as follow::

  Time: 2012-07-01 15:02:03: 1 Floors
  Time: 2012-07-01 15:05:03: 1 Floors
  Time: 2012-07-01 15:06:03: 2 Floors
  Time: 2012-07-01 15:09:03: 2 Floors
  Time: 2012-07-01 15:10:03: 2 Floors
  Time: 2012-07-01 15:13:03: 2 Floors


.. _`libfitbit project`: https://github.com/qdot/libfitbit
.. _`ANT protocol`: something here
