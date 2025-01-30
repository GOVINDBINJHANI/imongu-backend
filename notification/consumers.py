import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = self.scope['url_route']['kwargs']['company_id']
        self.room_group_name = self.group_name
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({"status" : "connected to new group"}))

    async def receive(self, text_data):
        await self.send(text_data=json.dumps({"status" : "we got you"}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def send_notification(self, event):
        data = json.loads(event['message'])
        await self.send(text_data=json.dumps(data))
