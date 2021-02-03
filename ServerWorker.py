from random import randint
import sys
import traceback
import threading
import socket
import os
import json

from VideoStream import VideoStream
from RtpPacket import RtpPacket


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    SWITCH = 'SWITCH'
    CHOOSE = 'CHOOSE'
    STOP = 'STOP'
    DESCRIBE = 'DESCRIBE'
    SCROLL = 'SCROLL'

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    clientInfo = {}

    def __init__(self, clientInfo):
        self.clientInfo = clientInfo

    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        connSocket = self.clientInfo['rtspSocket'][0]
        while True:
            data = connSocket.recv(256)
            if data:
                print("Data received:\n" + data.decode("utf-8"))
                self.processRtspRequest(data.decode("utf-8"))

    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        # Get the request type
        request = data.split('\n')
        line1 = request[0].split(' ')
        requestType = line1[0]

        # Get the media file name
        filename = line1[1]

        # Get the RTSP sequence number
        seq = request[1].split(' ')

        # Process SETUP request
        if requestType == self.SETUP:
            if self.state == self.INIT:
                # Update state
                print("processing SETUP\n")

                try:
                    self.clientInfo['videoStream'] = VideoStream(filename)
                    self.state = self.READY
                    # set rtpError to 0
                    self.rtpError = 0
                    self.frame_Number = 0
                    self.numberOfFrames = self.clientInfo['videoStream'].nbrOfFrames()
                    self.progress = None
                    self.setProgress = False
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

                # Generate a randomized RTSP session ID
                self.clientInfo['session'] = randint(100000, 999999)

                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])

                # Get the RTP/UDP port from the last line
                self.clientInfo['rtpPort'] = request[2].split(' ')[3]

        # Process PLAY request
        elif requestType == self.PLAY:
            if self.state == self.READY:
                print("processing PLAY\n")
                self.state = self.PLAYING

                # Create a new socket for RTP/UDP
                self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                self.replyRtsp(self.OK_200, seq[1])

                # Create a new thread and start sending RTP packets
                self.clientInfo['event'] = threading.Event()
                self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
                self.clientInfo['worker'].start()

        # Process PAUSE request
        elif requestType == self.PAUSE:
            if self.state == self.PLAYING:
                print("processing PAUSE\n")
                self.state = self.READY

                self.clientInfo['event'].set()

                self.replyRtsp(self.OK_200, seq[1])

        # Process TEARDOWN request
        elif requestType == self.TEARDOWN:
            print("processing TEARDOWN\n")

            self.clientInfo['event'].set()

            self.replyRtsp(self.OK_200, seq[1])
            # print statics
            rtpLossRate = self.rtpError * 100 / float(self.frame_Number)
            print("RTP packet loss rate is: %.3f %%" % (rtpLossRate))
            # Close the RTP socket
            self.clientInfo['rtpSocket'].close()

        # Process SWITCH request
        elif requestType == self.SWITCH:
            if not self.state == self.PLAYING:
                print("processing SWITCH\n")

                self.replyRtsp(self.OK_200, seq[1])

        # Process CHOOSE request
        elif requestType == self.CHOOSE:
            if not self.state == self.PLAYING:
                print("processing CHOOSE\n")

                try:
                    self.clientInfo['videoStream'].terminate()
                    self.clientInfo['videoStream'] = VideoStream(filename)
                except IOError:
                    self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

                # Send RTSP reply
                self.replyRtsp(self.OK_200, seq[1])

        # Process STOP request
        elif requestType == self.STOP:
            if self.state == self.PLAYING or self.state == self.READY:
                print("processing STOP\n")
                self.state = self.INIT

                self.clientInfo['event'].set()

                self.clientInfo['videoStream'].terminate()

                self.replyRtsp(self.OK_200, seq[1])

                self.clientInfo['rtpSocket'].close()

        # Process DESCRIBE request
        elif requestType == self.DESCRIBE:
            print("processing DESCRIBE\n")

            description = {}
            description['session'] = self.clientInfo['session']
            description['encoding'] = filename.split('.')[1]
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq[1] + '\nSession: ' + \
                str(self.clientInfo['session']) + \
                '\n' + json.dumps(description)
            self.clientInfo['rtspSocket'][0].send(reply.encode())
        
        # Process SCROLL request
        elif requestType == self.SCROLL:
            print("processing SCROLL\n")

            progress = int(request[3].split(' ')[1])
            self.progress = progress
            self.setProgress = True

            self.replyRtsp(self.OK_200, seq[1])

            if self.progress < self.frame_Number:
                if self.state == self.READY:
                    try:
                        self.clientInfo['videoStream'].terminate()
                        self.clientInfo['videoStream'] = VideoStream(filename)
                    except IOError:
                        self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])
                elif self.state == self.PLAYING:
                    self.clientInfo['event'].set()
                    try:
                        self.clientInfo['videoStream'].terminate()
                        self.clientInfo['videoStream'] = VideoStream(filename)
                    except IOError:
                        self.replyRtsp(self.FILE_NOT_FOUND_404, seq[1])

                    # Create a new socket for RTP/UDP
                    self.clientInfo["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                    # Create a new thread and start sending RTP packets
                    self.clientInfo['event'] = threading.Event()
                    self.clientInfo['worker'] = threading.Thread(target=self.sendRtp)
                    self.clientInfo['worker'].start()

    def sendRtp(self):
        """Send RTP packets over UDP."""
        while True:
            self.clientInfo['event'].wait(0.05)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.clientInfo['event'].isSet():
                break

            data = self.clientInfo['videoStream'].nextFrame()
            if data:
                frameNumber = self.clientInfo['videoStream'].frameNbr()
                self.frame_Number = frameNumber
                if not self.setProgress or self.setProgress and self.progress == frameNumber:
                    self.setProgress = False
                    self.progress = frameNumber
                    try:
                        address = self.clientInfo['rtspSocket'][1][0]
                        port = int(self.clientInfo['rtpPort'])
                        try:
                            self.clientInfo['rtpSocket'].sendto(self.makeRtp(data, frameNumber), (address, port))
                        except:
                            self.rtpError += 1
                            print("ServerWorker RTP/UDP Sending Error: " + str(self.rtpError))
                            self.replyRtsp(500, self.clientInfo['session'])
                    except:
                        print("Connection Error")
                        # print('-'*60)
                        # traceback.print_exc(file=sys.stdout)
                        # print('-'*60)

    def makeRtp(self, payload, frameNbr):
        """RTP-packetize the video data."""
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26  # MJPEG type
        seqnum = frameNbr
        ssrc = 0

        rtpPacket = RtpPacket()

        rtpPacket.encode(version, padding, extension, cc,seqnum, marker, pt, ssrc, payload)

        return rtpPacket.getPacket()

    def replyRtsp(self, code, seq):
        """Send RTSP reply to the client."""
        if code == self.OK_200:
            #print("200 OK")
            reply = 'RTSP/1.0 200 OK\nCSeq: ' + seq + \
                '\nSession: ' + str(self.clientInfo['session'])

            if not self.state == self.PLAYING:
                videoList = []
                for f in os.listdir():
                    if f.endswith(".Mjpeg"):
                        videoList.append(f)
                reply += '\n' + " ".join(videoList) + '\n' + str(self.numberOfFrames)

            connSocket = self.clientInfo['rtspSocket'][0]
            connSocket.send(reply.encode())

        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
