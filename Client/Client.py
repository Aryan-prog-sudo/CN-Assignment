#To Review: After the client sends LOGOUT it immediately closes with recieving the severs OK LOGOUT response

import socket
import threading
import os
from Common.protocol import *

HOST = '127.0.0.1'
PORT =  5000

def ReceiveMessages(ClientSocket):
    while True:
        Message = ReceiveCommand(ClientSocket)
        if Message is None:
            print("\nServer Disconnected")
            return

        if Message.startswith(RESP_OK):
            Parts = Message.split(' ', 3)
            if len(Parts)==4 and Parts[1]==CMD_DOWNLOAD:
                FileName = Parts[2]
                try:
                    FileSize = int(Parts[3])
                except ValueError:
                    print(f"\nInvalid download file size: {Parts[3]}")
                    continue
                os.makedirs("Downloads", exist_ok=True)
                FilePath = os.path.join("Downloads", FileName)
                ReceiveFileData(ClientSocket,  FilePath, FileSize)
                print(f"\nDownloaded '{FileName}' ({FileSize} bytes)")
            else:
                print(f"\nServer Response: {Message}")

        elif Message.startswith(RESP_ERR):
            print(f"\nServer Error: {Message}")

        elif Message.startswith(CMD_MSG):
            print(f"\nPrivate Message: {Message}")

        elif Message.startswith(CMD_BROADCAST):
            print(f"\nBroadcast: {Message}")

        elif Message.startswith(PUSH_INCOMING):
            Parts = Message.split(' ', 3)
            if len(Parts)!=4:
                print(f"\nInvalid INCOMING message: {Message}")
                continue
            Sender = Parts[1]
            FileName = Parts[2]
            try:
                FileSize = int(Parts[3])
            except ValueError:
                print(f"\nInvalid file size: {Parts[3]}")
                continue
            os.makedirs("Received", exist_ok=True)
            FilePath = os.path.join("Received", FileName)
            ReceiveFileData(ClientSocket, FilePath, FileSize)
            print(f"\nReceived '{FileName}' from {Sender} ({FileSize} bytes)")
        else:
            print(f"\nUnknown message from server: {Message}")
        print(">", end="", flush=True)
            

def StartClient():
    ClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ClientSocket.connect((HOST, PORT))
    print(f"Connected to server at {HOST}:{PORT}")
    UserName = input("Enter your username: ")
    SendCommand(ClientSocket, f"{CMD_LOGIN} {UserName}")
    Response = ReceiveCommand(ClientSocket)
    if Response is None:
        print("Server disconnected.")
        ClientSocket.close()
        return
    print(f"Server response: {Response}")
    ReceiverThread = threading.Thread(target=ReceiveMessages, args=(ClientSocket,), daemon=True)
    ReceiverThread.start()
    while True:
        Command = input(">")

        Parts = Command.split(' ', 1)
        if len(Parts)==2 and Parts[0]==CMD_UPLOAD:
            FilePath = Parts[1]
            if not os.path.isfile(FilePath):
                print(f"File not found: {FilePath}")
                continue
            FileName = os.path.basename(FilePath)
            FileSize = GetFileSize(FilePath)
            SendCommand(ClientSocket, f"{CMD_UPLOAD} {FileName} {FileSize}")
            SendFileData(ClientSocket, FilePath)
            continue

        if len(Parts)==2 and Parts[0]==CMD_SEND:
            SendParts = Parts[1].split(' ', 1)
            if len(SendParts)!=2:
                print("Usage: SEND <username> <file_path>")
                continue
            TargetUser = SendParts[0]
            FilePath = SendParts[1]
            if not os.path.isfile(FilePath):
                print(f"File not found: {FilePath}")
                continue
            FileName = os.path.basename(FilePath)
            FileSize = GetFileSize(FilePath)
            SendCommand(ClientSocket, f"{CMD_SEND} {TargetUser} {FileName} {FileSize}")
            SendFileData(ClientSocket, FilePath)
            continue

        SendCommand(ClientSocket, Command)

        if Command==CMD_LOGOUT:
            break
    ClientSocket.close()


if __name__ == "__main__":
    StartClient()