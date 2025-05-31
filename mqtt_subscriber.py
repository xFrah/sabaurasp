import paho.mqtt.client as mqtt
import time
import json

# Callback function for when the client connects to the broker
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    if rc == 0:
        print("[MQTT] Successfully connected to broker")
        # Subscribe to the topic upon successful connection
        client.subscribe(topic)
        print(f"[MQTT] Subscribed to topic: {topic}")
    else:
        print("[MQTT] Connection failed, retrying...")

# Callback function for when a message is received
def on_message(client, userdata, msg):
    try:
        # Decode the JSON payload
        data = json.loads(msg.payload.decode())
        print(f"[MQTT] Received message: {data}")
    except json.JSONDecodeError as e:
        print(f"[MQTT] Error decoding JSON: {e}")
        print(f"[MQTT] Raw message: {msg.payload.decode()}")

# Callback for disconnection
def on_disconnect(client, userdata, rc):
    if rc == 0:
        print("[MQTT] Clean disconnection from broker")
    else:
        print(f"[MQTT] Unexpected disconnection from broker. Return code: {rc}")
        while True:
            try:
                client.reconnect()
                break
            except Exception as e:
                print(f"[MQTT] Reconnection failed: {e}")
                time.sleep(5)

# MQTT broker settings (same as in your steerer.py)
broker_address = "lancionaco.love"
port = 1883
topic = "sensor/moisture"

# Create an MQTT client instance
client = mqtt.Client(
    client_id="python_mqtt_subscriber_001",
    protocol=mqtt.MQTTv311
)

# Set callback functions
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Connect to the broker
print(f"[MQTT] Connecting to broker {broker_address}...")
client.connect(broker_address, port, keepalive=120)

# Start the MQTT loop to listen for messages
client.loop_forever() 