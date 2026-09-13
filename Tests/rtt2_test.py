#This is for measuring RTT between two different users

import sys
import socket
import time
import statistics
from pathlib import Path

ProjectRoot = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ProjectRoot))

from Common.protocol import SendCommand, ReceiveCommand

HOST = "127.0.0.1"
PORT = 5000

SENDER_USERNAME = "performance_alice"
RECEIVER_USERNAME = "performance_bob"
NUM_TESTS = 100
MESSAGE = "Performance test message"


def Login(Socket, Username):
    SendCommand(Socket, f"LOGIN {Username}")
    Response = ReceiveCommand(Socket)
    if Response != f"OK LOGIN {Username}":
        raise RuntimeError(f"Login failed for {Username}: {Response}")


def Logout(Socket):
    try:
        SendCommand(Socket, "LOGOUT")
        ReceiveCommand(Socket)
    except (OSError, ConnectionError):
        pass


def RunTest():
    RTTs = []
    with (socket.socket(socket.AF_INET, socket.SOCK_STREAM) as SenderSocket,
          socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ReceiverSocket):

        SenderSocket.connect((HOST, PORT))
        ReceiverSocket.connect((HOST, PORT))
        SenderSocket.settimeout(10)
        ReceiverSocket.settimeout(10)

        Login(SenderSocket, SENDER_USERNAME)
        Login(ReceiverSocket, RECEIVER_USERNAME)
        print("Both users logged in successfully\n")

        # Warmup — discard the first RTT (connection/OS warm-up effects)
        SendCommand(SenderSocket, f"MSG {RECEIVER_USERNAME} Warmup")
        ReceiveCommand(SenderSocket)

        print(f"Running {NUM_TESTS} MSG round-trips (alice -> bob)\n")
        for TestNumber in range(1, NUM_TESTS + 1):
            StartTime = time.perf_counter_ns()
            SendCommand(SenderSocket, f"MSG {RECEIVER_USERNAME} {MESSAGE}")
            Response = ReceiveCommand(SenderSocket)
            EndTime = time.perf_counter_ns()

            if Response is None or not Response.startswith("OK MSG"):
                raise RuntimeError(f"Unexpected response: {Response}")

            RTTMilliseconds = (EndTime - StartTime) / 1_000_000
            RTTs.append(RTTMilliseconds)
            print(f"Test {TestNumber:3d}  RTT = {RTTMilliseconds:.3f} ms")

        Logout(SenderSocket)
        Logout(ReceiverSocket)

    if not RTTs:
        raise RuntimeError("No RTT measurements were recorded")

    print("\n" + "=" * 45)
    print("Test 1 - Two-User RTT Results")
    print("=" * 45)
    print(f"Sender             : {SENDER_USERNAME}")
    print(f"Receiver           : {RECEIVER_USERNAME}")
    print(f"Number of tests    : {NUM_TESTS}")
    print(f"Average RTT        : {statistics.mean(RTTs):.3f} ms")
    print(f"Median RTT         : {statistics.median(RTTs):.3f} ms")
    print(f"Minimum RTT        : {min(RTTs):.3f} ms")
    print(f"Maximum RTT        : {max(RTTs):.3f} ms")
    if len(RTTs) > 1:
        print(f"Std deviation      : {statistics.stdev(RTTs):.3f} ms")
    print("=" * 45)


if __name__ == "__main__":
    try:
        RunTest()
    except Exception as Error:
        print(f"\nTest Failed: {Error}")