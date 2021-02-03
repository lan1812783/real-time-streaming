from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os
import json
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    SWITCH = 4
    CHOOSE = 5
    STOP = 6
    DESCRIBE = 7
    SCROLL = 8

    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.stopAcked = 0
        self.connectToServer()
        self.frameNbr = 0
        self.scrollFlag = False

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        # self.setup = Button(self.master, width=20, padx=3, pady=3)
        # self.setup["text"] = "Setup"
        # self.setup["command"] = self.setupMovie
        # self.setup.grid(row=2, column=0, padx=2, pady=2)

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=2, padx=2, pady=2)

        # Create Teardown button
        # self.teardown = Button(self.master, width=20, padx=3, pady=3)
        # self.teardown["text"] = "Teardown"
        # self.teardown["command"] = self.exitClient
        # self.teardown.grid(row=2, column=3, padx=2, pady=2)

        # Create Stop button
        self.stop = Button(self.master, width=20, padx=3, pady=3)
        self.stop["text"] = "Stop"
        self.stop["command"] = self.stopSession
        self.stop.grid(row=2, column=3, padx=2, pady=2)

        # Create Switch button
        self.switch = Button(self.master, width=20, padx=3, pady=3)
        self.switch["text"] = "Switch"
        self.switch["command"] = self.switchMovie
        self.switch.grid(row=2, column=4, padx=2, pady=2)

        # Create Describe button
        self.describe = Button(self.master, width=20, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] = self.describeSession
        self.describe.grid(row=2, column=5, padx=2, pady=2)
        
        # Create Scroll progress bar
        self.scroll = Scale(self.master, from_=1, to=500, orient='vertical', length=288)
        self.scroll.bind("<ButtonPress-1>", self.mouseDown)
        self.scroll.bind("<ButtonRelease-1>", self.mouseUp)
        self.scroll.grid(row=0, column=4, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4,
                        sticky=W+E+N+S, padx=5, pady=5)

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        # Delete the cache image from video
        os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def playMovie(self):
        """Play button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)

        if self.state == self.PLAYING:
            return

        while True:
            if self.state == self.READY:
                self.sendRtspRequest(self.PLAY)
                self.playEvent = threading.Event()
                self.playEvent.clear()
                threading.Thread(target=self.listenRtp).start()
                break

    def switchMovie(self):
        """Switch button handler"""
        # if self.state == self.INIT:
        #     self.sendRtspRequest(self.SETUP)
        if self.state == self.PLAYING:
            return
        while True:
            if not self.state == self.PLAYING:
                self.sendRtspRequest(self.SWITCH)
                break

    def chooseMovie(self, videoList):
        def go(event):
            self.fileName = chooseMovie.get(chooseMovie.curselection())
            self.sendRtspRequest(self.CHOOSE)

        frame = Frame(self.master)
        frame.grid(row=0, column=5)

        # Create Choose listbox
        chooseMovie = Listbox(frame)
        chooseMovie.bind('<Double-1>', go)
        chooseMovie.pack(side='left', fill='y')

        scrollbarY = Scrollbar(frame, orient="vertical",command=chooseMovie.yview)
        scrollbarY.pack(side="right", fill="y")

        chooseMovie.config(yscrollcommand=scrollbarY.set)

        # Inserting items in Listbox
        for video in videoList:
            chooseMovie.insert("end", video)

    def mouseDown(self, o):
        self.scrollFlag = True
        
    def mouseUp(self, o):
        self.progress = self.scroll.get()
        self.frameNbr = self.progress
        self.sendRtspRequest(self.SCROLL)

    def stopSession(self):
        if self.state == self.PLAYING or self.state == self.READY:
            self.sendRtspRequest(self.STOP)

    def describeSession(self):
        if not self.state == self.INIT:
            self.sendRtspRequest(self.DESCRIBE)

    def listenRtp(self):
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    currFrameNbr = rtpPacket.seqNum()
                    print("Current Seq Num: " + str(currFrameNbr))

                    if currFrameNbr == 1:
                        self.frameNbr = 0

                    if currFrameNbr >= self.frameNbr:  # Discard the late packet
                        self.frameNbr = currFrameNbr
                        if not self.scrollFlag:
                            self.scroll.set(self.frameNbr)
                        self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet():
                    break

                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

                # Upon receiving ACK for STOP request,
                # close the RTP socket
                if self.stopAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

    def writeFrame(self, data):
        picSize = sys.getsizeof(data)
        self.movieSize += picSize # accumulate the movie size
        self.timeConsume = time.time() - self.playingTime # accumulate playing time
        dataRate = self.movieSize / self.timeConsume
        print("Video Data Rate: %.3f byte/s" % dataRate)

        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

        return cachename

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image=photo, height=288)
        self.label.image = photo

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
        except:
            tkMessageBox.showwarning(
                'Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        # -------------
        # TO COMPLETE
        # -------------

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            if self.requestSent == -1:
                threading.Thread(target=self.recvRtspReply).start()

                # Update RTSP sequence number.
                # ...
                self.rtspSeq = 1
                # clear movie size for next playing
                self.movieSize = 0
                # clear time counter for next playing
                self.timeConsume = 0
                # Write the RTSP request to be sent.

            else:
                self.rtspSeq += 1
            # request = ...
            request = ("SETUP " + str(self.fileName) + " RTSP/1.0 " + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Transport: RTP/UDP; client_port= " + str(self.rtpPort))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1
            self.playingTime = time.time()
            # Write the RTSP request to be sent.
            # request = ...
            request = ("PLAY " + str(self.fileName) + " RTSP/1.0 " + "\n" +
                       "CSeq: " + str(self.rtspSeq) + "\n" +
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("PAUSE " + str(self.fileName) + " RTSP/1.0 " + "\n" +
                       "CSeq: " + str(self.rtspSeq) + "\n" +
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("TEARDOWN " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.TEARDOWN

        # Switch request
        elif requestCode == self.SWITCH and not self.state == self.PLAYING:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("SWITCH " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.SWITCH

        # Choose request
        elif requestCode == self.CHOOSE and not self.state == self.PLAYING:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("CHOOSE " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.CHOOSE

        # Stop request
        elif requestCode == self.STOP and (self.state == self.PLAYING or self.state == self.READY):
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("STOP " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.STOP

        # Descibe request
        elif requestCode == self.DESCRIBE:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("DESCRIBE " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.DESCRIBE
        
        # Scroll request
        elif requestCode == self.SCROLL:
            # Update RTSP sequence number.
            # ...
            self.rtspSeq = self.rtspSeq + 1

            # Write the RTSP request to be sent.
            # request = ...
            request = ("SCROLL " + str(self.fileName) + " RTSP/1.0" + "\n"
                       "CSeq: " + str(self.rtspSeq) + "\n"
                       "Session: " + str(self.sessionId) + "\n"
                       "Progress: " + str(self.progress))

            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.SCROLL

        else:
            return

        # Send the RTSP request using rtspSocket.
        # ...
        self.rtspSocket.send(request.encode("utf-8"))

        print('\nData sent:\n' + request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)

            if reply:
                self.parseRtspReply(reply.decode("utf-8"))

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

            # Close the RTSP socket upon requesting Stop
            # if self.requestSent == self.STOP:
            #     self.rtspSocket.shutdown(socket.SHUT_RDWR)
            #     self.rtspSocket.close()
            #     break

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            session = int(lines[2].split(' ')[1])
            # New RTSP session ID
            if self.sessionId == 0 or self.state == self.INIT:
                self.sessionId = session

            # Process only if the session ID is the same
            if self.sessionId == session:
                if int(lines[0].split(' ')[1]) == 200:
                    if self.requestSent == self.SETUP:
                        # -------------
                        # TO COMPLETE
                        # -------------
                        # Update RTSP state.
                        # self.state = ...
                        self.state = self.READY
                        self.numberOfFrames = lines[4]
                        # self.scroll.configure(to=self.numberOfFrames)

                        # Open RTP port.
                        self.openRtpPort()
                    elif self.requestSent == self.PLAY:
                        # self.state = ...
                        self.state = self.PLAYING
                    elif self.requestSent == self.PAUSE:
                        # self.state = ...
                        self.state = self.READY

                        # The play thread exits. A new thread is created on resume.
                        self.playEvent.set()
                    elif self.requestSent == self.TEARDOWN:
                        # self.state = ...
                        self.state = self.INIT

                        # Flag the teardownAcked to close the socket.
                        self.teardownAcked = 1

                    elif self.requestSent == self.SWITCH:
                        self.chooseMovie(lines[3].split(" "))

                    elif self.requestSent == self.STOP:
                        self.state = self.INIT

                        self.stopAcked = 1

                    elif self.requestSent == self.DESCRIBE:
                        print(f'\nDescription: {lines[3]}')
                    
                    elif self.requestSent == self.SCROLL:
                        self.scrollFlag = False
                        print("Frame number: ", self.frameNbr)

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        # self.rtpSocket = ...
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Set the timeout value of the socket to 0.5sec
        # ...
        self.rtpSocket.settimeout(0.5)

        try:
            # Bind the socket to the address using the RTP port given by the client user
            # ...
            self.state = self.READY
            self.rtpSocket.bind(('', self.rtpPort))
        except:
            tkMessageBox.showwarning(
                'Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            self.playMovie()
