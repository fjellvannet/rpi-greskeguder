import time

import paho.mqtt.client as mqtt
import stmpy
from threading import Thread
from sense_hat import SenseHat
import json

MQTT_BROKER = "ec2-13-53-46-117.eu-north-1.compute.amazonaws.com"
MQTT_PORT = 1883

MQTT_TOPIC_INPUT = "raspberrypi"


class RaspberryPiMachine:
    def __init__(self, sense, group_no):
        self.tmp_int = 0

        t_initial = {
            "source": "initial",
            "target": "idle"
        }
        
        t_start_blink = {
            "source": "idle",
            "target": "assistance_light_on",
            "trigger": "assistance_requested",
        }
        
        t_light_off = {
            "source": "assistance_light_on",
            "target": "assistance_light_off",
            "trigger": "t",
        }
        
        t_light_on = {
            "source": "assistance_light_off",
            "target": "assistance_light_on",
            "trigger": "t",
        }

        t_idle_t = {
            "source": "idle",
            "target": "idle",
            "trigger": "t"
        }

        t_stop_off = {
            "source": "assistance_light_off",
            "target": "idle",
            "trigger": "assistance_done"
        }

        t_stop_on = {
            "source": "assistance_light_on",
            "target": "idle",
            "trigger": "assistance_done"
        }

        idle = {
            "name": "idle",
            "entry": "show_state('idle')"
        }

        assistance_light_on = {
            "name": "assistance_light_on",
            "entry": "start_timer('t', 1000); show_state('assistance_light_on')"
        }

        assistance_light_off = {
            "name": "assistance_light_off",
            "entry": "start_timer('t', 1000); show_state('assistance_light_off')"
        }

        self.sense = sense
        self.group_no = group_no

        self.stm = stmpy.Machine(
            name="student_machine",
            transitions=[
                t_initial,
                t_start_blink,
                t_light_on,
                t_light_off,
                t_stop_off,
                t_stop_on,
                t_idle_t
            ],
            states=[
                idle,
                assistance_light_on,
                assistance_light_off
            ],
            obj=self,
        )

    def show_state(self, name):
        print(f"Entered state {name}")
        if name == "idle":
            self.sense.show_letter(str(self.group_no), (0, 255, 0))
        else:
            self.sense.show_letter(
                {"assistance_light_on": str(self.group_no), "assistance_light_off": " "}[name], (255, 0, 0)
            )


class RaspberryPiDriver:
    def on_connect(self, client, userdata, flags, rc):
        # we just log that we are connected
        print("MQTT connected to {}".format(client))

    def on_message(self, client, userdata, msg):
        unwrapped = json.loads(msg.payload)
        self.raspberrypi_machine.send(unwrapped)

    def __init__(self):
        self.sense = SenseHat()
        self.sense.clear()
        self.group_no = self.get_group_no()

        # get the logger object for the component
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set("mosquitto", "mosquitto")
        # callback methods
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        # Connect to the broker
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        # subscribe to proper topic(s) of your choice
        self.mqtt_client.subscribe(f"{MQTT_TOPIC_INPUT}/{self.group_no}")
        # start the internal loop to process MQTT messages
        self.mqtt_client.loop_start()

        # we start the stmpy driver, without any state machines for now
        self.stm_driver = stmpy.Driver()
        self.stm_driver.start(keep_active=True)
        self.raspberrypi_machine = RaspberryPiMachine(self.sense, self.group_no).stm
        self.stm_driver.add_machine(self.raspberrypi_machine)

        Thread(target=self.sense_joystick).start()

    def stop(self):
        self.mqtt_client.loop_stop()
        self.stm_driver.stop()


    def get_group_no(self) -> int:
        #self.sense.show_message("Group #")
        number = 0
        self.sense.show_letter(str(number))
        while True:
            for event in self.sense.stick.get_events():
                if event.action == "pressed":
                    if event.direction in ("up", "right"):
                        number += 1
                        if number > 9:
                            number = 0
                    elif event.direction in ("down", "left"):
                        number -= 1
                        if number < 0:
                            number = 9
                    elif event.direction == "middle":
                        self.sense.clear()
                        return number
            self.sense.show_letter(str(number))
            time.sleep(0.1)


    def sense_joystick(self):
        while True:
            for event in self.sense.stick.get_events():
                if event.action == "pressed":
                    content = "assistance_requested" if self.raspberrypi_machine.state == "idle" else "assistance_done"
                    self.mqtt_client.publish(f"{MQTT_TOPIC_INPUT}/{self.group_no}", json.dumps(content))
                    self.raspberrypi_machine.send(content)
                time.sleep(0.1)



def main():
    t = RaspberryPiDriver()


if __name__ == "__main__":
    main()