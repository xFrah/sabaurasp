from onvif import ONVIFCamera
import cv2
import paho.mqtt.client as mqtt
import threading
import base64
import time
import numpy as np

class CameraStream:
    def __init__(self, camera_ip='192.168.0.174', camera_port=8000, 
                 username='admin', password='password',
                 mqtt_broker="lancionaco.ddns.net", mqtt_port=1883):
        # Camera settings
        self.stream_uri = None
        self.cap = None
        self.running = False
        self.frame_count = 0
        self.publish_count = 0
        self.last_frame_time = time.time()
        self.last_read_time = time.time()
        self.last_publish_time = time.time()
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
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
        else:
            print("[MQTT] Connection failed")

    def on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected with result code {rc}")

    def setup_camera(self, camera_ip, camera_port, username, password):
        # Initialize ONVIF camera
        mycam = ONVIFCamera(camera_ip, camera_port, username, password)
        
        # Get media service
        media = mycam.create_media_service()
        profiles = media.GetProfiles()
        token = profiles[0].token

        # Get stream URI
        request = media.create_type('GetStreamUri')
        request.ProfileToken = token
        request.StreamSetup = {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}}

        uri = media.GetStreamUri(request)
        stream_uri = uri.Uri
        
        # Modify URI to include credentials
        stream_parts = stream_uri.split('://')
        self.stream_uri = f'rtsp://{username}:{password}@{stream_parts[1]}'
        print('RTSP Stream URI:', self.stream_uri)

    def start_streaming(self):
        self.cap = cv2.VideoCapture(self.stream_uri)

        # set no buffer
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        # Get and print stream properties
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.stream_fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.frame_interval = (1000.0 / self.stream_fps) / 4  # Half the frame interval in milliseconds
        print(f'Stream Resolution: {width}x{height}')
        print(f'Stream FPS: {self.stream_fps}')

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
            current_time = time.time()
            elapsed_ms = (current_time - self.last_read_time) * 1000
            
            if elapsed_ms >= self.frame_interval:
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.current_frame = frame
                    self.last_read_time = current_time
                    
                    # Calculate actual FPS
                    self.frame_count += 1
                    if self.frame_count % 30 == 0:
                        fps = 30 / (current_time - self.last_frame_time)
                        print(f"Actual FPS: {fps:.2f}")
                        self.last_frame_time = current_time
            else:
                # Sleep for a short time to prevent CPU overuse
                time.sleep(0.001)

    def publish_frames(self):
        while self.running:
            with self.frame_lock:
                frame = self.current_frame
                
            if frame is not None and self.last_publish_time < self.last_read_time:
                # Resize frame to reduce bandwidth (adjust dimensions as needed)
                frame = cv2.resize(frame, (640, 480))
                
                # Encode frame to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                # Convert to base64
                jpg_as_text = base64.b64encode(buffer).decode()
                
                # Send over MQTT
                self.mqtt_client.publish("camera/stream", jpg_as_text).wait_for_publish()

                self.publish_count += 1
                if self.publish_count % 30 == 0:
                    current_time = time.time()
                    fps = 30 / (current_time - self.last_publish_time)
                    print(f"Publish FPS: {fps:.2f}")
                    self.last_publish_time = current_time
                
                # Display frame (optional)
                cv2.imshow('ONVIF Camera Stream', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.stop_streaming()
                    break
            
            # Sleep briefly to prevent CPU overuse
            time.sleep(0.001)

    def stop_streaming(self):
        self.running = False
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