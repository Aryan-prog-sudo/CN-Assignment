import os
import socket

BUFFER_SIZE = 4096
ENCODING = 'utf-8'

CMD_LOGIN = "LOGIN"
CMD_LOGOUT = "LOGOUT"
CMD_LIST = "LIST"
CMD_MSG = "MSG"
CMD_BROADCAST = "BROADCAST"
CMD_UPLOAD = "UPLOAD"
CMD_DOWNLOAD = "DOWNLOAD"
CMD_SEND = "SEND"

RESP_OK = "OK"
RESP_ERR = "ERR"
PUSH_INCOMING = "INCOMING"

ERR_USERNAME_TAKEN = "001"
ERR_FILE_NOT_FOUND = "002"
ERR_USER_OFFLINE = "003"
ERR_MALFORMED_COMMAND = "004"
ERR_UNAUTHENTICATED = "005"

def SendCommand(Socket, Command):
    Message = Command+'\n'
    Socket.sendall(Message.encode(ENCODING))

def ReceiveCommand(Socket):
    Data = bytearray()
    while True:
        try:
            Chunk = Socket.recv(1)
        except OSError:
            return None
        if not Chunk:
            return None
        if Chunk==b'\n':
            break
        Data.extend(Chunk)
    return Data.decode(ENCODING)

def SendFileData(Socket, FilePath):
    with open(FilePath, 'rb') as File:
        while True:
            Data = File.read(BUFFER_SIZE)
            if not Data:
                break
            Socket.sendall(Data)

def ReceiveFileData(Socket, FilePath, Size):
    BytesReceived = 0
    with open(FilePath, 'wb') as File:
        while BytesReceived < Size:
            Remaining = Size - BytesReceived
            ChunkSize = min(BUFFER_SIZE, Remaining)
            Data = Socket.recv(ChunkSize)
            if not Data:
                raise ConnectionError("Connection closed before receiving all data")
            File.write(Data)
            BytesReceived += len(Data)

def GetFileSize(FilePath):
    return os.path.getsize(FilePath)
