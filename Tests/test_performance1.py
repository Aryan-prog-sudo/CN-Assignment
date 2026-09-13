import sys
import socket
import time
import statistics
from pathlib import Path

ProjectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ProjectRoot))
from Common.protocol import(SendCommand, ReceiveCommand, BUFFER_SIZE)

HOST = "127.0.0.1"
PORT = 5000
USERNAME = "performace_user"
NUM_TESTS = 100
MESSAGE = "Performace test message"

def ReceiveMessageResponse(Socket):
    while True:
        Response = ReceiveCommand(Socket)
        if Response is None:
            raise ConnectionError("Connection closed while waiting for response")
        print(Response) if False else None
        if Response.startswith("OK MSG"):
            return Response
        if Response.startswith("MSG"):
            continue
        if Response.startswith("ERR"):
            raise RuntimeError(f"Server returned and an error: {Response}")

def Login(Socket):
    SendCommand(Socket, f"LOGIN {USERNAME}")
    Response = ReceiveCommand(Socket)
    if Response!= f"OK LOGIN {USERNAME}":
        raise RuntimeError(f"Login failed: {Response}")

def Logout(Socket):
    try:
        SendCommand(Socket, "LOGOUT")
        ReceiveCommand(Socket)
    except(OSError, ConnectionError):
        pass

def RunTest():
    RTTs = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as Socket:
        Socket.connect((HOST, PORT))
        Socket.settimeout(10)
        Login(Socket)
        print("Succesfully logged in")
        print(f"Running Test 1 with {NUM_TESTS} message\n")
        SendCommand(Socket, f"MSG {USERNAME} warmup")
        ReceiveMessageResponse(Socket)

        for TestNumber in range(1, NUM_TESTS+1):
            StartTime = time.perf_counter_ns()
            SendCommand(Socket, f"MSG {USERNAME} {MESSAGE}")
            ReceiveMessageResponse(Socket)
            EndTime = time.perf_counter_ns()
            RTTMillisecond = (EndTime-StartTime)/1_000_000
            RTTs.append(RTTMillisecond)
            print(f"Test {TestNumber:3d}: RTT={RTTMillisecond:.3f}ms")
        Logout(Socket)

    AverageRTT = statistics.mean(RTTs)
    MinimumRTT = min(RTTs)
    MaximumRTT = max(RTTs)
    MedianRTT = statistics.median(RTTs)

    print("\n" + "=" * 40)
    print("Test 1 - RTT Results")
    print("=" * 40)
    print(f"Number of tests : {NUM_TESTS}")
    print(f"Average RTT     : {AverageRTT:.3f} ms")
    print(f"Median RTT      : {MedianRTT:.3f} ms")
    print(f"Minimum RTT     : {MinimumRTT:.3f} ms")
    print(f"Maximum RTT     : {MaximumRTT:.3f} ms")
    print("=" * 40)

if __name__=="__main__":
    try:
        RunTest()
    except Exception as Error:
        print(f"\nTest Failed: {Error}")