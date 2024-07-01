import socket
import unittest
from unittest.mock import MagicMock, call, patch, mock_open
from client import Client


class TestClient(unittest.TestCase):
    def setUp(self) -> None:
        self.server_host = 'localhost'
        self.server_port = 8081
        self.server_endpoint = (self.server_host, self.server_port)

    @patch('socket.socket')
    def test_client_base_correct(self, mock_socket: MagicMock):
        urls = [f'https://smth_url{i}.com' for i in range(1000)]
        mock_file_data = '\n'.join(urls)
        responses = ['any response'] * len(urls)

        excepted_print = [
            call(f'{url} : {resp}')
            for url, resp in zip(urls, responses)
        ]
        excepted_call_socket = \
            [call(socket.AF_INET, socket.SOCK_STREAM)] * len(urls)
        excepted_call_sendall = [
            call(url.encode(encoding='utf-8')) for url in urls
        ]
        excepted_call_connect = [call(self.server_endpoint)] * len(urls)

        mock_cli_socket = MagicMock(name='mock_client_socket')
        mock_cli_socket.connect = MagicMock()
        mock_cli_socket.sendall = MagicMock()
        mock_cli_socket.recv.return_value.decode.side_effect = (
            resp for resp in responses
        )
        mock_socket.return_value.__enter__.return_value = mock_cli_socket

        with patch('builtins.open',
                   mock_open(read_data=mock_file_data)) as mock_file, \
                patch('builtins.print') as mock_print:
            client = Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=4,
                filename='filename.txt'
            )
            client.start()
            client.join()

        self.assertEqual(len(urls), mock_cli_socket.connect.call_count)
        self.assertEqual(len(urls), mock_cli_socket.sendall.call_count)
        self.assertEqual(len(urls), mock_cli_socket.recv.call_count)

        mock_print.assert_has_calls(excepted_print, any_order=True)
        self.assertEqual(
            [call('filename.txt', encoding='utf-8')], mock_file.call_args_list
        )
        mock_socket.assert_has_calls(excepted_call_socket, any_order=True)
        mock_cli_socket.connect.assert_has_calls(
            excepted_call_connect, any_order=True
        )
        mock_cli_socket.sendall.assert_has_calls(
            excepted_call_sendall, any_order=True
        )

    @patch('socket.socket')
    def test_client_more_threads_than_urls(self, mock_socket: MagicMock):
        urls = ['https://smth_url1.com',
                'https://smth_url2.com',
                'https://smth_url3.com',
                'https://smth_url4.com',]
        mock_file_data = '\n'.join(urls)
        responses = [f'any response {i}' for i in range(len(urls))]

        excepted_print = [
            call(f'{url} : {resp}')
            for url, resp in zip(urls, responses)
        ]
        excepted_call_socket = \
            [call(socket.AF_INET, socket.SOCK_STREAM)] * len(urls)
        excepted_call_sendall = [
            call(url.encode(encoding='utf-8')) for url in urls
        ]
        excepted_call_connect = [call(self.server_endpoint)] * len(urls)

        mock_cli_socket = MagicMock(name='mock_client_socket')
        mock_cli_socket.connect = MagicMock()
        mock_cli_socket.sendall = MagicMock()
        mock_cli_socket.recv.return_value.decode.side_effect = (
            resp for resp in responses
        )
        mock_socket.return_value.__enter__.return_value = mock_cli_socket

        with patch('builtins.open',
                   mock_open(read_data=mock_file_data)) as mock_file, \
                patch('builtins.print') as mock_print:
            client = Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=40,
                filename='filename.txt'
            )
            client.start()
            client.join()

        self.assertEqual(len(urls), mock_cli_socket.connect.call_count)
        self.assertEqual(len(urls), mock_cli_socket.sendall.call_count)
        self.assertEqual(len(urls), mock_cli_socket.recv.call_count)

        mock_print.assert_has_calls(excepted_print, any_order=True)
        self.assertEqual(
            [call('filename.txt', encoding='utf-8')], mock_file.call_args_list
        )
        mock_socket.assert_has_calls(excepted_call_socket, any_order=True)
        mock_cli_socket.connect.assert_has_calls(
            excepted_call_connect, any_order=True
        )
        mock_cli_socket.sendall.assert_has_calls(
            excepted_call_sendall, any_order=True
        )

    @patch.object(Client, '_worker_proc')
    def test_client_starts_correct_count_threads(self,
                                                 mock_worker_proc):
        for k_workers in [1, 5, 1000]:
            excepted_thread_calls = [
                call(name=f'client_worker-{i}', target=mock_worker_proc)
                for i in range(k_workers)
            ]

            with patch('builtins.open', mock_open(read_data='')):
                client = Client(
                    server_address=self.server_host,
                    server_port=self.server_port,
                    num_threads=k_workers,
                    filename='filename.txt'
                )

                with patch('threading.Thread') as mock_threads:
                    client.start()
                    client.join()

            self.assertEqual(
                k_workers + 1,  # Учитываем воркеров и поток чтения
                mock_threads.call_count
            )
            mock_threads.assert_has_calls(
                excepted_thread_calls, any_order=True
            )

    @patch('socket.socket')
    def test_client_any_socket_error(self, mock_socket: MagicMock):
        k_workers = 2
        urls = ['https://smth_url1.com',
                'https://smth_url2.com',
                'https://smth_url3.com',
                'https://smth_url4.com',]
        mock_file_data = '\n'.join(urls)

        excepted_print_errors = \
            [call('Socket error: Any socket error')] * len(urls)

        mock_cli_socket = MagicMock(name='mock_client_socket')
        mock_cli_socket.connect.side_effect = \
            socket.error('Any socket error')
        mock_socket.return_value.__enter__.return_value = mock_cli_socket

        with patch('builtins.open',
                   mock_open(read_data=mock_file_data)), \
                patch('builtins.print') as mock_print:
            client = Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=k_workers,
                filename='filename.txt'
            )
            client.start()
            client.join()

        mock_print.assert_has_calls(excepted_print_errors, any_order=True)
        self.assertEqual(len(urls), mock_print.call_count)

    @patch('socket.socket')
    def test_client_socket_error_conn_refused(self, mock_socket: MagicMock):
        k_workers = 2
        urls = ['https://smth_url1.com',
                'https://smth_url2.com',
                'https://smth_url3.com',
                'https://smth_url4.com',]
        mock_file_data = '\n'.join(urls)

        excepted_print_errors = \
            [call('Socket error: [Errno 111] Connection refused')] * k_workers

        mock_cli_socket = MagicMock(name='mock_client_socket')
        mock_cli_socket.connect.side_effect = \
            socket.error(111, 'Connection refused')
        mock_socket.return_value.__enter__.return_value = mock_cli_socket

        with patch('builtins.open',
                   mock_open(read_data=mock_file_data)), \
                patch('builtins.print') as mock_print:
            client = Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=k_workers,
                filename='filename.txt'
            )
            client.start()
            client.join()

        mock_print.assert_has_calls(excepted_print_errors, any_order=True)
        self.assertEqual(len(urls), mock_print.call_count)

    def test_client_uncorrect_threads_count(self):
        error_msg = 'num_threads must be an integer greater than 0'
        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=-1,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=0,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads='4',
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

    def test_client_uncorrect_server_addres(self):
        error_msg = 'Invalid server address: Must be a non-empty string'
        with self.assertRaises(ValueError) as err:
            Client(
                server_address=192,
                server_port=self.server_port,
                num_threads=4,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Client(
                server_address='',
                server_port=self.server_port,
                num_threads=4,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

    def test_client_uncorrect_server_port(self):
        error_msg = 'Invalid server port: ' + \
                    'Must be an integer between 0 and 65535'
        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port=90_000,
                num_threads=4,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port=-8081,
                num_threads=4,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Client(
                server_address=self.server_host,
                server_port='8080',
                num_threads=4,
                filename='filename.txt'
            )
        self.assertEqual(err.exception.args[0], error_msg)

    def test_client_uncorrect_file(self):
        with self.assertRaises(FileNotFoundError):
            client = Client(
                server_address=self.server_host,
                server_port=self.server_port,
                num_threads=4,
                filename='non_exsistent_file.txt'
            )
            client.load_links()


if __name__ == "__main__":
    unittest.main()
