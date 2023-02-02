from multiprocessing.connection import Client
from array import array

address = ('localhost', 6000)

with Client(address, authkey=b'secret password') as conn:
    while True:
        print(conn.recv())                  # => [2.25, None, 'junk', float]    # => 8
                      