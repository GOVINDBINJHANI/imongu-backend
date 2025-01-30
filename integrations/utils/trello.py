import requests
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import NotFound
import logging
from imongu_backend_app.models import Feature, Activity, RoleAccess, key_results
from integrations.models import TrelloConnection
from imongu_backend_app.models import okr
from django.conf import settings

TRELLO_API_BASE_URL = "https://api.trello.com/1"
logger = logging.getLogger(__name__)

def setup_webhooks(api_key, token, request):
    """
    Sets up webhooks for the user's Trello boards.
    """
    url = f"{TRELLO_API_BASE_URL}/members/me/boards?key={api_key}&token={token}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        boards = response.json()
        for board in boards:
            board_id = board.get("id")
            if board_id:
                create_webhook(api_key, token, board_id, request)
            else:
                logger.warning("Board ID not found in response")
    except requests.RequestException as e:
        logger.error(f"Failed to retrieve Trello boards: {e}")

def create_webhook(api_key, token, board_id, request):
    """
    Creates a webhook for a specific Trello board.
    """
    callback_url = settings.TRELLO_CALLBACK_URL
    webhook_data = {
        "key": api_key,
        "token": token,
        "description": "Webhook for Trello board",
        "callbackURL": callback_url,
        "idModel": board_id
    }
    webhook_url = f"{TRELLO_API_BASE_URL}/webhooks/"
    try:
        response = requests.post(webhook_url, json=webhook_data)
        response.raise_for_status()
        logger.info(f"Webhook created for board {board_id}")
    except requests.RequestException as e:
        logger.error(f"Failed to create webhook for board {board_id}: {e}")

def update_key_result_and_related_tables(card_id, checklist_item_id, checklist_item_state):
    try:
        key_result = key_results.objects.get(trello_checklist_item_id=checklist_item_id)
        if checklist_item_state == 'complete':
            key_result.current_number = key_result.target_number
            key_result.overall_gain = 100
        elif checklist_item_state == 'incomplete':
            key_result.current_number = key_result.initial_number 
            key_result.overall_gain = 0

        key_result.save()
        okr_instance = key_result.okr_id
        okr_instance.average_gain = calculate_okr_average_gain(okr_instance)
        okr_instance.save()
        
        goal_instance = okr_instance.goal_id
        goal_instance.average_gain = calculate_goal_average_gain(goal_instance)
        goal_instance.save()
    except key_results.DoesNotExist:
        logger.warning(f"No KeyResult entry found for Trello checklist item ID {checklist_item_id}")
    except Exception as e:
        logger.error(f"Error updating KeyResult: {e}")

def calculate_okr_average_gain(okr_instance):
    key_results = okr_instance.key_results.all()
    total_gain = sum(kr.overall_gain for kr in key_results)
    return total_gain / key_results.count() if key_results.exists() else 0

def calculate_goal_average_gain(goal_instance):
    okrs = goal_instance.okr_set.all()
    total_gain = sum(okr.average_gain for okr in okrs)
    return total_gain / okrs.count() if okrs.exists() else 0


def validate_feature_activity_access(role_id, company_id, feature_name, activity_name):
    """
    Validate if the user has access to a specific feature and activity in the company.
    """
    try:
        feature_obj = Feature.objects.get(feature_name=feature_name)
        activity_obj = Activity.objects.get(activity_name=activity_name, feature=feature_obj)
        role_access = RoleAccess.objects.filter(
            role_id=role_id,
            feature=feature_obj,
            activity=activity_obj,
            company_id=company_id
        ).first()
        if not role_access or not role_access.activity_status:
            raise PermissionDenied(f"User does not have access to the activity '{activity_name}' in feature '{feature_name}'.")
    except Feature.DoesNotExist:
        logger.error(f"Feature '{feature_name}' not found.")
        raise NotFound(f"Feature '{feature_name}' not found.")
    except Activity.DoesNotExist:
        logger.error(f"Activity '{activity_name}' not found.")
        raise NotFound(f"Activity '{activity_name}' not found.")
    except Exception as e:
        logger.error(f"Error validating feature and activity access: {e}")
        raise PermissionDenied("Access validation error")



def validate_trello(api_key, token):
    """
    Validates Trello API credentials.
    """
    url = f"{TRELLO_API_BASE_URL}/members/me"
    params = {"key": api_key, "token": token}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False

def get_trello_credentials(user_id):
    try:
        trello_connection = TrelloConnection.objects.get(user_id=user_id)
        api_key, token = trello_connection.api_key, trello_connection.token
        if validate_trello(api_key, token):
            return api_key, token
        logger.error("Invalid Trello credentials for user %s", user_id)
        return None, None
    except TrelloConnection.DoesNotExist:
        logger.warning("No Trello connection found for user %s", user_id)
        return None, None

def trello_create_board(user_id, name):
    api_key, token = get_trello_credentials(user_id)
    if not api_key or not token:
        return None

    url = f"{TRELLO_API_BASE_URL}/boards/"
    params = {"name": name, "key": api_key, "token": token}
    try:
        response = requests.post(url, params=params)
        response.raise_for_status()
        return response.json().get("id")
    except requests.RequestException as e:
        logger.error(f"Error creating Trello board: {e}")
        return None

def trello_get_or_create_list(user_id, board_id, name="To Do"):
    api_key, token = get_trello_credentials(user_id)
    if not api_key or not token:
        logger.error("Missing Trello credentials for user ID %s", user_id)
        return None

    try:
        # Fetch all lists on the board
        url = f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists"
        params = {"key": api_key, "token": token, "fields": "name"}
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error for bad status codes

        # Check if the list already exists
        lists = response.json()
        for trello_list in lists:
            if trello_list.get("name") == name:
                logger.info("Found existing list '%s' on board '%s'", name, board_id)
                return trello_list.get("id")

        # If not found, create a new list
        create_url = f"{TRELLO_API_BASE_URL}/boards/{board_id}/lists"
        create_params = {"name": name, "key": api_key, "token": token}
        create_response = requests.post(create_url, params=create_params)
        create_response.raise_for_status()
        
        logger.info("Created new list '%s' on board '%s'", name, board_id)
        return create_response.json().get("id")

    except requests.RequestException as e:
        logger.error("Error getting or creating list '%s' on board '%s': %s", name, board_id, e)
        return None


def trello_create_card(user_id, list_id, name, description=""):
    api_key, token = get_trello_credentials(user_id)
    if not api_key or not token:
        logger.error("Missing Trello credentials for user ID %s", user_id)
        return None

    url = f"{TRELLO_API_BASE_URL}/cards"
    params = {
        "name": name,
        "desc": description,
        "idList": list_id,
        "key": api_key,
        "token": token
    }
    response = requests.post(url, params=params)
    return response.json().get("id") if response.status_code == 200 else None

def trello_create_checklist(user_id, card_id, name="Key Results"):
    api_key, token = get_trello_credentials(user_id)
    if not api_key or not token:
        logger.error("Missing Trello credentials for user ID %s", user_id)
        return None

    try:
        url = f"{TRELLO_API_BASE_URL}/cards/{card_id}/checklists"
        params = {"name": name, "key": api_key, "token": token}
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        logger.info("Created checklist '%s' on card '%s'", name, card_id)
        return response.json().get("id")

    except requests.RequestException as e:
        logger.error("Failed to create checklist on card '%s': %s", card_id, e)
        return None
    


def trello_add_checklist_item(user_id, checklist_id, name):
    """
    Adds an item to an existing Trello checklist.
    
    Args:
        user_id (int): The ID of the user.
        checklist_id (str): The Trello checklist ID.
        name (str): The name of the checklist item.
    
    Returns:
        str: The ID of the added checklist item if successful, None otherwise.
    """
    api_key, token = get_trello_credentials(user_id)
    if not api_key or not token:
        logger.error("Missing Trello credentials for user ID %s", user_id)
        return None

    try:
        url = f"{TRELLO_API_BASE_URL}/checklists/{checklist_id}/checkItems"
        params = {"name": name, "key": api_key, "token": token}
        response = requests.post(url, params=params)
        response.raise_for_status()
        
        logger.info("Added checklist item '%s' to checklist '%s'", name, checklist_id)
        return response.json().get("id")

    except requests.RequestException as e:
        logger.error("Failed to add checklist item '%s' to checklist '%s': %s", name, checklist_id, e)
        return None
    

def update_okr_progress_on_card_movement(card_id, list_after):
    try:
        okr_instance = okr.objects.get(trello_card_id=card_id)  

        if list_after.lower() == "to do":
            okr_instance.average_gain = 0
            key_results = okr_instance.key_results.all()
            for kr in key_results:
                kr.current_number = kr.initial_number
                kr.overall_gain = 0
                kr.save()
        elif list_after.lower() == "doing":
            okr_instance.average_gain = 50
            key_results = okr_instance.key_results.all()
            for kr in key_results:
                kr.current_number = kr.initial_number
                kr.overall_gain = 50
                kr.save()
        elif list_after.lower() == "done":
            okr_instance.average_gain = 100
            key_results = okr_instance.key_results.all()
            for kr in key_results:
                kr.current_number = kr.target_number
                kr.overall_gain = 100
                kr.save()

        okr_instance.save()

        goal_instance = okr_instance.goal_id
        goal_instance.average_gain = calculate_goal_average_gain(goal_instance)
        goal_instance.save()

        logger.info(f"Updated OKR progress for card {card_id} to {okr_instance.average_gain}%")

    except okr.DoesNotExist:
        logger.warning(f"No OKR entry found for Trello card ID {card_id}")
    except Exception as e:
        logger.error(f"Error updating OKR progress: {e}")


def update_trello_board(api_key, token, board_id, new_title):
    try:
        url = f"https://api.trello.com/1/boards/{board_id}"
        params = {
            'name': new_title,
            'key': api_key,
            'token': token
        }
        response = requests.put(url, params=params)
        
        if response.status_code == 200:
            logger.info(f"Trello board {board_id} update successfully.")
            return True
        else:
            logger.error(f"Failed to update Trello board {board_id}: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"Error update Trello board {board_id}: {e}")
        return False

def delete_trello_board(api_key, token, board_id):
    try:
        url = f"https://api.trello.com/1/boards/{board_id}"
        params = {
            "key": api_key,
            "token": token
        }
        response = requests.delete(url, params=params)
        if response.status_code == 200:
            logger.info(f"Trello board {board_id} deleted successfully.")
            return True
        else:
            logger.error(f"Failed to delete Trello board {board_id}. Response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting Trello board {board_id}: {e}")
        return False
    
def update_trello_card(api_key, token, card_id, new_title, new_description=None):
    try:
        url = f"https://api.trello.com/1/cards/{card_id}"
        params = {
            'name': new_title,
            'desc': new_description if new_description else "",
            'key': api_key,
            'token': token
        }
        response = requests.put(url, params=params)
        
        if response.status_code == 200:
            logger.info(f"Trello card {card_id} updated successfully.")
            return True
        else:
            logger.error(f"Failed to update Trello card {card_id}: {response.json()}")
            return False
    except Exception as e:
        logger.error(f"Error updating Trello card {card_id}: {e}")
        return False

def delete_trello_card(api_key, token, card_id):
    try:
        url = f"https://api.trello.com/1/cards/{card_id}"
        params = {
            "key": api_key,
            "token": token
        }
        response = requests.delete(url, params=params)
        if response.status_code == 200:
            logger.info(f"Trello card {card_id} deleted successfully.")
            return True
        else:
            logger.error(f"Failed to delete Trello card {card_id}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting Trello card {card_id}: {e}")
        return False


def update_trello_checklist_item(api_key, token, card_id, checklist_item_id, new_name):
    try:
        url = f"https://api.trello.com/1/cards/{card_id}/checkItem/{checklist_item_id}"
        params = {
            'name': new_name,
            'key': api_key,
            'token': token
        }
        response = requests.put(url, params=params)
        if response.status_code == 200:
            logger.info(f"Trello checklist item {checklist_item_id} updated successfully.")
            return True
        else:
            logger.error(f"Failed to update Trello checklist item {checklist_item_id}: {response.text}")
            return False

    except requests.RequestException as e:
        logger.error(f"Error updating Trello checklist item {checklist_item_id}: {e}")
        return False


def delete_trello_checklist_item(api_key, token, card_id, checklist_id, checklist_item_id):
    try:
        url = f"https://api.trello.com/1/cards/{card_id}/checklist/{checklist_id}/checkItem/{checklist_item_id}"
        params = {
            'key': api_key,
            'token': token
        }
        response = requests.delete(url, params=params)

        if response.status_code == 200:
            logger.info(f"Trello checklist item {checklist_item_id} deleted successfully.")
            return True
        else:
            logger.error(f"Failed to delete Trello checklist item {checklist_item_id}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error deleting Trello checklist item {checklist_item_id}: {e}")
        return False