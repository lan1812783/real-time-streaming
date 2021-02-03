class VideoStream:
    def __init__(self, filename):
        self.filename = filename
        try:
            self.file = open(filename, 'rb')
        except:
            raise IOError
        self.frameNum = 0

        # Scroll implementation
        self.numberOfFrames = self.calNumberOfFrames()
        

    def nextFrame(self):
        """Get next frame."""
        data = self.file.read(5)  # Get the framelength from the first 5 bits
        if data:
            framelength = int(data)

            # Read the current frame
            data = self.file.read(framelength)
            self.frameNum += 1
        return data

    def calNumberOfFrames(self):
        """Calculate number of frames"""
        numberOfFrames = 0
        with open(self.filename, 'rb') as f:
            data = f.read(5)  # Get the framelength from the first 5 bits
            while data:
                framelength = int(data)

                # Read the current frame
                data = f.read(framelength)
                numberOfFrames += 1
                data = f.read(5)
        return numberOfFrames

    def nbrOfFrames(self):
        """Get number of frames"""
        return self.numberOfFrames

    def frameNbr(self):
        """Get frame number."""
        return self.frameNum

    def terminate(self):
        """Close file"""
        if not self.file.closed:
            self.file.close()
