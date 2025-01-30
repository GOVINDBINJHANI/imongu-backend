from rest_framework import serializers
from integrations.models import TrelloConnection
from imongu_backend_app.models import User
import logging

logger = logging.getLogger(__name__)

class TrelloConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrelloConnection
        fields = ['company', 'connection_name', 'api_key', 'token', 'board_id']

    def create(self, validated_data):
        # Extract user_id from context
        user_id = self.context.get('user_id')
        
        if not user_id:
            logger.error("User ID is missing from the context.")
            raise serializers.ValidationError({"user_id": "User ID is required."})

        # Retrieve User instance using user_id
        try:
            user_instance = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            logger.error(f"User with ID {user_id} does not exist.")
            raise serializers.ValidationError({"user_id": "Invalid user ID provided."})
        except Exception as e:
            logger.exception(f"Unexpected error while retrieving user with ID {user_id}: {e}")
            raise serializers.ValidationError({"error": "An unexpected error occurred while fetching user data."})

        # Create the Trello connection
        try:
            trello_connection = TrelloConnection.objects.create(user=user_instance, **validated_data)
            logger.info(f"Trello connection created successfully for user ID {user_id}.")
            return trello_connection
        except Exception as e:
            logger.exception(f"Failed to create Trello connection for user ID {user_id}: {e}")
            raise serializers.ValidationError({"error": "Failed to create Trello connection."})
