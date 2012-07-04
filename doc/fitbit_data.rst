
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
of deciphering data, but as well the will of having full control about
a tracker I wear day and night, and by such, data about my lifestyle.

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

An opcode is **always** seven bytes long. most of the time, only the
first few bytes are not zero.

The memory read is not the same as the memory written, even if the
*index* can be the same.

Get Device Information
----------------------

:opcode: [0x24, 0 (6 times)]
:response: [serial, hardrev, bslmaj, bslmin, appmaj, appmin, bslon,
  onbase]

The response first contains the serial number of the tracker on five
bytes, then the hardware revision, the BSL major version and minor
version, the App major version and minor version, if the BSL mode is
ON, and if the tracker is plugged on the base. Except the serial
number, every other information is coded on one byte.

Read memory
-----------

:opcode: [0x22, index, 0 (5 times)]
:response: data

Where *index* is the index of the memory bank requested.

The response is the content of the memory and its meaning differs from
memory to memory.

Write memory
------------

:opcode: [0x23, index, datalen, 0 (4 times) ]
:payload: data
:response: [0x41, 0 (6 times)]

Where *index* is the index of the memory to be written, and *datalen* the
length of the payload.

The content of the payload is index dependant.

Erase memory
------------

:opcode: [0x25, index, timestamp, 0]
:response: [0x41, 0 (6 times)]

Where *index* is the index of the memory bank to be erased, and
*timestamp* (on four bytes, MSB) is the date until which the data
should be erased.

Read Memory banks
=================

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

This bank contains data, but a request to read it is never sent from
the *fitbit service*.

Data Format
...........

This bank always contains thirty bytes. The meaning of only the first
ones is known.

The first five bytes contains the serial number, followed by the
hardware revision.

Example
.......

::

  01 02 03 04 05 0C 08 10 08 01 08 00 00 FF D8 00 06 A9 1D 9E 43 6A 3A
  63 48 83 BA 6E 1D 64

Which can be decoded as follow::

  Serial: 0102030405
  Hardware revision: 12

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

This can be decoded as follow::

  Time: 2012-07-01 15:02:03: 1 Floors
  Time: 2012-07-01 15:05:03: 1 Floors
  Time: 2012-07-01 15:06:03: 2 Floors
  Time: 2012-07-01 15:09:03: 2 Floors
  Time: 2012-07-01 15:10:03: 2 Floors
  Time: 2012-07-01 15:13:03: 2 Floors

bank7
-----

This bank is never requested from the *fitbit service*.

Its content is empty.

Write memory banks
==================

bank0
-----

This bank always receives 64 bytes.

bank1
-----

This bank always receive 16 bytes.

.. _`libfitbit project`: https://github.com/qdot/libfitbit
.. _`ANT protocol`: something here
