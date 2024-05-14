#!/bin/python3
#Script to stress CPU / RAM and disk

import os
import argparse
from multiprocessing import Pool, cpu_count, freeze_support, set_start_method
from threading import Event
import signal
import sys
import tempfile

#Pool functions
#CPU stress
def f(x):
  while True:
    x*x

#Disk stress
def d(x):
  block_to_write='x' * 1048576
  while True:
    filehandle=tempfile.NamedTemporaryFile(dir=x[1],mode='w+')
    for _ in range(x[0]):
      filehandle.write(block_to_write)
    filehandle.seek(0)
    for _ in range(x[0]):
      content = filehandle.read(1048576)
    filehandle.close()
    del content
    del filehandle
       
#Main function
if __name__ == '__main__':
    freeze_support()
    set_start_method('spawn')
    
    #Read arguments
    parser = argparse.ArgumentParser(description='Script to run very simple stress tests')
    parser.add_argument('--cpu', dest='cpus', type=int, default=1, help='number of CPU thread to stress (default: 1). Use -1 to stress all the CPUs')
    parser.add_argument('--time', dest='time', type=int, default=20, help='Time for the test in seconds (default: 20)')
    parser.add_argument('--ram', dest='rams', type=int, default=0, help='Allocate RAM blocks of 1MB (default is 0).')
    parser.add_argument('--ramp', dest='ramp', type=float, default=0, help='Allocate a given percent (in numbers between 0 and 1) of the total RAM (will override --ram command)')
    parser.add_argument('--disk', dest='disk', type=int, default=0, help='Start a disk read/write workes (default is 0)')
    parser.add_argument('--disk-path', dest='diskp', type=str, action='append', help='disk read/write path to use (default is /tmp/). Multiple paths can be set.')
    parser.add_argument('--disk-blocks', dest='diskb', type=int, default=1, help='Disk read/write for a given number of 1MB blocks per worker')

    args = parser.parse_args()
    if args.diskp is None:
      args.diskp=[tempfile.gettempdir()]

    #Signal wrapper to stop tests
    global poolc
    global poold
    global sleep
    poolc = None #workers for CPU stress
    poold = None #workers for disk stress
    sleep = Event() #event is used to have an interruptable sleep
    def exit_chld(x,y):
      global poolc
      global poold
      global sleep
      if poolc is not None:
        poolc.terminate()
      if poold is not None:
        for pooldisk in poold:
          pooldisk.terminate()
      sleep.set()
    signal.signal(signal.SIGINT, exit_chld)

    #Determining total memory for linux and windows
    def memtotal():
      if sys.platform=="win32":
        process = os.popen('wmic memorychip get capacity')
        result = process.read()
        process.close()
        totalMem = 0
        for m in result.split('\n'):
          try:
            totalMem += int(m.strip(' \r\n'))
          except ValueError:
            continue
        return totalMem
      else:
        return os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')

    if args.rams != 0 or args.ramp != 0:
      if args.rams < 0:
        args.rams = int(memtotal() / 1024 / 1024 *0.9)
      if args.ramp > 0:
        args.rams = int(memtotal() / 1024 / 1024 * args.ramp)

      print("Allocating %d blocks of 1MB of RAM" % args.rams)
      ramblock=[]
      for a in range(args.rams):
        ramblock.append('x' * 1048576)

    if args.cpus != 0:
      if args.cpus < 0:
        args.cpus=cpu_count()

      processes=args.cpus
      print("Running load on CPU...\nUtilizing %d cores" % processes)

      poolc = Pool(processes)
      poolc.map_async(f, range(processes))

    if args.disk != 0:
      poold=[]
      for diskpath in args.diskp:
        print("Spawing %d runners writing/reading %dx1MB blocks on %s" % (args.disk, args.diskb,diskpath))

        pooldpool = Pool(args.disk)
        pooldpool.map_async(d, [[args.diskb,diskpath]]*args.disk)
        poold.append(pooldpool)

    #Exit after seconds
    print("Working for %d seconds" % args.time)
    sleep.wait(args.time)
    exit_chld(0,0)
    sys.exit(0)
