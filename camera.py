from onvif import ONVIFCamera
import cv2
import paho.mqtt.client as mqtt
import threading
import base64
import time
import numpy as np
import json


# class Movement:
#     @staticmethod
#     def left():
#         return {"x": -0.5, "y": 0}
    
#     @staticmethod
#     def right():
#         return {"x": 0.5, "y": 0}
    
#     @staticmethod
#     def up():
#         return {"x": 0, "y": 0.5}
    
#     @staticmethod
#     def down():
#         return {"x": 0, "y": -0.5}


class CameraStream:
    def __init__(
        self, camera_ip="192.168.0.174", camera_port=8000, username="admin", password="password", mqtt_broker="lancionaco.ddns.net", mqtt_port=1883
    ):
        # Camera settings
        self.stream_uri = None
        self.cap = None
        self.running = False
        self.frame_count = 0
        self.publish_count = 0
        self.last_frame_time = time.time()
        self.last_read_time = time.time()
        self.last_publish_time = time.time()
        self.last_fps_time = time.time()
        self.current_frame = None
        self.frame_lock = threading.Lock()

        # PTZ control
        self.ptz = None
        self.ptz_config = None
        self.media = None
        self.profile = None
        self.request = None
        self.camera_positioned = False
        self.pan_space = None
        self.tilt_space = None
        self.zoom_space = None

        # MQTT settings
        self.mqtt_client = mqtt.Client(client_id="camera_stream_client", protocol=mqtt.MQTTv311)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect

        # Initialize camera
        self.setup_camera(camera_ip, camera_port, username, password)

        # Connect to MQTT broker
        print(f"[MQTT] Connecting to broker {mqtt_broker}...")
        self.mqtt_client.connect(mqtt_broker, mqtt_port, keepalive=120)

        # Start MQTT loop in a separate thread
        self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever)
        self.mqtt_thread.daemon = True
        self.mqtt_thread.start()

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Connected with result code {rc}")
        if rc == 0:
            print("[MQTT] Successfully connected to broker")
            # Subscribe to movement control topic
            self.mqtt_client.subscribe("camera/move")
            self.mqtt_client.on_message = self.on_move_message
        else:
            print("[MQTT] Connection failed")

    def on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected with result code {rc}")

    def on_move_message(self, client, userdata, msg):
        try:
            self.stop_movement()
        except Exception as e:
            print(f"Error stopping movement: {e}")

        try:
            # Parse the message payload as a string containing a dict
            position = json.loads(msg.payload.decode())
            
            # Create and send the move request
            request = self.ptz.create_type("AbsoluteMove")
            request.ProfileToken = self.profile.token
            request.Position = {
                "PanTilt": {"x": position["x"], "y": position["y"]},
                "Zoom": {"x": 0.5}  # Keep zoom constant
            }
            
            self.ptz.AbsoluteMove(request)
            print(f"Moving camera to x:{position['x']}, y:{position['y']}")
        except Exception as e:
            print(f"Error processing move command: {e}")

    def setup_camera(self, camera_ip, camera_port, username, password):
        # Initialize ONVIF camera
        mycam = ONVIFCamera(camera_ip, camera_port, username, password)

        # Get media service
        self.media = mycam.create_media_service()
        profiles = self.media.GetProfiles()
        self.profile = profiles[0]
        token = self.profile.token

        # Setup PTZ control
        self.ptz = mycam.create_ptz_service()

        # Get PTZ configuration
        self.ptz_config = self.ptz.GetConfiguration({"PTZConfigurationToken": self.profile.PTZConfiguration.token})

        # Get movement spaces from configuration
        self.pan_tilt_space = self.ptz_config.PanTiltLimits.Range

        print(f"Pan range: {self.pan_tilt_space.XRange.Min} to {self.pan_tilt_space.XRange.Max}")

        # Get stream URI
        request = self.media.create_type("GetStreamUri")
        request.ProfileToken = token
        request.StreamSetup = {"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}}

        uri = self.media.GetStreamUri(request)
        stream_uri = uri.Uri

        # Modify URI to include credentials
        stream_parts = stream_uri.split("://")
        self.stream_uri = f"rtsp://{username}:{password}@{stream_parts[1]}"
        print("RTSP Stream URI:", self.stream_uri)

    def start_streaming(self):
        self.cap = cv2.VideoCapture(self.stream_uri)

        # set no buffer
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Get and print stream properties
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.stream_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        print(f"Stream Resolution: {width}x{height}")
        print(f"Stream FPS: {self.stream_fps}")

        self.running = True

        # Start capture and publish threads
        self.capture_thread = threading.Thread(target=self.capture_frames)
        self.publish_thread = threading.Thread(target=self.publish_frames)
        self.capture_thread.daemon = True
        self.publish_thread.daemon = True
        self.capture_thread.start()
        self.publish_thread.start()

    def capture_frames(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.frame_lock:
                    self.current_frame = frame
                self.last_read_time = time.time()

                # cv2.imshow("ONVIF Camera Stream", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    self.stop_streaming()
                    break

                # Calculate actual FPS
                self.frame_count += 1
                if self.frame_count % 30 == 0:
                    fps = 30 / (time.time() - self.last_frame_time)
                    print(f"Actual FPS: {fps:.2f}")
                    self.last_frame_time = time.time()

    def publish_frames(self):
        while self.running:
            with self.frame_lock:
                frame = self.current_frame

            if frame is not None and self.last_publish_time < self.last_read_time:
                # Resize frame to reduce bandwidth (adjust dimensions as needed)
                frame = cv2.resize(frame, (640, 480))

                # Encode frame to JPEG
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                # Convert to base64
                jpg_as_text = buffer.tobytes()

                # Send over MQTT
                self.mqtt_client.publish("camera/stream", jpg_as_text).wait_for_publish()

                self.publish_count += 1
                if self.publish_count % 30 == 0:
                    current_time = time.time()
                    fps = 30 / (current_time - self.last_fps_time)
                    print(f"Publish FPS: {fps:.2f}")
                    self.last_fps_time = time.time()
                self.last_publish_time = time.time()

            # Sleep briefly to prevent CPU overuse
            time.sleep(0.001)

    def stop_movement(self):
        request = self.ptz.create_type("Stop")
        request.ProfileToken = self.profile.token
        self.ptz.Stop(request)

    def stop_streaming(self):
        self.running = False
        self.stop_movement()  # Stop any ongoing movement
        if self.capture_thread is not None:
            self.capture_thread.join()
        if self.publish_thread is not None:
            self.publish_thread.join()
        if self.cap is not None:
            self.cap.release()
        cv2.destroyAllWindows()
        self.mqtt_client.disconnect()


if __name__ == "__main__":
    # Create and start camera stream
    camera_stream = CameraStream()
    try:
        camera_stream.start_streaming()
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping stream...")
        camera_stream.stop_streaming()
