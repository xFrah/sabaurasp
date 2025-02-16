from onvif import ONVIFCamera
import cv2
import threading
import vlc
import time

cameras = {
    "bulb": {
        "ip": "lancionaco.ddns.net",
        "onvif_port": 7071,
        "rtsp_port": 7072,
        "username": "admin",
        "password": "password",
    },
    "tapo": {
        "ip": "lancionaco.ddns.net",
        "onvif_port": 7073,
        "rtsp_port": 7074,
        "username": "fdimonaco309@hotmail.com",
        "password": "Gaspardo1*tapo",
    },
}

selected_camera = cameras["tapo"]


class CameraControl:
    def __init__(self, camera_ip=selected_camera["ip"], camera_port=selected_camera["onvif_port"], username=selected_camera["username"], password=selected_camera["password"]):
        # PTZ control
        self.ptz = None
        self.media = None
        self.profile = None
        self.running = True
        self.last_position = {"x": 0, "y": 0}
        self.last_move_time = 0
        self.counter = 0

        # Initialize camera
        self.setup_camera(camera_ip, camera_port, username, password)

        # Create control window and trackbars
        cv2.namedWindow("Camera Control")
        cv2.createTrackbar("X Position", "Camera Control", 100, 200, lambda x: None)
        cv2.createTrackbar("Y Position", "Camera Control", 100, 200, lambda x: None)

        # Set initial positions to center (100 = 0.0)
        cv2.setTrackbarPos("X Position", "Camera Control", 100)
        cv2.setTrackbarPos("Y Position", "Camera Control", 100)

        # Start position checking thread
        self.position_thread = threading.Thread(target=self.check_and_move_position)
        self.position_thread.daemon = True
        self.position_thread.start()

    def map_to_range(self, value):
        # Map from 0-200 to -1 to 1
        return (value - 100) / 100.0

    def check_and_move_position(self):
        while self.running:
            current_time = time.time()

            # Get current positions and map to -1 to 1
            x_pos = self.map_to_range(cv2.getTrackbarPos("X Position", "Camera Control"))
            y_pos = self.map_to_range(cv2.getTrackbarPos("Y Position", "Camera Control"))

            current_position = {"x": x_pos, "y": y_pos}

            if current_position != self.last_position:
                print(f"Position changed: {current_position}")
                self.counter = 0

            # Only move if position changed and rate limit of 2 seconds
            if (current_position != self.last_position or self.counter < 5) and current_time - self.last_move_time >= 2.0:

                print(f"Moving to position: x={x_pos:.2f}, y={y_pos:.2f}")
                self.move_camera(current_position)

                self.last_position = current_position
                self.last_move_time = current_time
                self.counter += 1

            time.sleep(0.1)  # Small sleep to prevent CPU overuse

    def move_camera(self, position):
        """Move camera to specified position"""
        try:
            # Create and send the move request
            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = {"PanTilt": {"x": position["x"], "y": position["y"]}, "Zoom": {"x": 0.5}}  # Keep zoom constant

            # Send move request with callback
            self.ptz.AbsoluteMove(request)
        except Exception as e:
            print(f"Error moving camera: {e}")


    def setup_camera(self, camera_ip, camera_port, username, password):
        # Initialize ONVIF camera
        mycam = ONVIFCamera(camera_ip, camera_port, username, password)

        print(f"Connecting to camera at {camera_ip}:{camera_port}")

        # Get media service
        self.media = mycam.create_media_service()
        profiles = self.media.GetProfiles()
        self.profile = profiles[0]

        print(f"Connected to camera at {camera_ip}:{camera_port}")

        # Get RTSP URL
        stream_setup = {"Stream": "RTP-Unicast", "Transport": "RTSP"}
        self.stream_uri = self.media.GetStreamUri({"ProfileToken": self.profile.token, "StreamSetup": stream_setup}).Uri
        if not self.stream_uri.startswith("rtsp://"):
            raise ValueError("Invalid RTSP URI")

        self.stream_uri = "/" + self.stream_uri[7:].split("/", 1)[1]
        print(f"RTSP Stream URI: {self.stream_uri}")

        # Setup PTZ control
        self.ptz = mycam.create_ptz_service()

    def start(self):
        self.player = vlc.MediaPlayer(f"rtsp://{selected_camera['username']}:{selected_camera['password']}@{selected_camera['ip']}:{selected_camera['rtsp_port']}{self.stream_uri}")
        self.player.play()
        try:
            # Main loop to keep window open
            while self.running:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                time.sleep(0.1)

        except KeyboardInterrupt:
            pass
        finally:
            print("Stopping camera control...")
            self.cleanup()

    def cleanup(self):
        self.running = False
        cv2.destroyAllWindows()
        if self.position_thread.is_alive():
            self.position_thread.join()


if __name__ == "__main__":
    camera_control = CameraControl()
    camera_control.start()
