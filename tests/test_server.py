import unittest
from unittest.mock import Mock, MagicMock, patch, call
import time
from server import Server
import requests


class ServerTest(unittest.TestCase):
    def connection_mock_factory(
        self,
        messages: list,
        expected_send_data,
        max_conn: int = 0,
    ):
        self.created_connections = 0

        def create_mock_connection():
            resp_messages = messages.copy()

            if max_conn is not None and self.created_connections >= max_conn:
                raise TimeoutError()
            mock_conn = MagicMock()

            def recv_decode_side_effect():
                if len(resp_messages) > 0:
                    return resp_messages.pop().encode()
                return b''

            def sendall_side_effect(data):  # Проверка данных к клиенту
                self.assertEqual(expected_send_data, data)

            mock_conn.recv.return_value.decode.side_effect = \
                recv_decode_side_effect
            mock_conn.sendall.side_effect = sendall_side_effect

            self.created_connections += 1
            return (mock_conn, None)
        return create_mock_connection

    def setUp(self) -> None:
        self.server_host = 'localhost'
        self.server_port = 8081
        self.server_endpoint = (self.server_host, self.server_port)

        self.server = Server(
            server_address=self.server_host,
            server_port=self.server_port,
            num_workers=30,
            num_top_words=3,
        )

    @patch('socket.socket', autospec=True)
    @patch('requests.get')
    def test_server_base_work(
        self,
        mock_request_get: MagicMock,
        mock_socket: MagicMock
    ):
        test_url = 'url.com'
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = b'a a b b a b a'
        mock_request_get.return_value = mock_response

        func = self.connection_mock_factory(
            messages=[test_url],
            expected_send_data=b'{"a": 4, "b": 3}',
            max_conn=10,
        )

        mock_socket.return_value.__enter__.return_value.accept.side_effect = \
            func

        with patch('builtins.print') as mock_print:
            self.server.start()
            time.sleep(1)
            self.server.stop()

        self.server.join(timeout=2)
        self.assertFalse(self.server.is_alive())
        self.assertEqual(self.created_connections, mock_print.call_count)
        mock_print.assert_has_calls([
            call(f"Messages processed: {i + 1}")
            for i in range(self.created_connections)
        ])

    @patch('socket.socket', autospec=True)
    @patch.object(Server, '_worker_proc')
    def test_server_starts_correct_count_threads(
        self,
        mock_worker_proc,
        mock_socket,
    ):
        for k_workers in [1, 5, 1000]:
            excepted_thread_calls = [
                call(
                    name=f'server_worker-{i}',
                    target=mock_worker_proc,
                )
                for i in range(k_workers)
            ]

            func = self.connection_mock_factory(
                messages=[],
                expected_send_data=b'',
                max_conn=0,
            )

            mock_socket.return_value.__enter__.return_value\
                .accept.side_effect = func

            server = Server(
                server_address=self.server_host,
                server_port=self.server_port,
                num_workers=k_workers,
                num_top_words=1,
            )

            with patch('threading.Thread') as mock_threads:
                server.start()
                # Простая остановка, не требуящая остановки worker,
                # поскольку они не будут созданы
                server._keep_working = False
                server.join()

            self.assertEqual(
                k_workers,
                mock_threads.call_count
            )
            mock_threads.assert_has_calls(
                excepted_thread_calls, any_order=True
            )

    def test_server_uncorrect_server_addres(self):
        error_msg = 'Invalid address: Must be a non-empty string'
        with self.assertRaises(ValueError) as err:
            Server(
                server_address=192,
                server_port=self.server_port,
                num_workers=4,
                num_top_words=1,
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Server(
                server_address='',
                server_port=self.server_port,
                num_workers=4,
                num_top_words=1,
            )
        self.assertEqual(err.exception.args[0], error_msg)

    def test_client_uncorrect_server_port(self):
        error_msg = 'Invalid port: ' + \
                    'Must be an integer between 0 and 65535'
        with self.assertRaises(ValueError) as err:
            Server(
                server_address=self.server_host,
                server_port=90_000,
                num_workers=4,
                num_top_words=1,
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Server(
                server_address=self.server_host,
                server_port=-8081,
                num_workers=4,
                num_top_words=1,
            )
        self.assertEqual(err.exception.args[0], error_msg)

        with self.assertRaises(ValueError) as err:
            Server(
                server_address=self.server_host,
                server_port='8080',
                num_workers=4,
                num_top_words=1,
            )
        self.assertEqual(err.exception.args[0], error_msg)

    @patch('socket.socket')
    @patch('requests.get')
    def test_server_request_error(
        self,
        mock_request_get: MagicMock,
        mock_socket: MagicMock
    ):

        def exception_in_request(*args, **kwargs):
            raise requests.exceptions.RequestException()

        test_url = 'url.com'
        mock_request_get.side_effect = exception_in_request

        func = self.connection_mock_factory(
            messages=[test_url],
            expected_send_data=b'{"Error": ""}',
            max_conn=10,
        )

        mock_socket.return_value.__enter__.return_value.accept.side_effect = \
            func

        with patch('builtins.print') as mock_print:
            self.server.start()
            time.sleep(0.2)
            self.server.stop()

        self.server.join(timeout=2)
        self.assertFalse(self.server.is_alive())
        self.assertEqual(self.created_connections, mock_print.call_count)
        mock_print.assert_has_calls([
            call(f"Messages processed: {i + 1}")
            for i in range(self.created_connections)
        ])


if __name__ == "__main__":
    unittest.main()
