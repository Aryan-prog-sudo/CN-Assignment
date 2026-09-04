import socket
import threading
import os
from Common.protocol import *

HOST = '0.0.0.0'
PORT = 5000

STORAGE_DIR = 'Storage'

ActiveUsers = {}
StateLock = threading.Lock()

def HandleClient(ClientSocket, ClientAddress):
    print(f"Client connected: {ClientAddress}")
    Line = ReceiveCommand(ClientSocket)
    if Line is None:
        print(f"Client disconnected: {ClientAddress}")
        ClientSocket.close()
        return

    Parts = Line.split(' ', 1)
    if len(Parts) != 2 or Parts[0] != CMD_LOGIN:
        SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} bad login")
        ClientSocket.close()
        return
    UserName = Parts[1]
    with StateLock:
        if UserName in ActiveUsers:
            SendCommand(ClientSocket, f"{RESP_ERR} {ERR_USERNAME_TAKEN} username taken")
            ClientSocket.close()
            return
        ActiveUsers[UserName] = ClientSocket
    SendCommand(ClientSocket, f"{RESP_OK} LOGIN {UserName}")
    print(f"User logged in: {UserName} from {ClientAddress}")

    while True:
        Line = ReceiveCommand(ClientSocket)
        if Line is None:
            print(f"User disconnected: {UserName}")
            with StateLock:
                if UserName in ActiveUsers:
                    del ActiveUsers[UserName]
            ClientSocket.close()
            return
        if Line==CMD_LOGOUT:
            with StateLock:
                if UserName in ActiveUsers:
                    del ActiveUsers[UserName]
            SendCommand(ClientSocket, f"{RESP_OK} LOGOUT")
            print(f"User logged out: {UserName}")
            ClientSocket.close()
            return
        if Line==CMD_LIST:
            with StateLock:
                UserList = list(ActiveUsers.keys())
            SendCommand(ClientSocket, f"{RESP_OK} {' '.join(UserList)}")
            print(f"User list sent to: {UserName}")
            continue
        Parts = Line.split(' ', 2)
        if len(Parts)==3 and Parts[0]==CMD_MSG:
            TargetUser = Parts[1]
            Message = Parts[2]
            with StateLock:
                TargetSocket = ActiveUsers.get(TargetUser)
            if TargetSocket is None:
                SendCommand(ClientSocket, f"{RESP_ERR} {ERR_USER_OFFLINE} user offline")
                continue
            SendCommand(TargetSocket, f"{CMD_MSG} {UserName} {Message}")
            SendCommand(ClientSocket, f"{RESP_OK} MSG {TargetUser}")
            continue
        Parts = Line.split(' ', 1)
        if len(Parts)==2 and Parts[0]==CMD_BROADCAST:
            Message = Parts[1]
            with StateLock:
                UserSockets = list(ActiveUsers.values())
            for TargetSocket in UserSockets:
                SendCommand(TargetSocket, f"{CMD_BROADCAST} {UserName} {Message}")
            SendCommand(ClientSocket, f"{RESP_OK} BROADCAST")
            continue
        Parts = Line.split(' ', 2)
        if len(Parts)==3 and Parts[0]==CMD_UPLOAD:
            FileName = Parts[1]
            try:
                FileSize = int(Parts[2])
            except ValueError:
                SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            if FileSize < 0:
                SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            UserStorageDir = os.path.join(STORAGE_DIR, UserName)
            os.makedirs(UserStorageDir, exist_ok=True)
            FilePath = os.path.join(UserStorageDir, FileName)
            ReceiveFileData(ClientSocket, FilePath, FileSize)
            SendCommand(ClientSocket, f"{RESP_OK} UPLOAD {FileName}")
            print(f"User {UserName} uploaded file: {FileName} ({FileSize} bytes)")
            continue
        Parts = Line.split(' ', 1)
        if len(Parts)==2 and Parts[0]==CMD_DOWNLOAD:
            FileName = Parts[1]
            UserStorageDir = os.path.join(STORAGE_DIR, UserName)
            FilePath = os.path.join(UserStorageDir, FileName)
            if not os.path.isfile(FilePath):
                SendCommand(ClientSocket, f"{RESP_ERR} {ERR_FILE_NOT_FOUND} file not found")
                continue
            FileSize = GetFileSize(FilePath)
            SendCommand(ClientSocket, f"{RESP_OK} DOWNLOAD {FileName} {FileSize}")
            SendFileData(ClientSocket, FilePath)
            print(f"User {UserName} downloaded file: {FileName} ({FileSize} bytes)")
            continue
        




def StartServer():
    ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ServerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ServerSocket.bind((HOST, PORT))
    ServerSocket.listen()
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        ClientSocket, ClientAddress = ServerSocket.accept()
        ClientThread = threading.Thread(target=HandleClient, args=(ClientSocket, ClientAddress), daemon=True)
        ClientThread.start()

if __name__ == "__main__":
    StartServer()