#!/usr/bin/env python
import ADC0832
import time
import math
import RPi.GPIO as GPIO
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import config
import json

LED = 4
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED, GPIO.OUT)

myPWM = GPIO.PWM(LED, 10)
myPWM.start(50)

def init_sensors():
    ADC0832.setup()

def read_temperature():
    res = ADC0832.getADC(0)  
    Vr = 3.3 * float(res) / 255
    Rt = 10000 * Vr / (3.3 - Vr)
    temp = 1 / (((math.log(Rt / 10000)) / 3950) + (1 / (273.15 + 25)))
    Cel = temp - 273.15
    return Cel

def read_light_sensor():
    res = ADC0832.getADC(1)  
    vol = 3.3 / 255 * res
    lux = res * 100 / 255
    return res, lux, vol

def customCallback(client, userdata, message):
    print("Received a new message:")
    payload = json.loads(message.payload.decode())
    print(f"Message payload: {payload}")
    
    temperature = payload.get('temperature', None)
    
    if temperature and temperature > 20:
        print(f"Temperature {temperature}°C exceeds 20°C. Turning on the LED.")
        GPIO.output(LED, GPIO.HIGH)  # Turn on LED
    else:
        print(f"Temperature {temperature}°C is below or equal to 20°C. Turning off the LED.")
        GPIO.output(LED, GPIO.LOW)  # Turn off LED
    
    print("From topic:")
    print(message.topic)
    print("--------------\n\n")

myMQTTClient = AWSIoTMQTTClient(config.CLIENT_ID)
myMQTTClient.configureEndpoint(config.AWS_HOST, config.AWS_PORT)
myMQTTClient.configureCredentials(config.AWS_ROOT_CA, config.AWS_PRIVATE_KEY, config.AWS_CLIENT_CERT)
myMQTTClient.configureConnectDisconnectTimeout(config.CONN_DISCONN_TIMEOUT)
myMQTTClient.configureMQTTOperationTimeout(config.MQTT_OPER_TIMEOUT)

if myMQTTClient.connect():
    print('AWS connection succeeded')

# Subscribe to the republish topic
republish_topic = "champlain/republish"
myMQTTClient.subscribe(republish_topic, 1, customCallback)
print(f"Subscribed to topic {republish_topic}")
time.sleep(2)

# Initialize sensors
init_sensors()

# Collect and send data every 10 seconds
try:
    while True:
        # Read temperature and light sensor data
        temperature = read_temperature()
        light_res, lux, voltage = read_light_sensor()

        # Adjust PWM brightness based on light sensor
        myPWM.ChangeDutyCycle(lux)

        # Control the LED based on light levels
        if light_res < 128:
            print("dark")
            GPIO.output(LED, GPIO.LOW)
        else:
            print("light")
            GPIO.output(LED, GPIO.HIGH)

        # Print sensor readings
        print(f"Temperature: {temperature:.2f}°C")
        print(f"Light sensor: {light_res}, Voltage: {voltage:.2f}V, Lux: {lux:.2f}")

        # Prepare payload to send to AWS IoT Core
        payload = json.dumps({
            "temperature": temperature,
            "lux": lux,
        })

        # Publish to AWS IoT
        myMQTTClient.publish(config.TOPIC, payload, 1)
        print(f"Sent: {payload} to {config.TOPIC}")

        # Wait for 10 seconds before next reading
        time.sleep(10)

except KeyboardInterrupt:
    ADC0832.destroy()
    GPIO.cleanup()
    print('The end!')
