import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from channels.db import database_sync_to_async
from .models import Employee

class TrackingConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def get_employee(self, user):
        """Safely fetches the employee profile from the database in an async context."""
        try:
            return Employee.objects.select_related('tenant').get(system_username=user.username)
        except Employee.DoesNotExist:
            return None
        

    async def connect(self):
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return
        
        # 1. Fetch the employee securely
        employee = await self.get_employee(self.user)
        if not employee or not employee.tenant:
            await self.close(code=4403) # Reject connection if they have no tenant
            return
        
        self.room_group_name = f"tenant_{employee.tenant.id}_device_{self.user.username}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.broadcast_status(self.user.username, "ONLINE")


    async def disconnect(self, close_code):
        # Remove from group when connection drops
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)    
            
        if self.user and self.user.is_authenticated:
            await self.broadcast_status(self.user.username, "OFFLINE")



    async def receive(self, text_data):
        """
        Receives real-time state flags sent by the background agent client.
        Expects payload: {"status": "IDLE"} or {"status": "ONLINE"}
        """
        try:
            data = json.loads(text_data)
            client_status = data.get("status")
            app_name = data.get("app_name", "")
            username = self.user.username       
            if client_status in ["ONLINE", "IDLE", "OFFLINE"]:
                await self.broadcast_status(username, client_status,app_name)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass


    async def broadcast_status(self, username, status, app_name="", event_type="presence"):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_send( 
                self.room_group_name,
                {
                    "type": "status_message",
                    "username": username,
                    "status": status,
                    "app_name": app_name,
                    "event_type": event_type,
                    "timestamp":timezone.now().isoformat(),
                    }
                )


    async def status_message(self, event):
        await self.send(text_data=json.dumps({
            "username": event.get("username", ""),
            "status": event.get("status", ""),
            "app_name": event.get("app_name", ""),
            "event_type": event.get("event_type", "status"),
            "timestamp": event.get("timestamp", ""),
        }))