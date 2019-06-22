# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
"""This module contains user-facing asynchronous clients for the
Azure IoTHub Device SDK for Python.
"""

import logging
from azure.iot.device.common import async_adapter
from azure.iot.device.iothub.abstract_clients import (
    AbstractIoTHubClient,
    AbstractIoTHubDeviceClient,
    AbstractIoTHubModuleClient,
)
from azure.iot.device.iothub.models import Message
from azure.iot.device.iothub.pipeline import constant
from azure.iot.device.iothub.inbox_manager import InboxManager
from .async_inbox import AsyncClientInbox

logger = logging.getLogger(__name__)


class GenericIoTHubClient(AbstractIoTHubClient):
    """A super class representing a generic asynchronous client.
    This class needs to be extended for specific clients.
    """

    def __init__(self, pipeline):
        """Initializer for a generic asynchronous client.

        This initializer should not be called directly.
        Instead, use one of the 'create_from_' classmethods to instantiate

        :param pipeline: The pipeline that the client will use.
        """
        super().__init__(pipeline)
        self._inbox_manager = InboxManager(inbox_type=AsyncClientInbox)
        self._pipeline.on_connected = self._on_state_change
        self._pipeline.on_disconnected = self._on_state_change
        self._pipeline.on_method_request_received = self._inbox_manager.route_method_request

    def _on_state_change(self, new_state):
        """Handler to be called by the pipeline upon a connection state change."""
        logger.info("Connection State - {}".format(new_state))

        if new_state == "disconnected":
            self._on_disconnected()

    def _on_disconnected(self):
        """Helper handler that is called upon a a pipeline disconnect"""
        self._inbox_manager.clear_all_method_requests()
        logger.info("Cleared all pending method requests due to disconnect")

    async def connect(self):
        """Connects the client to an Azure IoT Hub or Azure IoT Edge Hub instance.

        The destination is chosen based on the credentials passed via the auth_provider parameter
        that was provided when this object was initialized.
        """
        logger.info("Connecting to Hub...")
        connect_async = async_adapter.emulate_async(self._pipeline.connect)

        def sync_callback():
            logger.info("Successfully connected to Hub")

        callback = async_adapter.AwaitableCallback(sync_callback)

        await connect_async(callback=callback)
        await callback.completion()

    async def disconnect(self):
        """Disconnect the client from the Azure IoT Hub or Azure IoT Edge Hub instance.
        """
        logger.info("Disconnecting from Hub...")
        disconnect_async = async_adapter.emulate_async(self._pipeline.disconnect)

        def sync_callback():
            logger.info("Successfully disconnected from Hub")

        callback = async_adapter.AwaitableCallback(sync_callback)

        await disconnect_async(callback=callback)
        await callback.completion()

    async def send_d2c_message(self, message):
        """Sends a message to the default events endpoint on the Azure IoT Hub or Azure IoT Edge Hub instance.

        If the connection to the service has not previously been opened by a call to connect, this
        function will open the connection before sending the event.

        :param message: The actual message to send. Anything passed that is not an instance of the
        Message class will be converted to Message object.
        """
        if not isinstance(message, Message):
            message = Message(message)

        logger.info("Sending message to Hub...")
        send_d2c_message_async = async_adapter.emulate_async(self._pipeline.send_d2c_message)

        def sync_callback():
            logger.info("Successfully sent message to Hub")

        callback = async_adapter.AwaitableCallback(sync_callback)

        await send_d2c_message_async(message, callback=callback)
        await callback.completion()

    async def receive_method_request(self, method_name=None):
        """Receive a method request via the Azure IoT Hub or Azure IoT Edge Hub.

        If no method request is yet available, will wait until it is available.

        :param str method_name: Optionally provide the name of the method to receive requests for.
        If this parameter is not given, all methods not already being specifically targeted by
        a different call to receive_method will be received.

        :returns: MethodRequest object representing the received method request.
        """
        if not self._pipeline.feature_enabled[constant.METHODS]:
            await self._enable_feature(constant.METHODS)

        method_inbox = self._inbox_manager.get_method_request_inbox(method_name)

        logger.info("Waiting for method request...")
        method_request = await method_inbox.get()
        logger.info("Received method request")
        return method_request

    async def send_method_response(self, method_response):
        """Send a response to a method request via the Azure IoT Hub or Azure IoT Edge Hub.

        If the connection to the service has not previously been opened by a call to connect, this
        function will open the connection before sending the event.

        :param method_response: The MethodResponse to send
        """
        logger.info("Sending method response to Hub...")
        send_method_response_async = async_adapter.emulate_async(
            self._pipeline.send_method_response
        )

        def sync_callback():
            logger.info("Successfully sent method response to Hub")

        callback = async_adapter.AwaitableCallback(sync_callback)

        # TODO: maybe consolidate method_request, result and status into a new object
        await send_method_response_async(method_response, callback=callback)
        await callback.completion()

    async def _enable_feature(self, feature_name):
        """Enable an Azure IoT Hub feature

        :param feature_name: The name of the feature to enable.
        See azure.iot.device.common.pipeline.constant for possible values.
        """
        logger.info("Enabling feature:" + feature_name + "...")
        enable_feature_async = async_adapter.emulate_async(self._pipeline.enable_feature)

        def sync_callback():
            logger.info("Successfully enabled feature:" + feature_name)

        callback = async_adapter.AwaitableCallback(sync_callback)

        await enable_feature_async(feature_name, callback=callback)

    async def get_twin(self):
        # TODO: copy doc from sync impl once it's finalized
        pass

    async def patch_twin_reported_properties(self, reported_properties_patch):
        # TODO: copy doc from sync impl once it's finalized
        pass

    async def receive_twin_desired_properties_patch(self):
        # TODO: copy doc from sync impl once it's finalized
        pass


class IoTHubDeviceClient(GenericIoTHubClient, AbstractIoTHubDeviceClient):
    """An asynchronous device client that connects to an Azure IoT Hub instance.

    Intended for usage with Python 3.5.3+
    """

    def __init__(self, pipeline):
        """Initializer for a IoTHubDeviceClient.

        This initializer should not be called directly.
        Instead, use one of the 'create_from_' classmethods to instantiate

        :param pipeline: The pipeline that the client will use.
        """
        super().__init__(pipeline)
        self._pipeline.on_c2d_message_received = self._inbox_manager.route_c2d_message

    async def receive_c2d_message(self):
        """Receive a C2D message that has been sent from the Azure IoT Hub.

        If no message is yet available, will wait until an item is available.

        :returns: Message that was sent from the Azure IoT Hub.
        """
        if not self._pipeline.feature_enabled[constant.C2D_MSG]:
            await self._enable_feature(constant.C2D_MSG)
        c2d_inbox = self._inbox_manager.get_c2d_message_inbox()

        logger.info("Waiting for C2D message...")
        message = await c2d_inbox.get()
        logger.info("C2D message received")
        return message


class IoTHubModuleClient(GenericIoTHubClient, AbstractIoTHubModuleClient):
    """An asynchronous module client that connects to an Azure IoT Hub or Azure IoT Edge instance.

    Intended for usage with Python 3.5.3+
    """

    def __init__(self, pipeline):
        """Intializer for a IoTHubModuleClient.

        This initializer should not be called directly.
        Instead, use one of the 'create_from_' classmethods to instantiate

        :param pipeline: The pipeline that the client will use.
        """
        super().__init__(pipeline)
        self._pipeline.on_input_message_received = self._inbox_manager.route_input_message

    async def send_to_output(self, message, output_name):
        """Sends an event/message to the given module output.

        These are outgoing events and are meant to be "output events"

        If the connection to the service has not previously been opened by a call to connect, this
        function will open the connection before sending the event.

        :param message: message to send to the given output. Anything passed that is not an instance of the
        Message class will be converted to Message object.
        :param output_name: Name of the output to send the event to.
        """
        if not isinstance(message, Message):
            message = Message(message)

        message.output_name = output_name

        logger.info("Sending message to output:" + output_name + "...")
        send_output_event_async = async_adapter.emulate_async(self._pipeline.send_output_event)

        def sync_callback():
            logger.info("Successfully sent message to output: " + output_name)

        callback = async_adapter.AwaitableCallback(sync_callback)

        await send_output_event_async(message, callback=callback)
        await callback.completion()

    async def receive_input_message(self, input_name):
        """Receive an input message that has been sent from another Module to a specific input.

        If no message is yet available, will wait until an item is available.

        :param str input_name: The input name to receive a message on.
        :returns: Message that was sent to the specified input.
        """
        if not self._pipeline.feature_enabled[constant.INPUT_MSG]:
            await self._enable_feature(constant.INPUT_MSG)
        inbox = self._inbox_manager.get_input_message_inbox(input_name)

        logger.info("Waiting for input message on: " + input_name + "...")
        message = await inbox.get()
        logger.info("Input message received on: " + input_name)
        return message