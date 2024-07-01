import socket
import threading
import argparse
import json
from collections import Counter
from queue import Queue
import time
from bs4 import BeautifulSoup
import requests


class Server(threading.Thread):
    message_processed = 0

    def __init__(self,
                 server_address: str,
                 server_port: int,
                 num_workers: int,
                 num_top_words: int) -> None:
        if not isinstance(server_address, str) or not server_address:
            raise ValueError('Invalid address: ' +
                             'Must be a non-empty string')

        if not isinstance(server_port, int) or not 0 <= server_port <= 65535:
            raise ValueError('Invalid port: ' +
                             'Must be an integer between 0 and 65535')

        if num_workers < 1:
            raise ValueError("The number of workers must be greater than 0")
        if num_top_words < 1:
            raise ValueError("The number of words must be greater than 0")

        self._server_endpoint = (server_address, server_port)
        self.num_workers: int = num_workers
        self.num_top_words: int = num_top_words
        self.processed_message_cnt: int = 0
        self._queue_connect: Queue = Queue()
        self._print_lock = threading.Lock()
        self._keep_working = True
        self._end_accept_connections = threading.Event()

        super().__init__(name='server_master')

    def run(self) -> None:
        # Запуск потоков обаботчиков
        self._start_workers()

        with socket.socket(socket.AF_INET,
                           socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(self._server_endpoint)
            server_socket.listen()
            server_socket.settimeout(1)

            # Наполнение очереди входящими соединенями от клиентов
            while self._keep_working:
                try:
                    conn, addr = server_socket.accept()
                except TimeoutError:
                    pass
                else:
                    self._queue_connect.put((conn, addr))
            self._end_accept_connections.set()

    def stop(self):
        self._keep_working = False

        # Ожидаем пока закончится вся работа с соединениями
        self._end_accept_connections.wait()
        # Останавливаем воркеров, говоря о конце очереди соединений
        for _ in range(self.num_workers):
            self._queue_connect.put((None, None))

        # Ожидание пока все принятые соединения будут обработаны
        self._queue_connect.join()

    def _start_workers(self) -> None:
        threads = [
            threading.Thread(
                name=f'server_worker-{i}',
                target=self._worker_proc,
            )
            for i in range(self.num_workers)
        ]
        for thread in threads:
            thread.start()

    def _worker_proc(self):
        while True:
            # Получает из очереди соединение
            conn, _ = self._queue_connect.get()
            if conn is None:
                self._queue_connect.task_done()
                break

            with conn:
                while True:
                    try:
                        url = conn.recv(1024).decode()
                        if not url:
                            break
                        result = json.dumps(self._request_data(url))
                        conn.sendall(result.encode(encoding='utf-8'))
                    except socket.error as error:
                        with self._print_lock:
                            print(f"Socket error: {error}")
                self._queue_connect.task_done()

    def _extract_top_num_wods(self, html):
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()
        words = map(lambda x: x.strip(), text.lower().split())

        top_words = dict(Counter(words).most_common(self.num_top_words))
        return top_words

    def _request_data(self, url):
        res = {}
        try:
            response = requests.get(url, timeout=3)
        except requests.exceptions.RequestException as exception:
            res = {'Error': f'{exception}'}
        else:
            html = response.text
            res = self._extract_top_num_wods(html)

        with self._print_lock:
            self.processed_message_cnt += 1
            print(f"Messages processed: {self.processed_message_cnt}")

        return res


def get_prg_args():
    parser_arg = argparse.ArgumentParser()
    parser_arg.add_argument('-w', type=int, required=True)
    parser_arg.add_argument('-k', type=int, required=True)
    args = parser_arg.parse_args()

    return args


if __name__ == '__main__':
    HOST = '127.0.0.1'
    PORT = 8081

    launch_args = get_prg_args()

    server = Server(
        server_address=HOST,
        server_port=PORT,
        num_workers=launch_args.w,
        num_top_words=launch_args.k,
    )
    server.start()
    time.sleep(20)
    server.stop()
