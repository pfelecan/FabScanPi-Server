__author__ = "Mario Lukas"
__copyright__ = "Copyright 2015"
__license__ = "AGPL"
__maintainer__ = "Mario Lukas"
__email__ = "info@mariolukas.de"

import time
import threading
import logging
import json

from fabscan.FSEvents import FSEventManager, FSEvents
from fabscan.controller import HardwareController
from fabscan.util import FSUtil
from fabscan.FSScanProcessor import FSScanProcessor
from fabscan.FSSettings import Settings

class FSState(object):
    IDLE = "IDLE"
    SCANNING = "SCANNING"
    SETTINGS = "SETTINGS"

class FSCommand(object):
    SCAN = "SCAN"
    START = "START"
    STOP = "STOP"
    UPDATE_SETTINGS = "UPDATE_SETTINGS"
    _COMPLETE = "_COMPLETE"

class FSScanner(threading.Thread):

    def __init__(self):

        threading.Thread.__init__(self)
        self._state = FSState.IDLE
        self._logger =  logging.getLogger(__name__)
        self._logger.setLevel(logging.DEBUG)
        self.settings = Settings.instance()
        self.daemon = True
        self.hardwareController = HardwareController.instance()
        self._exit_requested = False

        self.eventManager = FSEventManager.instance()
        self.eventManager.subscribe(FSEvents.ON_CLIENT_CONNECTED, self._on_client_connected)
        self.eventManager.subscribe(FSEvents.COMMAND, self._on_command)

    def run(self):
        while not self._exit_requested:
            self.eventManager.handle_event_q()

    def request_exit(self):
            self._exit_requested = True

    def _on_command(self,mgr, event):

        command = event.command

        ## Start Scan and goto Settings Mode
        if command == FSCommand.SCAN:
            if self._state is FSState.IDLE:
                self.set_state(FSState.SETTINGS)
                self.hardwareController.settings_mode_on()

        ## Update Settings in Settings Mode
        elif command == FSCommand.UPDATE_SETTINGS:
            if self._state is FSState.SETTINGS:
                try:
                    #self._logger.info(event.settings)
                    self.settings.update(event.settings)
                    self.hardwareController.led.on(self.settings.led.red,self.settings.led.green,self.settings.led.blue)
                except:
                    pass

        ## Start Scan Process
        elif command == FSCommand.START:
            if self._state is FSState.SETTINGS:
                self.set_state(FSState.SCANNING)
                self.hardwareController.settings_mode_off()
                self.scanProcessor = FSScanProcessor.start()
                self.scanProcessor.tell({FSEvents.COMMAND:FSCommand.START})

        ## Stop Scan Process or Stop Settings Mode
        elif command == FSCommand.STOP:
            if self._state is FSState.SCANNING:
                self.scanProcessor.ask({FSEvents.COMMAND:FSCommand.STOP})
                self.scanProcessor.stop()
                #self.set_state(FSState.IDLE)

            if self._state is FSState.SETTINGS:
                self.hardwareController.settings_mode_off()

            self.set_state(FSState.IDLE)

        elif command == FSCommand._COMPLETE:
            self.set_state(FSState.IDLE)
            self._logger.info("Scan complete")


    def _on_client_connected(self,eventManager, event):
        message = FSUtil.new_message()
        message['type'] = FSEvents.ON_CLIENT_INIT
        message['data']['client'] = event['client']
        message['data']['state'] = self._state
        #message['data']['points'] = self.pointcloud
        message['data']['settings'] = self.settings.todict(self.settings)
        #message['data']['settings'] = dict()


        eventManager.publish(FSEvents.ON_SOCKET_SEND, message)


    def set_state(self, state):
        self._state = state
        message = FSUtil.new_message()
        message['type'] = FSEvents.ON_STATE_CHANGED
        message['data']['state'] = state
        self.eventManager.publish(FSEvents.ON_SOCKET_BROADCAST,message)