from Common.protocol import *
import socket

server_socket, client_socket = socket.socketpair()
SendCommand(client_socket, "Login Alice")
command = ReceiveCommand(server_socket)
print("Received command:", command)
server_socket.close()
client_socket.close()