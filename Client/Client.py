import socket
from Common.protocol import *

HOST = '127.0.0.1'
PORT =  5000

def StartClient():
    ClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ClientSocket.connect((HOST, PORT))
    print(f"Connected to server at {HOST}:{PORT}")
    UserName = input("Enter your username: ")
    SendCommand(ClientSocket, f"{CMD_LOGIN} {UserName}")
    Response = ReceiveCommand(ClientSocket)
    if Response is None:
        print("Sever disconnected.")
        ClientSocket.close()
        return
    print(f"Server response: {Response}")
    ClientSocket.close()

if __name__ == "__main__":
    StartClient()