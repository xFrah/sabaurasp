import paho.mqtt.client as mqtt
import time
import subprocess
import json

# Callback functions
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    if rc == 0:
        print("Successfully connected to broker")
    else:
        print("Connection failed, retrying...")

def on_disconnect(client, userdata, rc):
    if rc == 0:
        print("Clean disconnection from broker")
    else:
        print(f"Unexpected disconnection from broker. Return code: {rc}")
        # rc meanings:
        # 0: Clean disconnect
        # 1: Protocol version error
        # 2: Invalid client identifier
        # 3: Server unavailable
        # 4: Bad username or password
        # 5: Not authorized
    while True:
        try:
            client.reconnect()
            break
        except Exception as e:
            print(f"Reconnection failed: {e}")
            time.sleep(5)

# MQTT broker settings
broker_address = "lancionaco.ddns.net"
port = 1883
topic = "sensor/moisture"  # Changed topic to be more descriptive

# Create a MQTT client instance
client = mqtt.Client(
    client_id="python_mqtt_client_001", 
    protocol=mqtt.MQTTv311
)

# Set callback functions
client.on_connect = on_connect
client.on_disconnect = on_disconnect

# Enable automatic reconnection
client.reconnect_delay_set(min_delay=1, max_delay=30)

# Connect to the broker
print(f"Connecting to broker {broker_address}...")
client.connect(broker_address, port, keepalive=120)

# Start the loop in a non-blocking way
client.loop_start()

# RTL_433 command
rtl_command = ["sudo", "rtl_433", "-f", "868M", "-R", "142", "-F", "json"]

# Main loop
try:
    # Start the rtl_433 process
    process = subprocess.Popen(rtl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Read output line by line
    while True:
        line = process.stdout.readline()
        if line:
            try:
                # Parse JSON data
                data = json.loads(line)
                # Publish the JSON data to MQTT
                client.publish(topic, json.dumps(data))
                print(f"Sent sensor data: {data}")
            except json.JSONDecodeError as e:
                # Skip lines that aren't valid JSON
                continue

except KeyboardInterrupt:
    print("\nScript terminated by user")
    process.terminate()  # Terminate the rtl_433 process
    client.loop_stop()
    client.disconnect()
except Exception as e:
    print(f"An error occurred: {e}")
    process.terminate()
    client.loop_stop()
    client.disconnect()
