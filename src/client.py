import socket
import threading
from queue import Queue
import argparse


class Client(threading.Thread):
    def __init__(self,
                 server_address: str,
                 server_port: int,
                 num_threads: int,
                 filename: str) -> None:
        if not isinstance(server_address, str) or not server_address:
            raise ValueError('Invalid server address: ' +
                             'Must be a non-empty string')

        if not isinstance(server_port, int) or not 0 <= server_port <= 65535:
            raise ValueError('Invalid server port: ' +
                             'Must be an integer between 0 and 65535')

        if not isinstance(num_threads, int) or num_threads < 1:
            raise ValueError('num_threads must be an integer greater than 0')
        self._server_endpoint = (server_address, server_port)
        self.num_threads = num_threads
        self.filename = filename
        self.urls = None
        self.queue_urls: Queue = Queue(maxsize=num_threads*2)
        self._lock = threading.Lock()

        super().__init__(name='client_master')

    def run(self):
        load_th = threading.Thread(
            name='client_loader_links',
            target=self.load_links,
        )
        load_th.start()

        self._server_call()

    def load_links(self):
        with open(self.filename, encoding='utf-8') as file:
            for line in file:
                self.queue_urls.put(line.rstrip())

        self.queue_urls.put(None)

    def _server_call(self):
        threads = [
            threading.Thread(
                name=f"client_worker-{i}",
                target=self._worker_proc,
            )
            for i in range(self.num_threads)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

    def _worker_proc(self):
        while True:
            url = self.queue_urls.get()
            if url is None:
                self.queue_urls.put(url)
                break

            with socket.socket(socket.AF_INET,
                               socket.SOCK_STREAM) as client_socket:
                try:
                    client_socket.connect(self._server_endpoint)
                    client_socket.sendall(url.encode(encoding='utf-8'))
                    response = client_socket.recv(1024).decode(
                        encoding='unicode-escape'
                    )
                except socket.error as error:
                    with self._lock:
                        print(f"Socket error: {error}")
                else:
                    with self._lock:
                        print(f'{url} : {response}')


def get_prg_args():
    parser = argparse.ArgumentParser(description="Client")
    parser.add_argument("num_threads", type=int, help="Number of threads")
    parser.add_argument("urls_file", type=str, help="File with URLs")

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    HOST = '127.0.0.1'
    PORT = 8081

    launch_args = get_prg_args()

    client = Client(
        server_address=HOST,
        server_port=PORT,
        num_threads=launch_args.num_threads,
        filename=launch_args.urls_file,
    )
    client.start()
