import paho.mqtt.client as mqtt
import cv2
import numpy as np
import base64
import threading
import time
from collections import deque
from datetime import datetime

counter = 0
last_time = time.time()

class StreamReceiver:
    def __init__(self, broker_address="lancionaco.ddns.net", port=1883, buffer_size=30):
        self.client = mqtt.Client(client_id="stream_receiver_client", protocol=mqtt.MQTTv311)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # Frame buffer and threading components
        self.frame_buffer = deque(maxlen=buffer_size)
        self.frame_times = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()
        self.running = True
        
        # Statistics
        self.stats_lock = threading.Lock()
        self.received_frames = 0
        self.last_stats_print = time.time()
        self.stats_interval = 5.0  # Print stats every 5 seconds
        self.processing_times = deque(maxlen=100)  # Track message processing times
        self.fps_window = deque(maxlen=100)  # Track frame arrival times for FPS calculation

        print(f"[MQTT] Connecting to broker {broker_address}...")
        self.client.connect(broker_address, port, keepalive=120)

    def on_connect(self, client, userdata, flags, rc):
        print(f"[MQTT] Connected with result code {rc}")
        if rc == 0:
            print("[MQTT] Successfully connected to broker")
            client.subscribe("camera/stream")
        else:
            print("[MQTT] Connection failed")

    def on_disconnect(self, client, userdata, rc):
        print(f"[MQTT] Disconnected with result code {rc}")

    def on_message(self, client, userdata, msg):
        global counter, last_time
        try:            
            # # Decode base64 string to image
            # img_data = base64.b64decode(msg.payload)
            # np_arr = np.frombuffer(img_data, np.uint8)
            # frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            # # Add frame to buffer with timestamp
            # with self.buffer_lock:
            #     self.frame_buffer.append(frame)
            #     self.frame_times.append(datetime.now())
            #     buffer_size = len(self.frame_buffer)

            counter += 1
            if counter % 30 == 0:
                current_time = time.time()
                fps = 30 / (current_time - last_time)
                print(f"Actual FPS: {fps:.2f}")
                last_time = current_time
            
            # # Print warning if buffer is full
            # if buffer_size >= self.frame_buffer.maxlen:
            #     print(f"Warning: Buffer filling up ({buffer_size}/{self.frame_buffer.maxlen})")
                
        except Exception as e:
            print(f"Error processing frame: {e}")

    def get_latest_frame(self):
        """Get the most recent frame from the buffer"""
        with self.buffer_lock:
            if len(self.frame_buffer) > 0:
                return self.frame_buffer[-1].copy()
        return None

    def start(self):
        try:
            # Start MQTT client loop in the main thread
            # Start MQTT client loop in the main thread
            self.client.loop_forever()
        except KeyboardInterrupt:
            print("Stopping receiver...")
            self.running = False
            self.client.disconnect()

if __name__ == "__main__":
    receiver = StreamReceiver()
    receiver.start()