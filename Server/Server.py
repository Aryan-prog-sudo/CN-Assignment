# To review: Potentiel deadlock in MSG

import socket
import threading
import os
from Common.protocol import *

HOST = '0.0.0.0'
PORT = 5000

STORAGE_DIR = 'Storage'

ActiveUsers = {}
SendLocks = {}
PendingTransfers = {} 
#The structure of this dictionary is as follows:
# PendingTransfers = {
#     'TargetUser1': [
#         {'Sender': 'UserA', 'FileName': 'file1.txt', 'FilePath': '/path/to/file1.txt', 'FileSize': 1234}
#     ]
# }

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
        SendLocks[UserName] = threading.Lock()
    with SendLocks[UserName]:
        SendCommand(ClientSocket, f"{RESP_OK} LOGIN {UserName}")
    print(f"User logged in: {UserName} from {ClientAddress}")
    #Now on succesful login, transfer (if any) pending files to the user
    with StateLock:
        PendingFiles = PendingTransfers.get(UserName, []).copy()
    for Transfer in PendingFiles:
        FileName = Transfer['FileName']
        Sender = Transfer['Sender']
        FilePath = Transfer['FilePath']
        FileSize = Transfer['FileSize']
        if not os.path.isfile(FilePath):
            print(f"Pending file not found for user {UserName}: {FilePath}")
            with StateLock:
                if UserName in PendingTransfers:
                    PendingTransfers[UserName].remove(Transfer)
            continue
        with SendLocks[UserName]:
            SendCommand(ClientSocket, f"{PUSH_INCOMING} {Sender} {FileName} {FileSize}")
            SendFileData(ClientSocket, FilePath)
        #After sending the file, remove it from the pending transfers and delete the temporary file
        with StateLock: 
            if UserName in PendingTransfers:
                PendingTransfers[UserName].remove(Transfer)
        os.remove(FilePath)
        print(f"Pending file sent to user {UserName}: {FileName} from {Sender} ({FileSize} bytes)")
    #Delete the user entry from the dictionary
    with StateLock:
        if UserName in PendingTransfers and not PendingTransfers[UserName]:
            del PendingTransfers[UserName]

    while True:
        Line = ReceiveCommand(ClientSocket)
        if Line is None:
            print(f"User disconnected: {UserName}")
            with StateLock:
                ActiveUsers.pop(UserName, None)
                SendLocks.pop(UserName, None)
            ClientSocket.close()
            return

        if Line==CMD_LOGOUT:
            with StateLock:
                ActiveUsers.pop(UserName, None)
                Lock = SendLocks.pop(UserName, None)
            if Lock:
                with Lock:
                    SendCommand(ClientSocket, f"{RESP_OK} LOGOUT")
            print(f"User logged out: {UserName}")
            ClientSocket.close()
            return

        if Line==CMD_LIST:
            with StateLock:
                UserList = list(ActiveUsers.keys())
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} {' '.join(UserList)}")
            print(f"User list sent to: {UserName}")
            continue

        Parts = Line.split(' ', 2)
        if len(Parts)==3 and Parts[0]==CMD_MSG:
            TargetUser = Parts[1]
            Message = Parts[2]
            with StateLock:
                TargetSocket = ActiveUsers.get(TargetUser)
                TargetLock = SendLocks.get(TargetUser)
            if TargetSocket is None:
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_USER_OFFLINE} user offline")
                continue
            with TargetLock:
                SendCommand(TargetSocket, f"{CMD_MSG} {UserName} {Message}")
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} MSG {TargetUser}")
            continue

        Parts = Line.split(' ', 1)
        if len(Parts)==2 and Parts[0]==CMD_BROADCAST:
            Message = Parts[1]
            with StateLock:
                Recipients = list(ActiveUsers.items())
            for TargetUser, TargetSocket in Recipients:
                with StateLock:
                    TargetLock = SendLocks.get(TargetUser)
                if TargetLock:
                    with TargetLock:
                        SendCommand(TargetSocket, f"{CMD_BROADCAST} {UserName} {Message}")
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} BROADCAST")
            continue

        Parts = Line.split(' ', 2)
        if len(Parts)==3 and Parts[0]==CMD_UPLOAD:
            FileName = Parts[1]
            try:
                FileSize = int(Parts[2])
            except ValueError:
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            if FileSize < 0:
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            UserStorageDir = os.path.join(STORAGE_DIR, UserName)
            os.makedirs(UserStorageDir, exist_ok=True)
            FilePath = os.path.join(UserStorageDir, FileName)
            ReceiveFileData(ClientSocket, FilePath, FileSize)
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} UPLOAD {FileName}")
            print(f"User {UserName} uploaded file: {FileName} ({FileSize} bytes)")
            continue

        Parts = Line.split(' ', 1)
        if len(Parts)==2 and Parts[0]==CMD_DOWNLOAD:
            FileName = Parts[1]
            UserStorageDir = os.path.join(STORAGE_DIR, UserName)
            FilePath = os.path.join(UserStorageDir, FileName)
            if not os.path.isfile(FilePath):
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_FILE_NOT_FOUND} file not found")
                continue
            FileSize = GetFileSize(FilePath)
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} DOWNLOAD {FileName} {FileSize}")
                SendFileData(ClientSocket, FilePath)
            print(f"User {UserName} downloaded file: {FileName} ({FileSize} bytes)")
            continue

        Parts = Line.split(' ', 3)
        if len(Parts)==4 and Parts[0]==CMD_SEND:
            TargetUser = Parts[1]
            FileName = Parts[2]
            try:
                FileSize = int(Parts[3])
            except ValueError:
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            if FileSize < 0:
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} Invalid File Size")
                continue
            with StateLock:
                TargetSocket = ActiveUsers.get(TargetUser)
                TargetLock = SendLocks.get(TargetUser)
            #If the target is offline
            if TargetSocket is None:
                PendingDir = os.path.join(STORAGE_DIR, "pending", TargetUser)
                os.makedirs(PendingDir, exist_ok=True)
                PendingPath = os.path.join(PendingDir, FileName)
                ReceiveFileData(ClientSocket, PendingPath, FileSize)
                with StateLock:
                    if TargetUser not in PendingTransfers:
                        PendingTransfers[TargetUser] = []
                    PendingTransfers[TargetUser].append({ "Sender": UserName, "FileName": FileName, "FilePath": PendingPath, "FileSize": FileSize })
                with SendLocks[UserName]:
                    SendCommand(ClientSocket, f"{RESP_OK} SEND_QUEUED {TargetUser} {FileName}")
                print(f"User {UserName} sent file: {FileName} to offline user {TargetUser} ({FileSize} bytes) - queued")
                continue
            #If the target is online
            TempDir = os.path.join(STORAGE_DIR, ".send_temp")
            os.makedirs(TempDir, exist_ok=True)
            TempPath = os.path.join(TempDir, f"{UserName}_{FileName}")
            ReceiveFileData(ClientSocket, TempPath, FileSize)
            with TargetLock:
                SendCommand(TargetSocket, f"{PUSH_INCOMING} {UserName} {FileName} {FileSize}")
                SendFileData(TargetSocket, TempPath)
            with SendLocks[UserName]:
                SendCommand(ClientSocket, f"{RESP_OK} SEND {TargetUser} {FileName}")
            print(f"User {UserName} sent file: {FileName} to {TargetUser} ({FileSize} bytes)")
            os.remove(TempPath)
            continue

        with SendLocks[UserName]:
            SendCommand(ClientSocket, f"{RESP_ERR} {ERR_MALFORMED_COMMAND} unknown command")



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